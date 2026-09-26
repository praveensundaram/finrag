"""Step 4: question -> top-k most similar chunks.

The corpus is loaded the first time search() is called, not when this module is
imported, so importing never does hidden work.
"""
import numpy as np

from finrag.clients import voyage_client
from finrag.config import EMBED_MODEL
from finrag.index import load_corpus

_chunks = None        # list of chunk records, filled on first search
_normalized = None    # matching unit-length vectors


def _ensure_loaded():
    """Load the corpus into memory once, on first use."""
    global _chunks, _normalized
    if _chunks is None:
        _chunks, _normalized = load_corpus()


def search(query_text, k=5):
    """Embed the query, score it against every chunk, return the top-k as
    (score, item, chunk_index, text) tuples, best first."""
    _ensure_loaded()
    q_result = voyage_client.embed(texts=[query_text], model=EMBED_MODEL, input_type="query")
    q = np.array(q_result.embeddings[0])
    q = q / np.linalg.norm(q)
    # Benign macOS Accelerate/BLAS warning on this matmul (data checked finite); keep narrow.
    with np.errstate(divide="ignore", over="ignore", invalid="ignore"):
        scores = _normalized @ q
    top_idx = np.argsort(scores)[::-1][:k]
    results = []
    for i in top_idx:
        rec = _chunks[i]
        results.append((float(scores[i]), rec["item"], rec["chunk_index"], rec["text"]))
    return results
