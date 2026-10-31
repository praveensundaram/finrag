# finrag — FDE interview Q&A bank

Talking points drafted with Claude from the finrag build and restart walkthrough (Oct 2026). Practice answering in your own words; re-check numbers against `eval/history.jsonl`.

---

## Framing

**Q: Walk me through finrag in two minutes.**
Hand-built RAG over Apple's FY2025 10-K. Parse HTML into Items (sec2md), chunk (~2,000 chars), embed (voyage-finance-2), brute-force cosine top 5, and Claude answers with (Source N, Item X) citations or refuses. The differentiator is the eval harness: a 37-question golden set, recall@5/MRR, an LLM judge for correctness and faithfulness, every run logged with its git commit. Baseline at `8f569f9`: recall@5 0.93, MRR 0.92, answerable 0.88, unanswerable 1.00, faithful 36/37. Reranker is next.

**Q: Why hand-build instead of LangChain/LlamaIndex?**
To own and defend every decision. Frameworks hide exactly the parts that break at customers: parsing, chunking, evaluation. I used libraries for commodity parts (embedding API; a parser only after a bake-off). FDE angle: on an engagement you debug below the framework.

**Q: Why 10-Ks?**
Real, messy, high-stakes documents with structure (Items), tables and boilerplate, like customer enterprise docs. Answers must be exact and cited.

## Parsing HTML

**Q: What did your first parser do?**
`BeautifulSoup(html, "html.parser")`, decompose script/style tags, `soup.get_text(separator="\n")`. HTML becomes a tree of nested tags; `get_text` walks it and collects every piece of text in document order. That's all.

**Q: What does `separator="\n"` actually do?**
Puts `"\n"` between every separate text node, not just block breaks, so a sentence with an italic phrase splits across lines. Without it, neighbors glue together ("AnalysisApple") and the line boundaries the chunker relies on are lost.

**Q: Why remove script/style tags, and did it matter?**
Intent: keep CSS/JS out of the text. Tested: BeautifulSoup 4.8.2 includes their contents in `get_text`; current versions (since ~2020) skip them. Apple's 10-K has none, so the line was a no-op twice over. Lesson: verify assumptions instead of carrying folklore.

**Q: Where does styling live in SEC filings?**
Mostly style attributes on tags (`<span style="font-weight:700">`), not style tags. Attributes aren't text, so `get_text` discards them — exactly how heading information got lost.

