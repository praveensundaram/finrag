# Read the file data/raw/aapl-2025-10k.htm into a string. (open(...).read())
# Parse that string with BeautifulSoup. (from bs4 import BeautifulSoup, then BeautifulSoup(html, "lxml"))
# Strip the noise — remove every <script> and <style> tag, since they're pure junk. (loop over soup(["script", "style"]) and call .decompose() on each)
# Extract and peek — pull the text out (.get_text(separator="\n")), then print how long it is and print the first ~3000 characters so you can eyeball the result.
from bs4 import BeautifulSoup
import re
from dotenv import load_dotenv
import voyageai
import json
import numpy as np
import os

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


# # Test it on the three sections that matter most: the monster, a medium, a tiny one.
# for s in sections:
#     if s["item"] in ("1A", "7", "1B"):
#         cs = chunk_section(s["text"])
#         print(f"\nItem {s['item']}: {len(s['text'])} chars -> {len(cs)} chunks")
#         for i, c in enumerate(cs):
#             print(f"  chunk {i}: {len(c)} chars | {c[:60].strip()!r}")





# --- Embedding: full corpus ---

load_dotenv()
vo = voyageai.Client()

EMBED_MODEL = "voyage-finance-2"
BATCH_SIZE  = 100   # chunks per API call; stays under Voyage's per-call limits

# STEP 1: gather ALL chunks, each as a record with provenance.
#   Walk every section, chunk it, and for each chunk build a dict:
#     {"item": <the section's item>, "chunk_index": <its position in that section>, "text": <the chunk>}
#   enumerate(list) gives you (index, value) pairs — use it for chunk_index.
records = []
for s in sections:
    chunks = chunk_section(s["text"])
    # TODO: loop over chunks WITH their index (enumerate), append one dict per chunk to records
    for i, chunk in enumerate(chunks):
        records.append({"item": s["item"], "chunk_index": i, "text": chunk})

print(f"gathered {len(records)} chunks across {len(sections)} sections")

# STEP 2: embed in batches, collecting vectors in order.
#   Walk records in slices of BATCH_SIZE. For each batch:
#     - pull the texts out of the batch records (a list of the "text" fields)
#     - call vo.embed(texts=..., model=EMBED_MODEL, input_type="document")
#     - extend a running list with result.embeddings
all_vectors = []
for start in range(0, len(records), BATCH_SIZE):
    batch = records[start:start + BATCH_SIZE]
    texts = [rec["text"] for rec in batch]
    result = vo.embed(texts=texts, model=EMBED_MODEL, input_type="document")
    all_vectors.extend(result.embeddings)
    print(f"  embedded {start + len(batch)} / {len(records)}")

# STEP 3: weld each vector back onto its record.
#   embed() returns vectors in input order, so all_vectors[i] belongs to records[i].
#   Attach each vector to its record under a "vector" key.
# TODO: loop over records and all_vectors together (zip) and set rec["vector"] = vec
for rec, vec in zip(records, all_vectors):
    rec["vector"] = vec

# sanity checks
print(f"records: {len(records)}, vectors: {len(all_vectors)}")
print(f"dimension: {len(records[0]['vector'])}")


# --- Storage: save (hybrid: text+provenance in JSONL, vectors in .npy) ---
OUT_DIR = "data/processed"
os.makedirs(OUT_DIR, exist_ok=True)   # create the folder if it doesn't exist

CHUNKS_PATH  = os.path.join(OUT_DIR, "chunks.jsonl")
VECTORS_PATH = os.path.join(OUT_DIR, "vectors.npy")

# STEP 1: write the text+provenance to JSONL, one record per line, IN ORDER.
#   For each record, write a JSON object with item / chunk_index / text
#   (everything EXCEPT the vector). One json.dumps(...) per line, followed by "\n".
with open(CHUNKS_PATH, "w", encoding="utf-8") as f:
    for rec in records:
        # TODO: build a dict with just item, chunk_index, text (drop the vector)
        # TODO: write json.dumps(that_dict) + "\n"
        f.write(json.dumps({"item": rec["item"], "chunk_index": rec["chunk_index"], "text": rec["text"]}) + "\n")

# STEP 2: stack all vectors into one array and save as .npy, SAME ORDER.
#   np.array([...]) over the "vector" field of each record, in the same order.
# TODO: vectors = np.array of each rec["vector"], in records order
vectors = np.array([rec["vector"] for rec in records])
np.save(VECTORS_PATH, vectors)

print(f"saved {len(records)} chunks -> {CHUNKS_PATH}")
print(f"saved vectors {vectors.shape} -> {VECTORS_PATH}")

# --- Storage: load back + search ---
loaded_chunks = []        # load the JSONL
with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
    for line in f:
        loaded_chunks.append(json.loads(line))
loaded_vectors = np.load(VECTORS_PATH)
# normalize block (fill TODO)
norms = np.linalg.norm(loaded_vectors, axis=1, keepdims=True)
normalized = loaded_vectors / norms

def search(query_text, k=5):
    # embed the query — note input_type="query", NOT "document"
    q_result = vo.embed(texts=[query_text], model=EMBED_MODEL, input_type="query")
    q = np.array(q_result.embeddings[0])

    # normalize the query the same way
    q = q / np.linalg.norm(q)

    # score against all stored vectors — 120 dot products in one op
    with np.errstate(divide="ignore", over="ignore", invalid="ignore"):
        scores = normalized @ q

    # indices of the top-k scores, highest first
    top_idx = np.argsort(scores)[::-1][:k]

    results = []
    for i in top_idx:
        rec = loaded_chunks[i]
        results.append((float(scores[i]), rec["item"], rec["chunk_index"], rec["text"]))
    return results

# smoke-test loop that calls search(...) and prints
for score, item, idx, text in search("What are the risks from foreign exchange rates?"):
    print(f"\n[{score:.3f}] Item {item} chunk {idx}")
    print(f"  {text[:150].strip()}...")


