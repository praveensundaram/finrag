"""Step 2: sections -> chunks of roughly CHUNK_TARGET characters."""
import re

from finrag.config import CHUNK_MIN, CHUNK_TARGET


def pack(pieces, target, min_size=CHUNK_MIN):
    """Greedily pack a list of text pieces into ~target-sized chunks.
    Merges a too-short FINAL chunk back into the previous one so no content is stranded."""
    chunks = []
    current = ""
    for piece in pieces:
        if current and len(current) + 1 + len(piece) > target:
            chunks.append(current)
            current = piece
        else:
            current = f"{current}\n{piece}" if current else piece
    if current:
        chunks.append(current)
    if len(chunks) > 1 and len(chunks[-1]) < min_size:
        runt = chunks.pop()
        chunks[-1] = f"{chunks[-1]}\n{runt}"
    return chunks


def split_paragraph(para, target):
    """Split ONE oversized paragraph into ~target-sized pieces on sentence boundaries."""
    sentences = re.split(r"(?<=[.!?])\s+", para)
    return pack(sentences, target)


def chunk_section(section_text):
    """Split one section into ~CHUNK_TARGET chunks. Oversized paragraphs are broken on
    sentence boundaries first, so no chunk blows past the target and no paragraph is skipped."""
    paragraphs = [p.strip() for p in section_text.split("\n") if p.strip()]
    units = []
    for para in paragraphs:
        if len(para) > CHUNK_TARGET:
            units.extend(split_paragraph(para, CHUNK_TARGET))
        else:
            units.append(para)
    chunks = pack(units, CHUNK_TARGET)
    return [c for c in chunks if len(c) >= CHUNK_MIN]


def chunk_sections(sections):
    """Chunk every section. Returns records: {"item", "chunk_index", "text"}."""
    records = []
    for s in sections:
        for idx, chunk in enumerate(chunk_section(s["text"])):
            records.append({"item": s["item"], "chunk_index": idx, "text": chunk})
    return records
