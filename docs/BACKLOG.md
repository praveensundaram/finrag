# finrag — ranked fix list

One change at a time, each measured against the baseline (commit `8f569f9`: recall@5 0.93, MRR 0.92, answerable 0.88, unanswerable 1.00, faithful 36/37). Commit before every eval run. Check items off as they're done and note the result.

## Diagnosis and measurement (do first)

- [x] **0. Housekeeping:** rename `claude.md` → `CLAUDE.md` and commit it. Also: `backlog.md` → `BACKLOG.md`, Q&A bank moved to gitignored `notes/`, baseline per-question results saved as `eval/results_baseline_8f569f9.json`.
- [ ] **1. Diagnose q23** (CORRECT but unfaithful): read `unsupported_claims` in `eval/results.json`. Answered from memory → tighten the grounding prompt. Claim is actually in the context → judge error. Claim is false → hallucination.
- [ ] **1b. Fix gap wording in `SYSTEM_PROMPT`:** when details are missing, use plain, hedged, user-facing wording that names what was checked, e.g. *"I couldn't find more on this in the sections I reviewed (Item 3, Legal Proceedings); it may appear elsewhere in the filing."* Never "the filing doesn't say," and no RAG jargon like "excerpts" (end users don't know about retrieval). Context: q17 claimed the filing had no further detail when the detail sat in an unretrieved chunk, and the judge still marked it faithful. Optional later: when an answer looks incomplete, automatically retrieve more (bigger k or neighboring chunks) before answering.
- [ ] **2. Diagnose q22 and q28** (PARTIAL): were the quarterly dividend rate / the $23.2B and $10.6B figures in the retrieved chunks? Decides retrieval problem vs generation problem.
- [ ] **3. Chunk-level retrieval check:** add an evidence string per golden question; hit if it appears in a retrieved chunk. Item-level recall@5 hides the q17/q28 misses, so later chunking fixes can't be measured without this. Also record per question whether `expected_items` means "any one is enough" (q12: CFO name in 9B or 16) or "all are needed" (q27: 1A, 1 and 8), so multi-Item questions get hit rate or true recall as appropriate.

## Improvements (most general first)

- [ ] **4. Reranker experiment:** Voyage `rerank-2.5` over the top 30 embedding candidates → top 5. `USE_RERANKER`, `RERANK_MODEL`, `RERANK_CANDIDATES` in `config.py`; skeleton with TODOs. First check stage-1 recall@30 for q11, q12, q17, q28 (is the answer chunk in the pool at all? a reranker can only reorder, not find). At 128 chunks, reranking all of them is a useful comparison. Measure `eval.recall` with the flag on vs off, then one `eval.score`. Never applied to code yet.
- [ ] **5. Heading-aware chunking (Step B):** start a new chunk at each subheading from sec2md; prefix every chunk with a breadcrumb (company, year, Item, subheading) before embedding. Targets q17 and q11/q12.
- [ ] **6. Tables as units:** keep each table whole as its own chunk, or repeat the header row when one must be split (rows currently pack as lines, so later pieces lose the year headers).
- [ ] **7. Keep whole-section short chunks** (Item 1B "None.") instead of dropping them, prefixed with the Item title.
- [ ] **8. Chunk size sweep:** 1,000 / 2,000 / 4,000 chars.
- [ ] **9. Hybrid search (BM25)** only if exact-term lookups still fail after 4–5. Widens the candidate pool for the reranker.
- [ ] **10. Optional:** full Contextual Retrieval (LLM-written context per chunk, with prompt caching), or Voyage's contextualized chunk embeddings endpoint. Possibly compare a newer Voyage model (e.g. voyage-4 family) against voyage-finance-2 — requires re-embedding everything.

## Robustness and polish

- [ ] **11. Answer truncation:** raise or handle `max_tokens=1024`.
- [ ] **11b. Manifest** next to the vectors (embedding model, chunk settings, commit), checked at load, so a model or chunking change forces a rebuild instead of silently mixing incompatible vectors.
- [ ] **11c. Chunk IDs on BOTH sides** (Praveen's idea): a `chunk_id` in `chunks.jsonl` (Item + index + short text hash) and the same IDs saved with the vectors (`np.savez` with ids + vectors, or an ids file); assert the ID lists match at load. Guarantees alignment instead of trusting row order. An ID in only one file wouldn't help.
- [ ] **12. Measure judge noise:** run `eval.score` twice on the same commit before trusting small differences.
- [ ] **13. Faster `eval.score`:** parallel calls; a `--rejudge` mode that re-grades saved answers.
- [ ] **13b. Harden the history log:** record a "dirty" flag when there are uncommitted changes (`git status --porcelain`); save each run's per-question results to its own file (commit + timestamp) instead of overwriting `eval/results.json`, so runs can be diffed per question.
- [ ] **14. Build-time section validation** (expected Items present and ordered, section-size sanity, little unassigned text) — only if finrag expands beyond one filing. Same trigger for moving to a vector store with metadata filtering (Chroma, LanceDB, pgvector). Recommendation for now: keep brute-force NumPy while finrag covers one filing (not yet decided).