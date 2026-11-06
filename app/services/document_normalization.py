import re 
import unicodedata

from dataclasses import dataclass 
from typing import Literal, Optional

from .document_extraction import ExtractionResult
from .document_extraction import SourceLocation


@dataclass 
class NormalizedResult(ExtractionResult):
    pass

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
    normalized_results : list[NormalizedResult] = []

    for result in extracted_result:
        segment = result.extracted_segment
        diagnostic = result.diagnostic
        pdf_metadata = result.pdf_metadata

        if segment is None:
            # Potential OCR Handling
            normalized_result = NormalizedResult(
                extracted_segment = segment,
                diagnostic = diagnostic,
                pdf_metadata = pdf_metadata
            )
            normalized_results.append(normalized_result)
            continue

        text = segment.text 
        source_location = segment.source_location
        kind = source_location.kind


        if kind == 'heading' or kind =='caption':
            normalized_heading = normalize_heading_text(text)
            segment.text = normalized_heading
            normalized_result = NormalizedResult(
                extracted_segment = segment,
                diagnostic = diagnostic,
                pdf_metadata = pdf_metadata
            )
            if normalized_heading != "":
                normalized_results.append(normalized_result)
        elif kind == 'paragraph':
            normalized_paragraph_text = normalize_paragraph_text(text)
            segment.text = normalized_paragraph_text
            normalized_result = NormalizedResult(
                extracted_segment = segment,
                diagnostic = diagnostic,
                pdf_metadata = pdf_metadata
            )
            if normalized_paragraph_text != '':
                normalized_results.append(normalized_result)
        elif kind == 'line':
            normalized_line_text = normalize_paragraph_text(text)
            segment.text = normalized_line_text
            normalized_result = NormalizedResult(
                extracted_segment = segment,
                diagnostic = diagnostic,
                pdf_metadata = pdf_metadata
            )
            if normalized_line_text != '':
                normalized_results.append(normalized_result)
        elif kind == 'table_row':
            normalized_results.append(result)
        elif kind == 'list_item':
            normalized_list_item_text = normalize_paragraph_text(text)
            segment.text = normalized_list_item_text
            normalized_result = NormalizedResult(
                extracted_segment = segment,
                diagnostic = diagnostic,
                pdf_metadata = pdf_metadata
            )
            if normalized_list_item_text != '':
                normalized_results.append(normalized_result)
        elif kind == 'list':
            normalized_list_text = normalize_list(text)
            segment.text = normalized_list_text
            normalized_result = NormalizedResult(
                extracted_segment = segment,
                diagnostic = diagnostic,
                pdf_metadata = pdf_metadata
            )
            if normalized_list_text != '':
                normalized_results.append(normalized_result)
        elif kind == 'code_block':
            normalized_code_block_text = normalize_code_block(text)
            segment.text = normalized_code_block_text
            normalized_result = NormalizedResult(
                extracted_segment = segment,
                diagnostic = diagnostic,
                pdf_metadata = pdf_metadata
            )
            if normalized_code_block_text != '':
                normalized_results.append(normalized_result)
        elif kind == 'block':
            block_text = ''
            for idx, line in enumerate(pdf_metadata.lines):
                line_text = line.text 
                line_text = normalize_paragraph_text(line_text)
                if line_text == '':
                    continue
                block_text += line_text
                if idx != len(pdf_metadata.lines) - 1:
                    block_text += "\n"
            block_text.strip()
            segment.text = block_text
            normalized_result = NormalizedResult(
                extracted_segment = segment,
                diagnostic = diagnostic,
                pdf_metadata = pdf_metadata
            )
            if block_text != "":
                normalized_results.append(normalized_result)

          
    return normalized_results 