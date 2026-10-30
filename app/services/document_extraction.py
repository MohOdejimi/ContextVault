import io
import logging
import os
import re
import zipfile
import chardet
import pymupdf

from dataclasses import dataclass
from docx import Document
from docx.text.paragraph import Paragraph
from docx.table import Table
from typing import Literal, Optional
from pymupdf import FileDataError
from markdown_it import MarkdownIt


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
    kind: Literal["page", "paragraph", "line", 'heading', 'link', 'list_item', 'inline', 'code_block', 'table_row', 'caption']
    index: Optional[int] = None


@dataclass
class ExtractedSegment:
    text: str
    source_location: SourceLocation
    origin_field: Literal["native_text", "ocr", "image_caption"]
    page_number: Optional[int] = None


@dataclass
class PageDiagnostic:
    classification: Optional[Literal["text_available", "likely_scanned", "unknown"]] = None
    page_number: Optional[int] = None 
    has_images: Optional[bool] = None
    image_count: Optional[int] = None
    image_coverage_ratio: Optional[list[float]] = None
    text_character_count: Optional[int] = None


@dataclass
class ExtractionResult:
    extracted_segment: ExtractedSegment | None
    diagnostic: Optional[PageDiagnostic] = None


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
    segments: list[ExtractionResult] = []
    detected = chardet.detect(data)
    encoding = detected.get('encoding', 'utf-8')
    for line_num, byte_line in enumerate(data.splitlines(), start=1):
        decoded_text = byte_line.decode(encoding, errors='replace').strip()
        if not decoded_text:
            continue
        segment = ExtractedSegment(
            text=decoded_text,
            source_location=SourceLocation(
                kind='line',
                index=line_num
            ),
            origin_field='native_text',
        )
        diagnostic = None

        segments.append(
            ExtractionResult(
                diagnostic=diagnostic,
                extracted_segment=segment,
            )
        )
    return segments 


def md_parser(data: bytes) -> list[ExtractionResult]:
    detected = chardet.detect(data)
    encoding = detected.get('encoding', 'utf-8')
    md_text = data.decode(encoding, errors='replace')

    md = MarkdownIt()
    tokens = md.parse(md_text)

    segments: list[ExtractionResult] = []
    index = 1
    current_block = None
    list_stack = []


    for _, token in enumerate(tokens):
        if token.type.startswith('inline'):
            inline_text = "".join(
                child.content
                for child in (token.children or [])
                if child.type in {"text", "code_inline", "image"}
            )
            if inline_text.strip() == "":
                current_block = None
                continue
            segment_kind = current_block or 'inline'
            if list_stack:
                segment_kind = 'list_item'
            segment = ExtractedSegment(
                text=inline_text,
                source_location=SourceLocation(
                    kind=segment_kind,
                    index=index
                ),
                origin_field='native_text',
                page_number=None
            )
            segments.append(
                ExtractionResult(
                    extracted_segment=segment,
                    diagnostic=None
                )
            ) 
            index += 1
            current_block = None
        elif token.type.startswith('heading_open'):
            current_block = 'heading'
        elif token.type.startswith('paragraph_open'):
            if current_block != 'list':
                current_block = 'paragraph'
        elif token.type.startswith('list_item_open'):
            list_stack.append('list_item')
            current_block = 'list'
        elif token.type.startswith('list_item_close'):
            if list_stack:
                list_stack.pop()
            current_block = None
        elif token.type == 'fence' or token.type == 'code_block':
            code_text = token.content.strip()
            if code_text == '':
                continue 
            segment = ExtractedSegment(
                text=code_text,
                source_location=SourceLocation(
                    kind='code_block',
                    index=index
                ),              
                origin_field='native_text',
                page_number=None
            )                   
            segments.append(
                ExtractionResult(
                    extracted_segment=segment,
                    diagnostic=None         
                )     
            )
            index += 1

    return segments

