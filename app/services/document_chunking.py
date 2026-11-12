from dataclasses import dataclass
from typing import Optional

from .document_extraction import SourceLocation, PDFBlockMetaData
from .document_normalization import NormalizedResult


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
