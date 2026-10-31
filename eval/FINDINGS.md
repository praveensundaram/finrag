# finrag — Eval Findings

Current baseline (commit 8f569f9, 2026-10-29), 37 questions (30 answerable, 7 unanswerable):
- Retrieval: recall@5 = 0.93 (28/30), MRR = 0.92
- Answers: answerable = 0.88, unanswerable = 1.00, faithful = 36/37
- Misses: q11, q12 not retrieved (Item 16 signature chunk outranked by Item 15
  exhibit list) and judged INCORRECT; q17, q22, q28 PARTIAL; q23 CORRECT but unfaithful.
- Per-question results: eval/results_baseline_8f569f9.json
- Unanswerable rose 0.79 → 1.00 because the judge policy changed in 8f569f9,
  not because finrag improved.
- Every run is logged in eval/history.jsonl

Original baseline (commit a276db4, 2026-09-25), 15 answerable + 4 unanswerable questions:
recall@5 = 1.00, MRR = 0.9667, answerable = 0.9667, unanswerable = 1.00, faithful = 19/19.
Findings 1–4 below were written against this baseline.

## 1. Section detection stopped at Item 9A — FIXED in 17ec67b
- What: the ITEMS list in explore.py ended at "9A", so Items 9B–16, the exhibit
  list, and the signature page were all labeled 9A (9A had 11 chunks; the real
  Item 9A is about 1–2).
- Impact: q11/q12 (CEO/CFO) used expected_items ["9A"] because that's where the
  signature page landed.
- Fix: parsing moved to sec2md (Step A), which yields all 23 Items (1–16).
  q11 relabeled to ["16"], q12 to ["9B", "16"].
- Follow-on: after relabeling, q11/q12 became real retrieval misses (see baseline above).

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
- Item-level recall@5 was at the ceiling (1.00) on the original 15 questions.
  With 37 questions it is 0.93, but it is still Item-level: q17 and q28 count as
  hits even though the chunk with the answer detail wasn't retrieved.
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
## 6. q23 "unfaithful" was a one-off generation slip, not a pattern (backlog item 1)
- What: at baseline 8f569f9, q23 (Apple vs S&P 500 over five years) was CORRECT but
  unfaithful. The answer copied the stock table correctly, then summarized it as
  "outperformed the S&P 500 in every measured year," contradicting its own table
  (2021: Apple $132 vs S&P $137) and a later sentence in the same answer.
- Diagnosis: a false claim (intrinsic hallucination: contradicts the context), not
  answered from memory (every number came from the context) and not a judge error.
  Correctness missed it because the reference only covers the 2025 end values;
  the faithfulness check caught it.
- Test: reran q23 5 times on the same commit (generation + judge, no code change).
  Retrieval returned the identical 5 chunks every time (deterministic). All 5
  answers summarized correctly ("every year since 2022", "except September 2021",
  etc.); all 5 judged CORRECT and faithful, and a manual read agreed.
- Result: 1 bad summary in 6 runs. No prompt change: fixing a one-off would be
  overfitting. Run-to-run noise comes from generation (and the judge), not
  retrieval. Temperature can't be lowered to reduce it: claude-sonnet-5 rejects
  the parameter ("deprecated for this model"), for both generation and the judge.
  Faithful 36/37 vs 37/37 is within noise, which supports measuring variance
  (items 3b, 12) before trusting one-question changes.