**Q: What does flattening with `get_text` lose?**
Which lines are headings (bold gone), sentence integrity (splits at inline tags), table structure (each cell its own line, so you can't tell which number belongs to which year). It also keeps page footers like "Apple Inc. | 2025 Form 10-K | 23" in the text (53 of 120 chunks had one).

**Q: Would `get_text` work on other 10-Ks?**
It extracts words from any HTML filing, but loses structure in every one, and the leftover noise varies by company (Microsoft left bare page numbers, JPMorgan running headers, even with a dedicated parser).

## Splitting into Items

**Q: How did you split sections originally?**
A hard-coded `ITEMS` list (1 through 9A). `find_last()` runs the regex `Item\s+{re.escape(item)}\s*\.` with `finditer` and returns the start index of the LAST match (or -1), to skip the table of contents, which mentions every Item first. Sort the positions and slice each section to the next. `\s+` handles non-breaking spaces; the `\.` stops "Item 1" matching "Item 10."

**Q: What were the weaknesses?**
(1) Items missing from the list get swallowed by the previous section: the 9A bug labeled 9B–16, exhibits and signatures as 9A. (2) Case-sensitive and period-required: "ITEM 7." returns -1, so MD&A merges into Item 6 ("[Reserved]"); an all-caps filing yields zero sections. (3) A cross-reference like "Part II, Item 7." after the real heading becomes the last match and misplaces the boundary. (4) It all fails silently.

**Q: Why are wrong section labels dangerous?**
Wrong citations, and eval distortion in both directions. The 9A mislabel inflated recall (any 9A chunk counted as a hit for the CEO/CFO questions); a missed Item would deflate it. Labels are part of the eval's ground truth.

**Q: Why was a fragile first version still the right call?**
Simplest thing that worked on one document; it got the pipeline running end to end, and evals then showed exactly where it broke. Perfecting the parser before you can measure is guessing.

## Choosing a parser

**Q: What parser do you use and why?**
sec2md for parsing, my own chunker on top. Bake-off on Apple FY2024, Microsoft FY2025 and JPMorgan FY2024: found all Items 1–16 for Apple and Microsoft (JPMorgan had trouble), removed Apple's footers, kept tables as Markdown with year columns, kept headings as emphasis markers. Its own chunker ignored headings, crossed Item boundaries and used overlap by default, so I kept mine.

**Q: What alternatives exist?**
EdgarTools (broadest open-source library: Item access, XBRL financials, a ~1,200-line pattern-based section finder; works alongside sec2md). sec-api.io Extractor (paid; filings since 1994; admits ~1 in 1,000 filings with merged sections). EDGAR-CRAWLER (academic; built EDGAR-CORPUS of 10-Ks 1993–2020; can strip tables). sec-parser (semantic tree; 10-Q-focused; less active). At scale: download with EdgarTools, parse with sec2md.

**Q: Why not LlamaParse, Docling or PyMuPDF4LLM?**
They're PDF parsers that infer tables and headings from rendered page layout. EDGAR 10-Ks are HTML with real table tags and style attributes, so converting to PDF throws structure away and pays to guess it back. They're right for glossy annual-report PDFs, foreign filings, scans and slide decks. Principle: choose the parser by source format; never discard structure you already have.

**Q: How exactly does sec2md do better than `get_text` + regex?**
Reads style attributes (font-weight 700/bold → `**`, italic → `*`, plus b/strong/i/em tags; merges same-style neighbors). Converts HTML tables to Markdown tables. Splits pages using page-break CSS, which lets it detect the table of contents (first five pages, 3+ Item rows, dot leaders or table Item cells) and skip it, and strip footers and lone page numbers. Its Item regex is case-insensitive, start-of-line only, flexible on punctuation, and ignores matches preceded by "Part II" and page-top breadcrumbs. Skips `display:none` content.

**Q: What does "walks forward instead of searching a fixed list" mean?**
The old parser asked "where is Item 7?" for each list entry, so unlisted Items never got a boundary. sec2md reads top to bottom and asks "what heading is this?": every heading closes the current section and opens a new one labeled from the text itself. Its built-in map of which Items belong in which Part is used afterward to check and drop misfits, not to find.

**Q: Does sec2md use the table of contents' page numbers?**
No, it only detects and skips the TOC; boundaries come from body headings. Page numbers are too coarse (several short Items share one page) and printed numbers don't map cleanly to HTML page order (unnumbered cover/TOC). Better use of the TOC: a per-filing checklist of which Items should exist.

**Q: What are sec2md's limits?**
Still heuristics. The footer rule fits "Company | Year Form 10-K | Page" shapes (JPMorgan's headers slipped through); the TOC check only looks at the first five pages; bold markers get stripped from heading lines in section output; only weight 700/bold counts as bold. On a fake 10-K with planted traps (all-caps heading, cross-reference, unlisted 9B, footers, a table), the old parser got almost every boundary wrong silently; sec2md got all five sections right.

## Robustness across companies and years

**Q: How would you make ingestion reliable across many 10-Ks?**
No parser is perfect, so make failures loud. (1) A dedicated parser. (2) Build-time validation per filing: expected Items present and in order, section sizes sane (a 40,000-char "[Reserved]" Item 6 means something was swallowed), little unassigned text; quarantine failing filings instead of indexing wrong labels. (3) Evals on a sample of companies and years. Optionally cross-check two parsers (sec2md vs EdgarTools) and hand-check where they disagree.

**Q: Why do filing years matter?**
The Item list changed: Item 16 added 2016; Item 6 became "[Reserved]" 2021; 9C added 2021–22; 1C Cybersecurity for fiscal years ending after mid-December 2023. A hard-coded "all 23 Items" check fails older filings, so validation must be year-aware or use the filing's own TOC. Formatting drifts too (filing software changes; pre-2000s filings are plain text).

## Chunking

**Q: Why chunk, and how big?**
One vector per passage. Too big averages many topics (Item 1A is 68,000 chars of mixed risks) and floods the prompt; too small loses context ("this increased 6%"). `CHUNK_TARGET` 2,000 chars (~500 tokens), `CHUNK_MIN` 200.

**Q: How does your packer work?**
Greedy, in order, never cutting a piece: keep adding pieces until the next won't fit (counting the +1 for the `"\n"` join), seal, start a new chunk; flush the leftover; merge-back glues a final runt under the minimum onto the previous chunk, so chunks can reach TARGET + MIN (test bound 2,200).

**Q: What chunking bugs did you hit?**
Paragraphs over 2,000 chars passed through whole, because the packer accepts any piece into an empty chunk (Item 1A had a 3,647-char chunk), so I added `split_paragraph`. Off-by-one: the join `"\n"` wasn't counted, giving three 2,001-char chunks; tests caught it. A 2,086-char chunk was legitimate merge-back, so the bound became TARGET + MIN with a comment.

**Q: How do you split oversized paragraphs?**
`re.split(r"(?<=[.!?])\s+")`: the lookbehind cuts after sentence punctuation while keeping it attached. Then reuse `pack()` on the sentences. Abbreviations like "U.S." mis-split, but repacking glues them back unless that spot lands on a chunk boundary. `extend` (not `append`) adds the pieces as individual units.

**Q: Why both merge-back and a final minimum filter?**
Different jobs. Merge-back rescues a short tail that has a neighbor; the filter drops orphans with no neighbor (Item 1B's entire text is "None.": one chunk, so merge-back's `len(chunks) > 1` check fails, and merging across Items would mislabel it). Tradeoff: dropping "None." loses a real fact, so "Does Apple have unresolved SEC staff comments?" can't be answered; a fix would keep short chunks that are a whole section, prefixed with the Item title. 120 chunks across 14 sections originally; 128 after sec2md.

**Q: What are greedy chunking's weaknesses?**
Boundaries fall where size runs out, not where topics change: q17's Epic appeal answer landed in a chunk that never says "Epic." Also ragged last chunks, double-packing, rare oversized sentences, and since sec2md writes table rows as lines, a big table can split and later chunks lose the header row. Fix direction: heading-aware chunking with breadcrumbs.

**Q: Did you try chunk overlap?**
300-char overlap: q17's chunk still missed the top 10 and MRR fell 0.97 → 0.92, so I reverted. Reaching "Epic" would need overlap of nearly the whole previous chunk, diluting every chunk.

**Q: How does your chunking compare to best practices?**
Holds up: ~500-token chunks sit in the commonly validated range; paragraph→sentence packing is a hand-rolled recursive splitter (Chroma found recursive splitting strong when tuned); no overlap is backed by Chroma's results and my own eval (overlap is contested: NVIDIA found 15% best on FinanceBench at 1,024 tokens); semantic chunking skipped, consistent with Vectara's finding that it rarely justifies its cost; chunks never cross Items. Falls short: ignores subheadings within Items (Unstructured's element-based chunking beat fixed splits on SEC filings), chunks carry no context (Anthropic's Contextual Retrieval: ~35% fewer retrieval failures, ~49% with BM25, ~67% with reranking), tables aren't treated as units, chunk size never swept on my eval. A context prefix applied to every chunk is a general technique, so it passes my no-overfitting rule even though the q11/q12 one-off didn't. Lesson: read primary sources; blog summaries misquote Chroma as favoring 10–20% overlap.

## Embeddings, storage, retrieval

**Q: Which embedding model and how?**
voyage-finance-2 (finance-tuned, 1,024 dims, normalized); `input_type="document"` for chunks and `"query"` for questions (asymmetric retrieval). Vectors from different models can't be mixed: switching models means re-embedding everything.

**Q: How is the index stored?**
`chunks.jsonl` (item, chunk_index, text) + `vectors.npy`, linked by row order, an invariant checked by a row-count test. Built once and loaded from disk; delete `data/processed` to rebuild after chunking changes. Known weakness: a row-count check can't catch reordering; fix is matching chunk IDs on both sides plus a manifest.

**Q: Why no vector database?**
~128 vectors: brute-force cosine (normalized matrix @ query, argsort) is exact and instant, while a vector DB adds infrastructure and usually approximate (ANN) search that can miss true nearest neighbors. Switch triggers: corpus large enough that brute force gets slow or memory-heavy; metadata filtering (company, year, Item) once there are many filings; incremental updates/deletes; multiple services or users sharing the index. A DB also stores vector, text and metadata as one record, fixing my row-order weakness. Search sits behind one `search()` function, so swapping in Chroma, LanceDB or pgvector is a contained change.

**Q: Why do you need several metrics instead of one?**
Thought experiment: drop the `[::-1]` in search so it returns the 5 WORST chunks. No error is raised. Refusal accuracy stays near perfect (finrag correctly refuses when context is irrelevant) and faithfulness stays high (it's faithful to the useless context), but recall@5 and answerable accuracy collapse. Each metric covers a different failure; looking at only one can hide a broken system.

**Q: Tell me about a tricky bug.**
The NumPy matmul raised divide-by-zero, overflow and invalid-value warnings. I ruled out every data cause (empty chunks or queries, zero/NaN/inf vectors), concluded it was a benign macOS Accelerate BLAS artifact, and scoped `np.errstate` around just that matmul instead of silencing warnings globally.

## Generation

**Q: How do you keep answers grounded?**
System prompt: use only the provided context, cite (Source N, Item X), say when the answer isn't there. Validated synthesis across chunks, grounding under training-data temptation (CEO name taken from the signature block, not memory), refusing the unknowable (current stock price) and the absent (hiring in China).

**Q: Was q17 a retrieval or a generation failure?**
Mainly retrieval (the chunk with the stay denial and October oral arguments wasn't in the top 5), plus a subtle generation failure: Claude said "the filing provides no further detail," a claim about the whole filing when it only saw 5 chunks. That overclaim tells a user to stop looking for information that exists. The judge marked it faithful too — a judge blind spot. Fix: claim only what the system knows (what it checked, not what the filing lacks), in the user's language rather than RAG jargon: "I couldn't find more on this in the sections I reviewed (Item 3, Legal Proceedings); it may appear elsewhere in the filing." Longer term: if the answer looks incomplete, retrieve more before answering. FDE angle: design wording for the actual user (an analyst), not for engineers.

**Q: What's your refusal policy?**
A refusal may mention a related figure clearly labeled as a different metric; estimating the requested figure scores PARTIAL; the prompt forbids estimates built on unstated assumptions (q09 kept citing buyback prices when asked the current stock price).

## Evaluation

**Q: How do you evaluate finrag?**
Golden set (id, question, type, expected_items, reference_answer), 37 questions (30 answerable, 7 unanswerable). `eval.recall`: recall@5 and MRR, fast with no LLM. `eval.score`: Claude judge returns CORRECT/PARTIAL/INCORRECT (1/0.5/0) plus faithfulness and unsupported_claims; answerable and refusal accuracy reported separately; unparseable judge output is ERROR and excluded.

**Q: Why both recall@5 and MRR?**
recall@5 was 1.00 at the original baseline, and a metric at its ceiling can't show improvement. MRR captures rank (q18's first hit at rank 2), and per-question scores show which question moved. Overlap left recall unchanged but dropped MRR 0.97 → 0.92.

**Q: Is your "recall@5" really recall?**
Strictly it's hit rate@5 (success@5): 1 if ANY top-5 chunk comes from ANY expected Item. True recall@k is the fraction of all relevant items retrieved, so a question needing Items 1A, 1 and 8 that only gets 1A chunks scores a full hit under my metric but 1/3 under true recall. MRR (mean of 1/rank of first hit): 27 questions at rank 1, q18 at rank 2, q11/q12 missed → 27.5/30 = 0.92. Retrieval metrics run without an LLM, so they're fast, cheap and deterministic.

**Q: What does recall@5 hide?**
It's Item-level, so any chunk from the right Item counts as a hit. q17 and q28 score as rank-1 hits while their answers come back PARTIAL because the specific chunk with the detail wasn't retrieved. A chunk-level or answer-span check would expose that.

**Q: What LLM-as-judge pitfalls did you hit?**
q03: the judge said CORRECT though finrag claimed iPhone had the largest dollar increase (Services did, ~$13.0B vs ~$8.4B), because the reference didn't mention it; fix was giving the judge the retrieved context and returning `faithful` + `unsupported_claims`. Judge JSON got truncated (thinking counted toward a 500-token limit), fixed with 2,000 + a `stop_reason` check. The judge called a refusal on an answerable question CORRECT; rule changed to INCORRECT. Judge self-tests became named PASS/FAIL cases. General pitfalls: run-to-run noise, leniency toward familiar style, preferring longer answers — comparing against a fixed reference reduces the last two.

**Q: Why exclude judge ERRORs instead of counting them INCORRECT?**
An ERROR is a failure of the measuring tool, not of finrag. Counting it INCORRECT would blame finrag for the judge's bug and hide the judge problem. Report errors separately; if any occur, fix and rerun before trusting the scores.

**Q: Correct vs faithful — what's the difference?**
Correctness compares the answer to the reference; faithfulness checks every claim against the retrieved context. Four boxes: correct+faithful (goal); correct+unfaithful (q23 — right but not from the context, likely training memory); incorrect+faithful (q11 — honest report of bad retrieval, so look at retrieval); incorrect+unfaithful (hallucination). Watching both matters: loosening the grounding rule could flip q11/q12 to CORRECT from memory, raising answerable accuracy while making the system less trustworthy.

**Q: How do you keep eval numbers trustworthy?**
Commit before running evals; `history.jsonl` logs commit + metrics for every run; findings in `FINDINGS.md`; one change at a time. Grew the golden set with `random.seed(42)` chunk sampling (Claude drafted, I verified against the filing) plus new unanswerable traps (smartphone market-share %, Vision Pro revenue) to reduce selection bias. With 30 answerable questions the smallest score step is ~0.017 (one PARTIAL flip), which can be judge noise, so check which questions moved.

**Q: Your scores dropped after switching parsers. Why?**
sec2md run: recall 0.87, MRR 0.83, almost entirely q11/q12 (CEO/CFO). The answer now lives in Item 16's signature chunk, a short names table diluted by boilerplate, with Item 15's exhibit list ("Certification of Chief Executive Officer") competing. The old 1.00 was inflated by the 9A mislabel. Lower but honest beats high but wrong.

**Q: Refusal accuracy jumped from 0.79 to 1.00. Did finrag get better?**
No: the judge's refusal policy changed (labeled related figures now count as CORRECT), so the measuring stick moved, not the system. Always attribute a score change to code vs rules vs data before claiming improvement. Fresh baseline at `8f569f9`: answerable 0.88 (q11/q12 INCORRECT; q17, q22, q28 PARTIAL), unanswerable 1.00, faithful 36/37 (q23).

## Improvement decisions

**Q: How do you decide what to fix?**
Judge changes by overall retrieval impact, not by rescuing one test. I rejected patching sec2md internals to keep bold markers for q11/q12 as overfitting; isolating the signature table or adding LLM-written descriptions helped but were targeted patches, set aside. Order: judge fix → larger golden set → reranker → hybrid search (BM25) → heading-aware chunker.

**Q: How does a reranker differ from embedding search, and what can't it fix?**
Embedding search (bi-encoder) embeds question and chunk separately (chunks at build time) and compares them with one dot product, so it measures topic similarity. A cross-encoder reranker joins question + chunk into one input; attention runs across both texts in every layer, so it judges whether the chunk *answers* the question (it can see "Who" needs a name and "Timothy D. Cook" sits next to "Chief Executive Officer," while the exhibit list only mentions the role). It's accurate but can't be precomputed, so it only re-scores a candidate pool (top 30 → top 5). Limit: it can only reorder, not find. If the answer chunk isn't in the top 30, stage 1 has to improve (better chunks, hybrid BM25 to widen the pool); stage-1 recall@30 caps everything after it.

**Q: How did you refactor safely?**
Split `explore.py` into a `finrag/` package (config, clients, parse, chunk, index, retrieve, generate) plus `build.py`/`ask.py`; verified identical scores before any behavior change (so later score changes could be attributed cleanly); added tests (Items in order, chunk bounds, jsonl/npy row match, no footers). The stable `{item, text}` interface later let me swap in sec2md without touching anything downstream.

## FDE-style generalization

**Q: A customer has tens of thousands of contracts as PDFs. What changes from finrag?**
Discovery on document variety first; parser chosen by format (layout-aware PDF parsing, OCR for scans); build-time validation with quarantine; eval samples per document type, ideally seeded with real user questions; a vector database with metadata filtering at that scale; reranking; explicit cost and latency budgets. Same principles: keep structure, make failures loud, measure every change.