# finrag — context and working rules for Claude

## Who I am and why this exists

I'm Praveen, building finrag as my portfolio project for Forward Deployed Engineer (FDE) roles.
I need to understand and defend every line in interviews, so **learning matters as much as the code**.

## How to work with me

- Explain the concept and the tradeoffs **before** any code. Go slowly on unfamiliar pieces; use small concrete examples.
- Give me **skeletons with TODOs**; I fill in the logic myself. Don't write full implementations unless I explicitly ask.
- Running commands, reading files, running tests and evals is fine.
- Ask me a short check question after explaining something new, and wait for my answer before moving on.
- Be direct. Surface gaps honestly, and correct yourself if something you said earlier was wrong.
- Use plain language; I'm not an HTML/ML specialist.
- When a fix teaches something interview-worthy, add a Q&A entry to `notes/INTERVIEW_QA.md`.

## Engineering rules

- **One change at a time.** Commit before running evals, so the logged commit hash matches the code.
- Run `python3 -m eval.recall` first (fast, no LLM, deterministic), then `python3 -m eval.score`.
- Compare against the baseline below and look at **which questions changed**, not just averages.
- Judge every change by its effect on retrieval **overall**, never by whether it rescues one question (no overfitting to the golden set).
- Before claiming an improvement, ask what moved: the **code**, the **rules** (judge policy), or the **data** (golden set).
- Record findings in `eval/FINDINGS.md`; keep or revert each change based on the numbers.

## The system

Hand-built RAG over Apple's FY2025 10-K (`data/raw/aapl-2025-10k.htm`).

| Stage | Where | What |
|---|---|---|
| Parse | `finrag/parse.py` | `load_sections()` uses sec2md → 23 Items (1–16) as `{item, text}`, footers removed, tables as Markdown |
| Chunk | `finrag/chunk.py` | Per Item: split lines → oversized paragraphs split at sentences (`split_paragraph`) → greedy `pack()` to `CHUNK_TARGET` 2,000 chars → merge-back runts → drop < `CHUNK_MIN` 200. No overlap. 128 chunks. |
| Embed | `finrag/index.py` | Voyage `voyage-finance-2` (1,024 dims, normalized); `input_type="document"` for chunks, `"query"` for questions |
| Store | `data/processed/` (gitignored) | `chunks.jsonl` + `vectors.npy`, linked **only by row order**. Built once by `build.py`; `rm -rf data/processed` to force a rebuild |
| Search | `finrag/retrieve.py` | Brute-force cosine: `vectors @ q`, `argsort[::-1][:k]`, k=5. Corpus loaded lazily. `np.errstate` scoped around the matmul (benign macOS BLAS warnings) |
| Generate | `finrag/generate.py` | `format_context()` → `[Source N — Item X]` blocks; `SYSTEM_PROMPT`: only use context, cite `(Source N, Item X)`, say when missing; `claude-sonnet-5`, `max_tokens=1024`. `answer_with_context()` also returns the context for evals |

Settings live in `finrag/config.py`; API clients in `finrag/clients.py`; keys in `.env` (never commit it).

## Evaluation

- `eval/golden_set.json`: 37 questions (30 answerable, 7 unanswerable) with `expected_items` and `reference_answer`.
- `eval/recall.py`: recall@5 (really **hit rate@5**: any top-5 chunk from any expected Item) and MRR.
- `eval/judge.py` + `eval/score.py`: Claude judge → CORRECT / PARTIAL / INCORRECT (1 / 0.5 / 0), plus `faithful` and `unsupported_claims` checked against the retrieved context. Unparseable judge output = ERROR, excluded and reported separately.
  - Judge rules: refusing an answerable question = INCORRECT; for unanswerable questions, a refusal mentioning a related figure clearly labeled as a different metric = CORRECT, an estimate of the requested figure = PARTIAL.
- `eval/history.jsonl`: one line per run with commit + metrics. `eval/results.json`: per-question detail for the **latest** run only (gets overwritten).
- Tests: `python3 -m pytest tests/ -v` (5 tests: Items in order, chunk size bounds, jsonl/npy row counts, no page footers).

### Known metric blind spots

- recall@5 is **Item-level**: q17 and q28 count as rank-1 hits even though the chunk with the answer detail wasn't retrieved.
- `expected_items` mixes "any one is enough" (q12) with "all are needed" (q27).
- The judge passed q17's claim that "the filing provides no further detail" as faithful.
- The judge is an LLM: verdicts can vary run to run; a one-question change (~0.017) may be noise.

## Baseline to beat — commit `8f569f9`

| recall@5 | MRR | answerable | unanswerable | faithful |
|---|---|---|---|---|
| 0.93 (28/30) | 0.92 | 0.88 | 1.00 | 36/37 |

- Retrieval misses: **q11** (CEO) and **q12** (CFO). The answer lives in Item 16's signature chunk; Item 15's exhibit list outranks it. q18 first hit at rank 2.
- Answer-level: q11, q12 INCORRECT (refused); q17, q22, q28 PARTIAL; **q23 CORRECT but unfaithful**.
- Note: unanswerable went 0.79 → 1.00 because the judge's refusal policy changed in `8f569f9`, not because finrag improved.

## Where we are

- Concept walkthrough of the whole project is complete.
- Fixes are starting, in the order in `docs/BACKLOG.md`.
- **Current item: 1 — diagnose q23** (read its `unsupported_claims`; decide: answered from memory → tighten prompt; claim actually in context → judge error; false claim → hallucination). First save the baseline per-question results: `cp eval/results.json eval/results_baseline_8f569f9.json`.
- The reranker (item 4) was designed but never added to the code.

## Other files

- `docs/BACKLOG.md` — ranked fix list (source of truth for what's next)
- `notes/INTERVIEW_QA.md` — my FDE interview Q&A bank (private; keep it updated)
- `eval/FINDINGS.md` — experiment write-ups