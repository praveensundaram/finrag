# finrag — working rules

- I'm building this to learn and to defend it in FDE interviews.
- Default to explaining concepts and tradeoffs before any code.
- Give me skeletons with TODOs; I fill in the logic. Don't write
  full implementations unless I explicitly ask.
- Running commands, reading files, and running tests/evals is fine.
- One change at a time; run evals after each and compare to
  eval/history.jsonl. Commit before running evals.
- Judge changes on overall retrieval metrics, not on fixing
  individual golden-set questions.

## Current state
- See eval/FINDINGS.md and eval/history.jsonl.
- Next up: reranker → hybrid search (BM25) → heading-aware chunker.