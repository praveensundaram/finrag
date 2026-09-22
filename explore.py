# finrag — ingestion + retrieval + generation over Apple's 10-K
# Run once to build the corpus (parse -> chunk -> embed -> save).
# Every run after that loads the saved corpus from disk and answers — no re-embedding.
import warnings
warnings.filterwarnings("ignore")
from bs4 import BeautifulSoup
import re
from dotenv import load_dotenv
import voyageai
import anthropic
import json
import numpy as np
import os
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

# --- Config / clients / paths ---
load_dotenv()
vo = voyageai.Client()
client = anthropic.Anthropic()
console = Console()


EMBED_MODEL  = "voyage-finance-2"
BATCH_SIZE   = 100      # chunks per embedding API call
CHUNK_TARGET = 2000     # aim for ~2000 chars/chunk (~400-500 words); tune later against eval
CHUNK_MIN    = 200      # drop chunks smaller than this (kills the "None." noise)

OUT_DIR      = "data/processed"
os.makedirs(OUT_DIR, exist_ok=True)
CHUNKS_PATH  = os.path.join(OUT_DIR, "chunks.jsonl")
VECTORS_PATH = os.path.join(OUT_DIR, "vectors.npy")

# The Items we care about, in document order.
ITEMS = ["1", "1A", "1B", "1C", "2", "3", "4",
         "5", "6", "7", "7A", "8", "9", "9A"]


# --- Section detection ---
def find_last(text, item):
    """Return the LAST character index where 'Item <item>.' appears, or -1.
    Last-occurrence skips the table-of-contents copy and lands on the body header."""
    pattern = re.compile(rf"Item\s+{re.escape(item)}\s*\.")
    matches = list(pattern.finditer(text))
    if not matches:
        return -1
    return matches[-1].start()


# --- Chunking ---
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


# --- Retrieval ---
# Note: search() reads the module-level `normalized` and `loaded_chunks`, which the
# QUERY block builds below. They exist by the time search() is actually called.
def search(query_text, k=5):
    """Embed the query, score against all stored vectors, return top-k records."""
    q_result = vo.embed(texts=[query_text], model=EMBED_MODEL, input_type="query")
    q = np.array(q_result.embeddings[0])
    q = q / np.linalg.norm(q)
    with np.errstate(divide="ignore", over="ignore", invalid="ignore"):
        scores = normalized @ q
    top_idx = np.argsort(scores)[::-1][:k]
    results = []
    for i in top_idx:
        rec = loaded_chunks[i]
        results.append((float(scores[i]), rec["item"], rec["chunk_index"], rec["text"]))
    return results


# --- Generation ---
def format_context(results):
    """Turn search results into a single labeled context string for the prompt."""
    blocks = []
    for n, (score, item, chunk_index, text) in enumerate(results, start=1):
        blocks.append(f"[Source {n} — Item {item}]\n{text}")
    return "\n\n".join(blocks)


SYSTEM_PROMPT = """You are a financial analyst assistant answering questions about Apple's SEC 10-K filing.

Answer the user's question using ONLY the context provided below the question. Follow these rules:

- Base your answer only on the provided context. Do not use outside knowledge about Apple.
- Cite the source for each claim using its label, e.g. (Source 1, Item 1A).
- If the context does not contain enough information to answer, say so plainly rather than guessing.
- Be concise and factual."""


def answer(question, k=5):
    """Retrieve relevant chunks and have Claude write a grounded, cited answer."""
    results = search(question, k)
    context = format_context(results)
    user_message = f"Context:\n{context}\n\nQuestion: {question}"
    message = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )
    return message.content[0].text


# --- BUILD (only if the saved corpus doesn't exist yet) ---
if not os.path.exists(VECTORS_PATH):
    print("No saved corpus found — building it...")

    # Parse the filing, strip noise, pull out text.
    with open("data/raw/aapl-2025-10k.htm", "r", encoding="utf-8", errors="ignore") as f:
        data = f.read()
    soup = BeautifulSoup(data, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = soup.get_text(separator="\n")

    # Locate each Item's body position, in document order.
    found = []
    for item in ITEMS:
        pos = find_last(text, item)
        if pos != -1:
            found.append((item, pos))
    found.sort(key=lambda pair: pair[1])

    # Slice the document into labeled sections.
    sections = []
    for i in range(len(found)):
        item, start = found[i]
        end = found[i + 1][1] if i + 1 < len(found) else len(text)
        sections.append({"item": item, "text": text[start:end].strip()})

    # Gather chunks, each with provenance (item + position + text).
    records = []
    for s in sections:
        for idx, chunk in enumerate(chunk_section(s["text"])):
            records.append({"item": s["item"], "chunk_index": idx, "text": chunk})
    print(f"gathered {len(records)} chunks across {len(sections)} sections")

    # Embed in batches; collect vectors in order.
    all_vectors = []
    for start in range(0, len(records), BATCH_SIZE):
        batch = records[start:start + BATCH_SIZE]
        texts = [rec["text"] for rec in batch]
        result = vo.embed(texts=texts, model=EMBED_MODEL, input_type="document")
        all_vectors.extend(result.embeddings)
        print(f"  embedded {start + len(batch)} / {len(records)}")

    # Weld each vector back onto its record (same order).
    for rec, vec in zip(records, all_vectors):
        rec["vector"] = vec

    # Save (hybrid): text+provenance -> JSONL, vectors -> .npy, linked by row order.
    with open(CHUNKS_PATH, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps({"item": rec["item"],
                                "chunk_index": rec["chunk_index"],
                                "text": rec["text"]}) + "\n")
    vectors = np.array([rec["vector"] for rec in records])
    np.save(VECTORS_PATH, vectors)
    print(f"saved {len(records)} chunks -> {CHUNKS_PATH}")
    print(f"saved vectors {vectors.shape} -> {VECTORS_PATH}")
else:
    print("Saved corpus found — skipping build.")


# --- QUERY (always runs): load the saved corpus and normalize once ---
loaded_chunks = []
with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
    for line in f:
        loaded_chunks.append(json.loads(line))
loaded_vectors = np.load(VECTORS_PATH)

norms = np.linalg.norm(loaded_vectors, axis=1, keepdims=True)
normalized = loaded_vectors / norms


# --- Smoke test ---
question = "What are the risks from foreign exchange rates?"
response = answer(question)
console.print(Panel(question, title="Question", border_style="cyan"))
console.print(Panel(Markdown(response), title="Answer", border_style="green"))