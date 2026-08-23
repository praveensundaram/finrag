# Read the file data/raw/aapl-2025-10k.htm into a string. (open(...).read())
# Parse that string with BeautifulSoup. (from bs4 import BeautifulSoup, then BeautifulSoup(html, "lxml"))
# Strip the noise — remove every <script> and <style> tag, since they're pure junk. (loop over soup(["script", "style"]) and call .decompose() on each)
# Extract and peek — pull the text out (.get_text(separator="\n")), then print how long it is and print the first ~3000 characters so you can eyeball the result.
from bs4 import BeautifulSoup
import re

with open("data/raw/aapl-2025-10k.htm", "r", encoding="utf-8", errors="ignore") as f:
    data = f.read()
soup = BeautifulSoup(data, "html.parser")
for tag in soup(["script", "style"]):
    tag.decompose()

text = soup.get_text(separator="\n")

# The Items we care about, in document order. (A subset is fine to start.)
ITEMS = ["1", "1A", "1B", "1C", "2", "3", "4",
         "5", "6", "7", "7A", "8", "9", "9A"]

def find_last(text, item):
    """Return the LAST character index where 'Item <item>.' appears, or -1."""
    # Build a pattern that tolerates the whitespace variation you discovered:
    # 'Item', space(s), the number, a dot. \s* matches any spaces incl. \xa0.
    pattern = re.compile(rf"Item\s+{re.escape(item)}\s*\.")
    matches = list(pattern.finditer(text))
    if not matches:
        return -1
    return matches[-1].start()

# Build a list of (item, position) for items actually found, in position order.
found = []
for item in ITEMS:
    pos = find_last(text, item)
    if pos != -1:
        found.append((item, pos))
found.sort(key=lambda pair: pair[1])

sections = []
for i in range(len(found)):
    item, start = found[i]
    # The section runs from this Item's position to the NEXT Item's position.
    # For the LAST item, it runs to the end of the document.
    # TODO (you): set `end` to the next item's position, or len(text) if this is the last one.
    #   hint: the next item is found[i + 1], but only if i + 1 < len(found)
    #   the next item's position is the [1] element of that tuple
    if i + 1 < len(found):
        end = found[i + 1][1]
    else:
        end = len(text)

    body = text[start:end].strip()
    sections.append({"item": item, "text": body})

CHUNK_TARGET = 2000   # aim for ~2000 chars/chunk (~400-500 words); tune later against eval
CHUNK_MIN    = 200    # drop chunks smaller than this (kills the "None." noise)

def pack(pieces, target, min_size=CHUNK_MIN):
    """Greedily pack a list of text pieces into ~target-sized chunks.
    Merges a too-short FINAL chunk back into the previous one so no content is stranded."""
    chunks = []
    current = ""

    for piece in pieces:
        if current and len(current) + len(piece) > target:
            chunks.append(current)
            current = piece
        else:
            current = f"{current}\n{piece}" if current else piece
    # STEP 2 goes here (after the loop)
    if current:
        chunks.append(current)

    # STEP 3 goes here (after step 2)
    if len(chunks) > 1 and len(chunks[-1]) < min_size:
        runt = chunks.pop()
        chunks[-1] = f"{chunks[-1]}\n{runt}"

    return chunks

def split_paragraph(para, target):
    """Split ONE oversized paragraph into ~target-sized pieces on sentence boundaries."""
    # STEP 1: split `para` into sentences on sentence boundaries.
    sentences = re.split(r"(?<=[.!?])\s+", para)

    # STEP 2: pack those sentences into ~target-sized pieces and return them.
    return pack(sentences, target)

def chunk_section(section_text):
    """Split one section into ~CHUNK_TARGET chunks. Oversized paragraphs are broken on
    sentence boundaries first, so no chunk blows past the target and no paragraph is skipped."""
    paragraphs = [p.strip() for p in section_text.split("\n") if p.strip()]

    # STEP 1: build the "safe units" list.
    #   Walk each paragraph and route it:
    #     - oversized (longer than CHUNK_TARGET)  -> EXTEND units with split_paragraph(para, CHUNK_TARGET)
    #     - fits                                   -> APPEND para whole
    units = []
    for para in paragraphs:
        if len(para) > CHUNK_TARGET:
            units.extend(split_paragraph(para, CHUNK_TARGET))
        else:
            units.append(para)

    # STEP 2: pack the safe units, then drop genuine orphans.
    chunks = pack(units, CHUNK_TARGET)
    return [c for c in chunks if len(c) >= CHUNK_MIN]


# Test it on the three sections that matter most: the monster, a medium, a tiny one.
for s in sections:
    if s["item"] in ("1A", "7", "1B"):
        cs = chunk_section(s["text"])
        print(f"\nItem {s['item']}: {len(s['text'])} chars -> {len(cs)} chunks")
        for i, c in enumerate(cs):
            print(f"  chunk {i}: {len(c)} chars | {c[:60].strip()!r}")