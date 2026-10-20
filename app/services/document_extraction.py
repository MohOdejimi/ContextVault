import os

from pathlib import Path
from typing import Literal
from dataclasses import dataclass

mime_validation_map = {"application/pdf","text/plain","text/markdown",
    (
        "application/vnd.openxmlformats-officedocument."
        "wordprocessingml.document"
    )
}

def is_pdf(data: bytes) -> bool:
    return b"%PDF-" in data[:1024]

def is_text(data: bytes) -> bool:
    if b"\x00" in data[:8192]:   
        return False
    try:
        data[:8192].decode("utf-8")
    except UnicodeDecodeError as e:
        if e.start < len(data[:8192]) - 3:
            return False
    return True

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
    
def extract_document(data, filename, size, content_type):
    if size == 0:
        raise EmptyDocumentError

    if content_type not in mime_validation_map:
        raise UnsupportedDocumentTypeError(f"Invalid file type '{content_type}'. Allowed '{', '.join(mime_validation_map)}'")

    

    