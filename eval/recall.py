# recall@k: for each answerable question, did retrieval return
# at least one chunk from an expected Item?
import json
from explore import search

GOLDEN_PATH = "eval/golden_set.json"
K = 5


def load_golden(path):
    """Load the golden set (a JSON array) and return it as a list of dicts."""
    with open(path, "r") as f:
        return json.load(f)


def is_hit(retrieved_items, expected_items):
    """True if ANY retrieved label is one of the expected labels."""
    return any(item in expected_items for item in retrieved_items)

def reciprocal_rank(retrieved_items, expected_items):
    """1 / (position of the first retrieved label that is expected).
    Positions start at 1. Return 0.0 if none of them are expected."""
    for position, item in enumerate(retrieved_items, start=1):
        if item in expected_items:
            return 1.0 / position
    return 0.0

def main():
    golden = load_golden(GOLDEN_PATH)
    answerable = [q for q in golden if q["type"] == "answerable"]

    hits, rr_total = 0, 0.0
    for q in answerable:
        results = search(q["question"], k=K)
        # Each result is a tuple: (score, item, chunk_index, text)
        retrieved_items = [result[1] for result in results]

        hit = is_hit(retrieved_items, q["expected_items"])
        rr = reciprocal_rank(retrieved_items, q["expected_items"])
        if hit: hits += 1
        rr_total += rr

        status = "HIT" if hit else "MISS"
        print(f"Question ID: {q['id']} | {status} | Expected: {q['expected_items']} | Retrieved: {retrieved_items} | RR={rr:.2f}")
    recall = hits / len(answerable) if answerable else 0
    mrr = rr_total / len(answerable) if answerable else 0
    print(f"\nrecall@{K}: {recall:.2f} ({hits}/{len(answerable)})")
    print(f"mean reciprocal rank@{K}: {mrr:.2f}")


if __name__ == "__main__":
    main()