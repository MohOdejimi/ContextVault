from dataclasses import dataclass
from typing import Optional
from logging import getLogger

from .document_extraction import SourceLocation, PDFBlockMetaData
from .document_normalization import NormalizedResult

logger = getLogger(__name__)


@dataclass(frozen=True)
class ChunkSource:
    source_location: SourceLocation
    origin_field: str
    start_char: int
    end_char: int
    page_number: Optional[int] = None
    pdf_metadata: Optional[PDFBlockMetaData] = None


@dataclass(frozen=True)
class PreparedContentUnit:
    text: str
    kind: str
    source: ChunkSource
    separator_before: str = "\n\n"
    keep_with_next: bool = False
    preferred_split_offsets: tuple[int, ...] = ()


@dataclass
class DocumentChunk:
    document_id: int
    chunk_index: int
    text: str
    token_count: int
    sources: list[ChunkSource]



def _get_separator(kind: str) -> str:
    """
    Determines how adjacent prepared units should be joined.
    """
    if kind in {"list_item", "table_row", "line"}:
        return "\n"

    if kind == "inline":
        return ""

    return "\n\n"


def _get_newline_split_offsets(text: str) -> tuple[int, ...]:
    """
    Returns character offsets immediately after newline characters.
    """
    return tuple(
        index + 1
        for index, character in enumerate(text[:-1])
        if character == "\n"
    )


def _get_pdf_split_offsets(
    text: str,
    metadata: PDFBlockMetaData,
) -> tuple[int, ...]:
    """
    Returns preferred splitting positions between PDF lines.

    Offsets are relative to the complete normalized block text.
    """
    lines = metadata.lines

    if len(lines) < 2:
        return ()

    reconstructed_text = "\n".join(line.text for line in lines)

    # Only trust line boundaries when they match the normalized block.
    if reconstructed_text != text:
        return ()

    offsets = []
    cursor = 0

    for line in lines[:-1]:
        cursor += len(line.text)

        # Include the newline in the preceding portion.
        offsets.append(cursor + 1)
        cursor += 1

    return tuple(offsets)


def _prepare_unit(
    result: NormalizedResult,
    *,
    preferred_split_offsets: tuple[int, ...] = (),
) -> PreparedContentUnit:

    segment = result.extracted_segment

    if segment is None:
        raise ValueError("Cannot prepare a result without an extracted segment.")

    kind = segment.source_location.kind
    text = segment.text

    source = ChunkSource(
        source_location=segment.source_location,
        origin_field=segment.origin_field,
        start_char=0,
        end_char=len(text),
        page_number=segment.page_number,
        pdf_metadata=result.pdf_metadata,
    )

    return PreparedContentUnit(
        text=text,
        kind=kind,
        source=source,
        separator_before=_get_separator(kind),
        keep_with_next=(kind == "heading"),
        preferred_split_offsets=preferred_split_offsets,
    )


def prepare_content_units(
    normalized_results: list[NormalizedResult],
) -> list[PreparedContentUnit]:

    prepared_units: list[PreparedContentUnit] = []

    for result in normalized_results:

        segment = result.extracted_segment

        # Diagnostic-only results do not produce content units.
        if segment is None:
            continue

        text = segment.text

        if not text or not text.strip():
            continue

        kind = segment.source_location.kind
        split_offsets: tuple[int, ...] = ()

        if kind == "block" and result.pdf_metadata is not None:
            split_offsets = _get_pdf_split_offsets(
                text,
                result.pdf_metadata,
            )

        elif kind == "code_block":
            split_offsets = _get_newline_split_offsets(text)

        unit = _prepare_unit(
            result,
            preferred_split_offsets=split_offsets,
        )

        prepared_units.append(unit)

    return prepared_units


HARD_MAXIMUM = 480 
TARGET_CHUNK_SIZE = 350
OVERLAP_TOKENS = 30

