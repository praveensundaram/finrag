"""Build the corpus: parse -> chunk -> embed -> save to data/processed/.

Usage:  python3 build.py
To rebuild after changing parsing or chunking, delete data/processed/ first.
"""
from finrag.index import build_corpus, corpus_exists

if __name__ == "__main__":
    if corpus_exists():
        print("Saved corpus found — skipping build. Delete data/processed/ to rebuild.")
    else:
        print("No saved corpus found — building it...")
        build_corpus()