def flush_list_items_buffer_helper(index: int, list_items_buffer: list):
    result = None
    if list_items_buffer:
            segment = ExtractedSegment(
                text='\n'.join(list_items_buffer),
                source_location=SourceLocation(
                    kind='list',
                    index=index
                ),
                origin_field='native_text',
                page_number=None
            )
            result = ExtractionResult(
                extracted_segment=segment,
                diagnostic=None
            )
            list_items_buffer.clear()

    return result

def is_list_item(paragraph: Paragraph) -> bool:
    paragraph_properties = paragraph._p.pPr

    if paragraph.style.name.startswith('Heading'):
        return False

    if paragraph_properties is not None and paragraph_properties.numPr is not None:
        return True 

    style = paragraph.style 

    while style is not None:
        style_properties = style._element.pPr 

        if style_properties is not None and style_properties.numPr is not None:
            return True 

        style = style.base_style

    return False


def docx_parser(data: bytes) -> list[ExtractionResult]:
    file_like_obj = io.BytesIO(data)
    doc = Document(file_like_obj)
    list_items_buffer = []

    results: list[ExtractionResult] = []
    index = 1

    for block in doc.iter_inner_content():
        if isinstance(block, Paragraph):
            text = block.text.strip()

            kind = 'paragraph'

            if block.style is None:
                if not text:
                    continue 
                else:
                    segment = ExtractedSegment(
                        text=text,
                        source_location=SourceLocation(
                            kind=kind,
                            index=index
                        ),
                        origin_field='native_text',
                        page_number=None
                    )
                    results.append(
                        ExtractionResult(
                            extracted_segment=segment,
                            diagnostic=None
                        )
                    )
                    index += 1
                    continue

            if block.style.name.startswith('Title') or block.style.name.startswith('Heading'):
                kind = 'heading'
            
            if is_list_item(block):
                if text == '':
                    continue
                else:
                    list_items_buffer.append(text)
                continue
            else:
                result = flush_list_items_buffer_helper(index, list_items_buffer)
                if result is not None:
                    results.append(result)
                    index += 1
                    
            if block.style.name.startswith('Caption'):
                kind = 'caption'
            if not text:
                continue
            segment = ExtractedSegment(
                text=text,
                source_location=SourceLocation(
                    kind=kind,
                    index=index
                ),
                origin_field='native_text',
                page_number=None
            )
            results.append(
                ExtractionResult(
                    extracted_segment=segment,
                    diagnostic=None
                )
            )
            index += 1
        elif isinstance(block, Table):
            result = flush_list_items_buffer_helper(index, list_items_buffer)
            if result is not None:
                results.append(result)
                index += 1
            for row in block.rows:
                row_data = [cell.text for cell in row.cells]
                if not any(row_data):
                    continue
                segment = ExtractedSegment(
                    text = '|'.join(row_data),
                    source_location=SourceLocation(
                        kind='table_row',
                        index=index
                    ),
                    origin_field='native_text',
                    page_number=None
                )
                results.append(
                    ExtractionResult(
                        extracted_segment=segment,
                        diagnostic=None
                    )
                )
                index += 1

    result = flush_list_items_buffer_helper(index, list_items_buffer)
    if result is not None:
        results.append(result)
        index += 1

    return results
  
type_to_parser_map = {
    "application/pdf": pdf_parser,
    "text/plain": text_parser,
    "text/markdown": md_parser,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": docx_parser
}


def extract_segments_from_document(data: bytes, metadata) -> list[ExtractionResult]:
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
        results = type_to_parser_map[content_type](data)
        if not results:
            raise EmptyDocumentError('DOCX contains no content')
            #Extend docx parsing logic for old doc files
        return results

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
        
        results = type_to_parser_map[content_type](data)
        if not results:
            raise EmptyDocumentError('MD file contains no content')
        return results

    raise UnsupportedDocumentTypeError(
        f"No parser is configured for content type: {content_type}"
    )