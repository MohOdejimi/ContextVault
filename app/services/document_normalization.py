import re 
import unicodedata

from dataclasses import dataclass 
from typing import Literal, Optional

from .document_extraction import ExtractionResult
from .document_extraction import SourceLocation


@dataclass 
class NormalizedSegment:
    text: str
    source_location: SourceLocation
    origin_field: Literal["native_text", "ocr", "image_caption"]
    page_number: Optional[int] = None


def normalize_heading_text(text: str) -> str:
    text = unicodedata.normalize('NFC', text)   
    text = re.sub(r'\s+', ' ', text).strip()    
         
    return text.strip()  

def normalize_paragraph_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = "".join(
        " " if ch.isspace() else ch
        for ch in text
        if unicodedata.category(ch) != "Cc" or ch.isspace()
    )
    return re.sub(r"\s+", " ", text).strip()

def normalize_list_item(list_item: str) -> str:
    return list_item.strip()

def normalize_list(text: str) -> str:
    text = unicodedata.normalize('NFC', text)

    normalized_list = ''

    list_items = text.splitlines()
    for index, list_item in enumerate(list_items):
        normalized_list += normalize_list_item(list_item)
        if index != len(list_items) - 1:
            normalized_list += '\n'
    
    return normalized_list

def normalize_code_block(code_block: str) -> str:
    code_block = re.replace('\x00', '')
    lines = code_block.splitlines()
    normalized = '\n'.join(lines)

    return normalized


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

        if kind == 'heading' or kind =='caption':
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
            if normalized_segment.text != '':
                normalized_segments.append(normalized_segment)
        elif kind == 'line':
            normalized_line_text = normalize_paragraph_text(text)
            normalized_segment = NormalizedSegment(
                text = normalized_line_text,
                source_location = source_location,
                origin_field = origin_field, 
                page_number = page_number
            )
            if normalized_segment.text != '':
                normalized_segments.append(normalized_segment)
        elif kind == 'table_row':
            normalized_segment = NormalizedSegment(
                text = text,
                source_location = source_location,
                origin_field = origin_field,
                page_number = page_number
            )
            if normalized_segment.text != '':
                normalized_segments.append(normalized_segment)
        elif kind == 'list_item':
            normalized_list_item_text = normalize_paragraph_text(text)
            normalized_segment = NormalizedSegment(
                text = normalized_list_item_text,
                source_location = source_location,
                origin_field = origin_field,
                page_number = page_number
            )
            if normalized_segment.text != '':
                normalized_segments.append(normalized_segment)
        elif kind == 'list':
            normalized_list_text = normalize_list(text)
            normalized_segment = NormalizedSegment(
                text = normalized_list_text,
                source_location = source_location,
                origin_field = origin_field,
                page_number = page_number
            )
            if normalized_segment.text != '':
                normalized_segments.append(normalized_segment)
        elif kind == 'page':
            normalized_segment = NormalizedSegment(
                text = text,
                source_location = source_location,
                origin_field = origin_field,
                page_number = page_number
            )
            if normalized_segment.text != '':
                normalized_segments.append(normalized_segment)
        elif kind == 'code_block':
            normalized_segment = NormalizedSegment(
                text = normalize_code_block(text),
                source_location = source_location,
                origin_field = origin_field,
                page_number = page_number
            )
            if normalized_segment.text != '':
                normalized_segments.append(normalized_segment)
            
    return normalized_segments