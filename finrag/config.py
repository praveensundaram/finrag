"""All settings in one place. Change a value here and every module sees it."""
import os

# --- Models ---
EMBED_MODEL = "voyage-finance-2"
GEN_MODEL = "claude-sonnet-5"

# --- Chunking ---
CHUNK_TARGET = 2000     # aim for ~2000 chars/chunk (~400-500 words); tune against eval
CHUNK_MIN = 200         # drop chunks smaller than this (kills the "None." noise)

# --- Embedding ---
BATCH_SIZE = 100        # chunks per embedding API call

# --- Paths ---
RAW_PATH = "data/raw/aapl-2025-10k.htm"
OUT_DIR = "data/processed"
CHUNKS_PATH = os.path.join(OUT_DIR, "chunks.jsonl")
VECTORS_PATH = os.path.join(OUT_DIR, "vectors.npy")

# --- Sections ---
# The Items we look for, in document order.
# Known issue (eval/FINDINGS.md): stops at 9A, so Items 9B-16 get merged into 9A.
# Left as-is for this refactor so scores stay identical; fixed in Phase 2.
ITEMS = ["1", "1A", "1B", "1C", "2", "3", "4",
         "5", "6", "7", "7A", "8", "9", "9A"]