def token_assembler(prepared_units: list[PreparedContentUnit], document_id: int, tokenizer) -> list[DocumentChunk]:
    document_chunks: list[DocumentChunk] = []
    current_chunk_text = ""
    source_fragments: list[ChunkSource] = []
    current_token_count = 0
    chunk_index = 0
    emitted = False
    for unit in prepared_units:
        text = unit.text
        separator = unit.separator_before
        if current_chunk_text == "" and not emitted:
            current_chunk_text = text
            current_token_count = len(tokenizer.encode(text)) 

            source_fragment = ChunkSource(
                source_location=unit.source.source_location,
                origin_field=unit.source.origin_field,
                start_char=unit.source.start_char,
                end_char=unit.source.end_char,
                page_number=unit.source.page_number,
                pdf_metadata=unit.source.pdf_metadata
            )

            source_fragments.append(source_fragment)
            if current_token_count <= TARGET_CHUNK_SIZE or unit.keep_with_next == True:
                current_chunk_text = current_chunk_text +  separator
                current_token_count = len(tokenizer.encode(current_chunk_text))
                continue
            if current_token_count > HARD_MAXIMUM:
                logger.warning("Chunk size exceeded hard maximum for document %s, chunk %s", document_id, chunk_index)
                # Recursive text split character and append each split fragement to the document_chunks list

            document_chunk = DocumentChunk(
                document_id=document_id,
                chunk_index=chunk_index,
                text=current_chunk_text,
                token_count=current_token_count,
                sources=source_fragments
            )  
            emitted = True
            current_chunk_tokens = tokenizer.encode(current_chunk_text)
            overlap_tokens = current_chunk_tokens[-OVERLAP_TOKENS:] if len(current_chunk_tokens) > OVERLAP_TOKENS else current_chunk_tokens
            decoded_overlap_tokens = tokenizer.decode(overlap_tokens)

            if len(document_chunks) > 0:
                document_chunks.append(document_chunk)
                current_chunk_text = decoded_overlap_tokens + separator + text
                source_fragments = []
            else:
                document_chunks.append(document_chunk)
                current_chunk_text = decoded_overlap_tokens
                source_fragments = []

            chunk_index += 1  
            current_token_count = len(tokenizer.encode(current_chunk_text))
            if current_token_count > HARD_MAXIMUM:
                logger.warning("Chunk size exceeded hard maximum for document %s, chunk %s", document_id, chunk_index)  
        else:
            candidate_text = current_chunk_text + separator + text
            candidate_token_count = len(tokenizer.encode(candidate_text))
            source_fragment = ChunkSource(
                source_location=unit.source.source_location,
                origin_field=unit.source.origin_field,
                start_char=unit.source.start_char,
                end_char=unit.source.end_char,
                page_number=unit.source.page_number,
                pdf_metadata=unit.source.pdf_metadata
            )

            source_fragments.append(source_fragment)

            if candidate_token_count <= TARGET_CHUNK_SIZE or unit.keep_with_next == True:
                current_chunk_text = candidate_text
                current_token_count = candidate_token_count
                continue
            emitted = True
            if current_token_count > HARD_MAXIMUM:
                logger.warning("Chunk size exceeded hard maximum for document %s, chunk %s", document_id, chunk_index)
            document_chunk = DocumentChunk(
                document_id=document_id,
                chunk_index=chunk_index,
                text=current_chunk_text,
                token_count=current_token_count,
                sources=source_fragments
            )

            current_chunk_tokens = tokenizer.encode(current_chunk_text)
            overlap_tokens = current_chunk_tokens[-OVERLAP_TOKENS:] if len(current_chunk_tokens) > OVERLAP_TOKENS else current_chunk_tokens
            decoded_overlap_tokens = tokenizer.decode(overlap_tokens)

            if len(document_chunks) > 0:
                document_chunks.append(document_chunk)
                current_chunk_text = decoded_overlap_tokens + separator + text
                source_fragments = []
            else:
                document_chunks.append(document_chunk)
                current_chunk_text = decoded_overlap_tokens
                source_fragments = []
            chunk_index += 1  
            current_token_count = len(tokenizer.encode(current_chunk_text))

            if current_token_count > HARD_MAXIMUM:
                logger.warning("Chunk size exceeded hard maximum for document %s, chunk %s", document_id, chunk_index)

    if current_chunk_text:
        if current_token_count > HARD_MAXIMUM:
            logger.warning("Chunk size exceeded hard maximum for document %s, chunk %s", document_id, chunk_index)
        document_chunk = DocumentChunk(
            document_id=document_id,
            chunk_index=chunk_index,
            text=current_chunk_text,
            token_count=current_token_count,
            sources=source_fragments
        )
        document_chunks.append(document_chunk)
    return document_chunks

