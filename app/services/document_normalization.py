import logging 
import re 
import unicodedata

from dataclasses import dataclass 
from typing import Literal, Optional

from .document_extraction import ExtractionResult

@dataclass 
class SourceLocation:
    kind: Literal["page", "paragraph", "line", 'heading', 'link', 'list_item', 'inline', 'code_block', 'table_row', 'caption']
    index: Optional[int] = None

@dataclass 
class NormalizedSegment:
    text: str
    source_location: SourceLocation
    origin_field: Literal["native_text", "ocr", "image_caption"]
    page_number: Optional[int] = None

_NUMBER_PREFIX = re.compile(r'^\s*(?:\d+(?:\.\d+)*[.)]?|[IVXLCDM]+[.)])\s+')

def normalize_heading_text(text: str) -> str:
    text = unicodedata.normalize('NFKC', text)   
    text = re.sub(r'\s+', ' ', text).strip()    
    text = _NUMBER_PREFIX.sub('', text)          
    return text.rstrip(':').strip()  

def normalize_paragraph_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = "".join(
        " " if ch.isspace() else ch
        for ch in text
        if unicodedata.category(ch) != "Cc" or ch.isspace()
    )
    return re.sub(r"\s+", " ", text).strip()

def normalize_extraction_results(extracted_result: list[ExtractionResult]): 
    normalized_segments: list[NormalizedSegment] = []

    for result in extracted_result:
        segment = result.extracted_segment
        if segment is None:
            continue
        diagnostic = result.diagnostic

        text = segment.text 
        source_location = segment.source_location
        kind = source_location.kind
        index = source_location.index 
        page_number = segment.page_number
        origin_field = segment.origin_field 

        if kind == 'heading':
            normalized_heading = normalize_heading_text(text)
            normalized_segment = NormalizedSegment(
                text = normalized_heading,
                source_location = source_location,
                origin_field = origin_field, 
                page_number = page_number
            )
            normalized_segments.append(normalized_segment)
        elif kind == 'paragraph':
            normalized_paragraph_text = normalize_paragraph_text(text)
            normalized_segment = NormalizedSegment(
                text = normalized_paragraph_text,
                source_location = source_location,
                origin_field = origin_field, 
                page_number = page_number
            )
            normalized_segments.append(normalized_segment)

    return normalized_segments