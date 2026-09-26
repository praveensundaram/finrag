# finrag — Eval Findings

Baseline (commit a276db4, 2026-09-25):
- Retrieval: recall@5 = 1.00, MRR = 0.9667 (15 answerable questions)
- Answers: answerable = 0.9667, unanswerable = 1.00, faithful = 19/19
- Every run is logged in eval/history.jsonl

## 1. Section detection stops at Item 9A
- What: the ITEMS list in explore.py ends at "9A", so Items 9B–16, the exhibit
  list, and the signature page are all labeled 9A (9A has 11 chunks; the real
  Item 9A is about 1–2).
- Impact: q11/q12 (CEO/CFO) use expected_items ["9A"] because that's where the
  signature page landed.
- Fix (M4): extend ITEMS through Item 16, rebuild the corpus, relabel q11/q12.

## 2. Chunk boundaries split related text
- What: the Epic Games appeal is split across Item 3 chunks 2 and 3. Chunk 3
  holds the latest status but never mentions "Epic", so search misses it.
- Evidence: q17 is PARTIAL on every run, while recall@5 still counts it as a HIT
  (Item-level labels can't see chunk-level misses).
- Fix ideas (M4): overlap between chunks, or prefix each chunk with its
  section heading.

## 3. Tables lose their structure
- What: financial tables come through as flat rows of numbers with no column
  headers attached, so the model must infer which number is which year.
- Evidence: no failures yet, but a risk for numeric questions (e.g. q06).

## 4. Limits of the eval itself
- Item-level recall@5 is at the ceiling (1.00), so it can't show improvement.
  MRR is the more useful retrieval number.
- The judge only checks claims against the reference answer. Added a
  faithfulness check after hand-checking found it passed a wrong claim in q03
  ("iPhone had the largest dollar increase"; Services did).
- finrag and the judge both vary run to run (unanswerable went 0.88 → 1.00 with
  no code change). A one-question score change may be noise; rerun before
  concluding.

## 5. Heading map for Apple's FY2025 10-K (from tools/style_census.py)

Checked across the whole filing with a style census, not guessed from samples.

Rules, applied in order (first match wins):

| Order | Rule | Result |
|---|---|---|
| 1 | Before Item 1; page footers ("Apple Inc. \| 2025 Form 10-K \| N"); "Apple Inc."; "PART I–IV" | drop |
| 2 | Block contains a <table> | table |
| 3 | Bold, text starts with "Item N." | level 1: Item title |
| 4 | Bold, not italic | level 2: section heading |
| 5 | Bold and italic | level 3: risk factor title (1A only, full sentences) |
| 6 | Italic, not bold, under 100 chars | level 3: subheading |
| 7 | Text starts with "•" | list item |
| 8 | Everything else | body text |

Evidence:
- Spacing (margin-top) is NOT a reliable signal: headings and body text both appear at 6–18pt.
- Italic headings are 3–43 chars; italic paragraphs are 443+ chars, so a 100-char cutoff is safe.
- Non-Item bold headings are at most 74 chars. Item titles can be up to 119 chars, but are caught by the "Item N." check first.
- Bold "MIXED" blocks are wrappers around tables, so the table check must come before the heading rules.
- Items 9B, 9C and 10–16 exist and use the same bold Item style.
- Known limitation: in Item 8, "Note N –" headings and their subsections are both bold, so they
  land at the same level. Starting simple; revisit only if Item 8 questions suffer in the eval.