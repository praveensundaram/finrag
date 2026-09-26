"""Step 1: HTML filing -> labeled sections.

This is the module Phase 2 replaces with the structure-aware parser.
"""
import re

from bs4 import BeautifulSoup

from finrag.config import ITEMS


def load_text(path):
    """Read the filing's HTML, strip scripts/styles, and return plain text."""
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        data = f.read()
    soup = BeautifulSoup(data, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    return soup.get_text(separator="\n")


def find_last(text, item):
    """Return the LAST character index where 'Item <item>.' appears, or -1.
    Last-occurrence skips the table-of-contents copy and lands on the body header."""
    pattern = re.compile(rf"Item\s+{re.escape(item)}\s*\.")
    matches = list(pattern.finditer(text))
    if not matches:
        return -1
    return matches[-1].start()


def split_sections(text, items=ITEMS):
    """Slice the text into sections, one per Item found, in document order.
    Returns a list of {"item": ..., "text": ...}."""
    found = []
    for item in items:
        pos = find_last(text, item)
        if pos != -1:
            found.append((item, pos))
    found.sort(key=lambda pair: pair[1])

    sections = []
    for i in range(len(found)):
        item, start = found[i]
        end = found[i + 1][1] if i + 1 < len(found) else len(text)
        sections.append({"item": item, "text": text[start:end].strip()})
    return sections
