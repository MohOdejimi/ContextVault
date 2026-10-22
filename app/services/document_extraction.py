import os
import io
import zipfile
import re
import pymupdf 
import logging

from pathlib import Path
from typing import Literal
from dataclasses import dataclass
from pymupdf import FileDataError

mime_validation_map = {
    "application/pdf",
    "text/plain",
    "text/markdown",
    (
        "application/vnd.openxmlformats-officedocument.",
        "wordprocessingml.document"
    )
}

logger = logging.getLogger(__name__)

def is_docx(data: bytes) -> bool:
    if not data.startswith(b"PK\x03\x04"):
        return False
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            names = set(z.namelist())
            return "[Content_Types].xml" in names and "word/document.xml" in names
    except zipfile.BadZipFile:
        return False

def is_pdf(data: bytes) -> bool:
    return b"%PDF-" in data[:1024]

def is_text_or_is_markdown(data: bytes) -> bool:
    if b"\x00" in data:   
        return False
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as e:
        return False
    return not re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", text)


@dataclass
class SourceLocation:
    kind: Literal["page", "paragraph", "line"]
    index: int

@dataclass
class ExtractedSegment:
    text: str
    source_location: SourceLocation

class UnsupportedDocumentTypeError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)

class CorruptFileError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)

class EmptyDocumentError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)

def pdf_parser(data: bytes):
    segments = []
    try:
        with pymupdf.open(stream=data, filetype="pdf") as doc:
            for page_number, page in enumerate(doc, start=1):
                texts = []
                for _, _, _, _, text, _ , _ in page.get_text("blocks", sort=True):
                    text = text.strip()
                    if not text:
                        continue
                    texts.append(text)
                if len(texts) != 0:
                    segment = ExtractedSegment(
                        text = "\n\n".join(texts),
                        source_location=SourceLocation(
                            kind="page",
                            index=page_number
                        )
                    )
                    segments.append(segment)
        return segments 
    except FileDataError as e:
        logger.exception("Failed to open stream")
        raise CorruptFileError(
            "Corrupted File"
        )
    except RuntimeError as e:
        logger.exception("Unexpected runtime error")
        raise
    except Exception:
        raise
    
def extract_document(data: bytes, metadata) -> list[ExtractedSegment]:
    size = metadata.document_size
    id = metadata.id 
    content_type = metadata.content_type
    filename = metadata.original_filename
    _, file_extension = os.path.splitext(filename)
    file_extension = file_extension.lower()

    if content_type not in mime_validation_map:
        raise UnsupportedDocumentTypeError(
            f"Unsupported document type: {content_type} for document {id}"
        )

    if size == 0:
        raise EmptyDocumentError(
            f"Document can't be empty"
        )

    if content_type == "application/pdf" and is_pdf(data) and file_extension == '.pdf':
        segments = pdf_parser(data)
        if len(segments) == 0:
            raise EmptyDocumentError(
                "Empty Document"
            )
        return segments
        

    if content_type == ("application/vnd.openxmlformats-officedocument." "wordprocessingml.document") and is_docx(data) and file_extension == '.docx':
        if data[:3] == b'\xef\xbb\xbf':
            text = data.decode('utf-8-sig')
        else:
            text = data.decode('utf-8')

    if content_type == "text/plain" and is_text_or_is_markdown(data) and file_extension == '.txt':
        if data[:3] == b'\xef\xbb\xbf':
            text = data.decode('utf-8-sig')
        else:
            text = data.decode('utf-8')


    

    