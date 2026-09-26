# Ingestion tests: fast structural checks on parsing and chunking.
# No API calls, so they run in seconds and cost nothing.
import os
import re

import numpy as np
import pytest

from finrag.chunk import chunk_sections
from finrag.config import (CHUNK_MIN, CHUNK_TARGET, CHUNKS_PATH, ITEMS,
                           RAW_PATH, VECTORS_PATH)
from finrag.parse import load_sections

FOOTER = re.compile(r"Apple Inc\. \| 2025 Form 10-K \| \d+")


@pytest.fixture(scope="module")
def sections():
    """Parse the filing once and share the result with every test in this file."""
    return load_sections(RAW_PATH)


@pytest.fixture(scope="module")
def records(sections):
    """Chunk the sections once and share the result."""
    return chunk_sections(sections)


def label(rec):
    """Short description of a chunk for failure messages, e.g. 'Item 3 chunk 2 (1840 chars)'."""
    return f"Item {rec['item']} chunk {rec['chunk_index']} ({len(rec['text'])} chars)"


def test_all_items_found_in_order(sections):
    found = [s["item"] for s in sections]
    assert found == ITEMS


def test_chunks_not_too_small(records):
    too_small = [label(r) for r in records if len(r["text"]) < CHUNK_MIN]
    assert not too_small, f"{len(too_small)} chunk(s) under {CHUNK_MIN} chars: {too_small}"


def test_chunks_not_too_big(records):
    # pack() can merge a final runt (< CHUNK_MIN) into the previous chunk,
    # so the real upper bound is CHUNK_TARGET + CHUNK_MIN.
    limit = CHUNK_TARGET + CHUNK_MIN
    too_big = [label(r) for r in records if len(r["text"]) > limit]
    assert not too_big, f"{len(too_big)} chunk(s) over {limit} chars: {too_big}"


def test_corpus_files_match():
    if not os.path.exists(VECTORS_PATH):
        pytest.skip("No saved corpus; run `python3 build.py` first.")
    with open(CHUNKS_PATH, encoding="utf-8") as f:
        n_chunks = sum(1 for _ in f)
    n_vectors = np.load(VECTORS_PATH).shape[0]
    assert n_chunks == n_vectors, f"{n_chunks} chunks but {n_vectors} vectors"

def test_no_page_footers(records):
    with_footer = [label(r) for r in records if FOOTER.search(r["text"])]
    assert not with_footer, f"{len(with_footer)} chunk(s) contain a page footer: {with_footer}"