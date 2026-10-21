import os
import io
import zipfile
import re

from pathlib import Path
from typing import Literal
from dataclasses import dataclass

mime_validation_map = {
    "application/pdf",
    "text/plain",
    "text/markdown",
    (
        "application/vnd.openxmlformats-officedocument.",
        "wordprocessingml.document"
    )
}

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

class EmptyDocumentError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)
    
def extract_document(data: bytes, metadata):
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
        pass 

    if content_type == ("application/vnd.openxmlformats-officedocument." "wordprocessingml.document") and is_docx(data) and file_extension == '.docx':
        pass 

    if content_type == "text/markdown" and is_text_or_is_markdown(data) and file_extension == '.md':
        text = data.decode("utf-8-sig")

    if content_type == "text/plain" and is_text_or_is_markdown(data) and file_extension == '.txt':
        text = data.decode("utf-8-sig")


    

    