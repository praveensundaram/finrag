"""Step 5: retrieved chunks -> grounded, cited answer from Claude."""
from finrag.clients import anthropic_client
from finrag.config import GEN_MODEL
from finrag.retrieve import search

SYSTEM_PROMPT = """You are a financial analyst assistant answering questions about Apple's SEC 10-K filing.

Answer the user's question using ONLY the context provided below the question. Follow these rules:

- Base your answer only on the provided context. Do not use outside knowledge about Apple.
- Cite the source for each claim using its label, e.g. (Source 1, Item 1A).
- If the context does not contain enough information to answer, say so plainly rather than guessing.
- Be concise and factual."""


def format_context(results):
    """Turn search results into a single labeled context string for the prompt."""
    blocks = []
    for n, (score, item, chunk_index, text) in enumerate(results, start=1):
        blocks.append(f"[Source {n} — Item {item}]\n{text}")
    return "\n\n".join(blocks)


def answer_with_context(question, k=5):
    """Retrieve relevant chunks and have Claude write a grounded, cited answer.
    Returns a tuple: (answer_text, context)."""
    results = search(question, k)
    context = format_context(results)
    user_message = f"Context:\n{context}\n\nQuestion: {question}"
    message = anthropic_client.messages.create(
        model=GEN_MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )
    # The model may put a thinking block first; take the first block that is text.
    text = next(block.text for block in message.content if block.type == "text")
    return text, context


def answer(question, k=5):
    """Same as answer_with_context(), but returns only the answer text."""
    return answer_with_context(question, k)[0]
