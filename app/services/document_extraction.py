import io
import logging
import os
import re
import zipfile
import chardet
from dataclasses import dataclass
from typing import Literal

import pymupdf
from pymupdf import FileDataError

logger = logging.getLogger(__name__)

MIME_VALIDATION_SET = {
    "application/pdf",
    "text/plain",
    "text/markdown",
    (
        "application/vnd.openxmlformats-officedocument."
        "wordprocessingml.document"
    ),
}

LIKELY_SCANNED_COVERAGE_THRESHOLD = 0.75


@dataclass
class SourceLocation:
    kind: Literal["page", "paragraph", "line"]
    index: int


@dataclass
class ExtractedSegment:
    text: str
    source_location: SourceLocation
    page_number: int | None
    origin_field: Literal["native_text", "ocr", "image_caption"]


@dataclass
class PageDiagnostic:
    page_number: int
    has_images: bool
    image_count: int
    image_coverage_ratio: list[float]
    text_character_count: int
    classification: Literal["text_available", "likely_scanned", "unknown"]


@dataclass
class ExtractionResult:
    extracted_segment: ExtractedSegment | None
    diagnostic: PageDiagnostic


class UnsupportedDocumentTypeError(Exception):
    pass


class CorruptFileError(Exception):
    pass


class EmptyDocumentError(Exception):
    pass


class OCRRequiredError(Exception):
    pass


def is_docx(data: bytes) -> bool:
    if not data.startswith(b"PK\x03\x04"):
        return False

    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = set(archive.namelist())
            return (
                "[Content_Types].xml" in names
                and "word/document.xml" in names
            )
    except (zipfile.BadZipFile, OSError):
        return False


def is_pdf(data: bytes) -> bool:
    return b"%PDF-" in data[:1024]


def is_text_or_is_markdown(data: bytes) -> bool:
    if b"\x00" in data:
        return False

    try:
        detected = chardet.detect(data)
        encoding = detected.get('encoding', 'utf-8')
        text = data.decode(encoding)
    except UnicodeDecodeError:
        return False

    return not re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", text)


def _inspect_page(page, page_number: int) -> tuple[str, PageDiagnostic]:
    texts: list[str] = []
    text_character_count = 0

    for block in page.get_text("blocks", sort=True):
        text = block[4].strip()
        if not text:
            continue
        texts.append(text)
        text_character_count += len(text)

    page_rect = page.rect
    page_area = page_rect.get_area()
    coverage_ratios: list[float] = []
    image_count = 0

    if page_area > 0:
        for image_info in page.get_image_info():
            bbox = pymupdf.Rect(image_info["bbox"])
            visible = bbox & page_rect

            if visible.is_empty or visible.get_area() <= 0:
                continue

            coverage = visible.get_area() / page_area
            coverage_ratios.append(max(0.0, min(1.0, coverage)))
            image_count += 1

    native_text = "\n\n".join(texts)

    if text_character_count > 0:
        classification = "text_available"
    elif any(
        ratio >= LIKELY_SCANNED_COVERAGE_THRESHOLD
        for ratio in coverage_ratios
    ):
        classification = "likely_scanned"
    else:
        classification = "unknown"

    diagnostic = PageDiagnostic(
        page_number=page_number,
        has_images=image_count > 0,
        image_count=image_count,
        image_coverage_ratio=coverage_ratios,
        text_character_count=text_character_count,
        classification=classification,
    )
    return native_text, diagnostic


def pdf_parser(data: bytes) -> list[ExtractionResult]:
    extraction_results: list[ExtractionResult] = []

    try:
        with pymupdf.open(stream=data, filetype="pdf") as doc:
            for page_number, page in enumerate(doc, start=1):
                native_text, diagnostic = _inspect_page(page, page_number)

                segment = None
                if native_text:
                    segment = ExtractedSegment(
                        text=native_text,
                        source_location=SourceLocation(
                            kind="page",
                            index=page_number,
                        ),
                        page_number=page_number,
                        origin_field="native_text",
                    )

                extraction_results.append(
                    ExtractionResult(
                        extracted_segment=segment,
                        diagnostic=diagnostic,
                    )
                )

        return extraction_results

    except FileDataError as exc:
        logger.exception("Failed to open PDF stream")
        raise CorruptFileError("Corrupted PDF file") from exc
    except (RuntimeError, ValueError) as exc:
        logger.exception("PDF inspection or extraction failed")
        raise CorruptFileError("Unable to read PDF file") from exc

def text_parser(data: bytes) -> list[ExtractionResult]:
    try:
        segments = []
        for line_num, byte_line in enumerate(data.splitlines(), start=1):
            detected = chardet.detect(data)
            encoding = detected.get('encoding', 'utf-8')
            decoded_text = byte_line.decode(encoding, errors='replace')
            segment = ExtractedSegment(
                text=decoded_text.strip(),
                source_location=SourceLocation(
                    kind='line',
                    index=line_num
                ),
                page_number=line_num,
                origin_field='native_text'
            )

            segments.append(segment)
        return segments 
    except Exception as e:
        raise
    
type_to_parser_map = {
    "application/pdf": pdf_parser,
    "text/plain": text_parser,
}


def extract_document(data: bytes, metadata) -> list[ExtractionResult]:
    document_id = metadata.id
    size = metadata.document_size
    content_type = metadata.content_type.lower().strip()
    filename = metadata.original_filename
    _, file_extension = os.path.splitext(filename)
    file_extension = file_extension.lower()

    if content_type not in MIME_VALIDATION_SET:
        raise UnsupportedDocumentTypeError(
            f"Unsupported document type: {content_type} "
            f"for document {document_id}"
        )

    if size == 0 or len(data) == 0:
        raise EmptyDocumentError("Document can't be empty")

    if content_type == "application/pdf":
        if file_extension != ".pdf" or not is_pdf(data):
            raise CorruptFileError(
                f"PDF content does not match the filename for document "
                f"{document_id}"
            )

        results = type_to_parser_map[content_type](data)
        if not results:
            raise EmptyDocumentError("PDF contains no pages")
        return results


    if content_type == (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ):
        if file_extension != ".docx" or not is_docx(data):
            raise CorruptFileError(
                f"DOCX content does not match the filename for document "
                f"{document_id}"
            )
        raise NotImplementedError("DOCX extraction has not been implemented yet")

    if content_type == "text/plain":
        if file_extension != ".txt" or not is_text_or_is_markdown(data):
            raise CorruptFileError(
                f"TXT content does not match the filename for document "
                f"{document_id}"
            )
        results = type_to_parser_map[content_type](data)
        if not results:
            raise EmptyDocumentError('TXT file contains no content')
        return results
    
    if content_type == "text/markdown":
        if file_extension != ".md" or not is_text_or_is_markdown(data):
            raise CorruptFileError(
                f"Markdown content does not match the filename for document "
                f"{document_id}"
            )
        raise NotImplementedError(
            "Markdown extraction has not been implemented yet"
        )

    raise UnsupportedDocumentTypeError(
        f"No parser is configured for content type: {content_type}"
    )
