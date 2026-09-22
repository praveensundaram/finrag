import json, sys

keyword = sys.argv[1].lower()
with open("data/processed/chunks.jsonl") as f:
    for line in f:
        c = json.loads(line)
        text = c["text"]
        pos = text.lower().find(keyword)
        if pos != -1:
            snippet = text[max(0, pos - 150): pos + 250].replace("\n", " ")
            print(f"[Item {c['item']} | chunk {c['chunk_index']}] ...{snippet}...\n")