# recall@k: for each answerable question, did retrieval return
# at least one chunk from an expected Item?
import json
from explore import search

GOLDEN_PATH = "eval/golden_set.json"
K = 5


def load_golden(path):
    """Load the golden set (a JSON array) and return it as a list of dicts."""
    # TODO: open the file and return json.load(...) of it
    with open(path, "r") as f:
        return json.load(f)


def is_hit(retrieved_items, expected_items):
    """True if ANY retrieved label is one of the expected labels."""
    # TODO: return True if any label in retrieved_items is in expected_items
    return any(item in expected_items for item in retrieved_items)

def main():
    golden = load_golden(GOLDEN_PATH)
    answerable = [q for q in golden if q["type"] == "answerable"]

    hits = 0
    for q in answerable:
        results = search(q["question"], k=K)
        # Each result is a tuple: (score, item, chunk_index, text)
        retrieved_items = [result[1] for result in results]

        hit = is_hit(retrieved_items, q["expected_items"])
        # TODO: if hit, add 1 to hits
        if hit:
            hits += 1

        # TODO: print one line per question: id, HIT or MISS,
        #       expected items, retrieved items
        status = "HIT" if hit else "MISS"
        print(f"Question ID: {q['id']} | {status} | Expected: {q['expected_items']} | Retrieved: {retrieved_items}")

    recall = hits / len(answerable) if answerable else 0
    print(f"\nrecall@{K}: {recall:.2f} ({hits}/{len(answerable)})")


if __name__ == "__main__":
    main()