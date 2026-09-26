"""Step 3: chunks -> embeddings -> saved corpus on disk (and loading it back).

Storage (hybrid): text + provenance in chunks.jsonl, vectors in vectors.npy.
Invariant: row i of vectors.npy is the embedding of line i of chunks.jsonl.
"""
import json
import os

import numpy as np

from finrag.chunk import chunk_sections
from finrag.clients import voyage_client
from finrag.config import (BATCH_SIZE, CHUNKS_PATH, EMBED_MODEL, OUT_DIR,
                           RAW_PATH, VECTORS_PATH)
from finrag.parse import load_text, split_sections


def corpus_exists():
    """True if a saved corpus is already on disk."""
    return os.path.exists(VECTORS_PATH)


def embed_texts(texts):
    """Embed a list of document texts in batches. Returns vectors in the same order."""
    all_vectors = []
    for start in range(0, len(texts), BATCH_SIZE):
        batch = texts[start:start + BATCH_SIZE]
        result = voyage_client.embed(texts=batch, model=EMBED_MODEL, input_type="document")
        all_vectors.extend(result.embeddings)
        print(f"  embedded {start + len(batch)} / {len(texts)}")
    return np.array(all_vectors)


def save_corpus(records, vectors):
    """Write chunks.jsonl and vectors.npy, linked by row order."""
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(CHUNKS_PATH, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps({"item": rec["item"],
                                "chunk_index": rec["chunk_index"],
                                "text": rec["text"]}) + "\n")
    np.save(VECTORS_PATH, vectors)
    print(f"saved {len(records)} chunks -> {CHUNKS_PATH}")
    print(f"saved vectors {vectors.shape} -> {VECTORS_PATH}")


def build_corpus(raw_path=RAW_PATH):
    """Full ingestion: parse -> chunk -> embed -> save."""
    text = load_text(raw_path)
    sections = split_sections(text)
    records = chunk_sections(sections)
    print(f"gathered {len(records)} chunks across {len(sections)} sections")
    vectors = embed_texts([rec["text"] for rec in records])
    save_corpus(records, vectors)


def load_corpus():
    """Load the saved corpus. Returns (chunks, normalized_vectors)."""
    if not corpus_exists():
        raise FileNotFoundError(
            f"No corpus at {VECTORS_PATH}. Run `python3 build.py` first."
        )
    chunks = []
    with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
        for line in f:
            chunks.append(json.loads(line))
    vectors = np.load(VECTORS_PATH)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return chunks, vectors / norms
