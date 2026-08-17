# Decision Log

## Choice of pdfplumber
Selected for reliable extraction of legal PDFs and preservation
of document structure.

## No OCR
Documents are text-based; OCR would introduce noise and errors.

## Use of requirements.txt
Chosen for simplicity, transparency, and reproducibility.

## Limited document set
Scope intentionally restricted to ensure quality and traceability
during early prototyping.

## Regulation-aware chunking, not fixed-size or page-based
Chunk boundaries follow each authority's own citable structure (CSSF
sections, DORA articles, EBA paragraphs) rather than token/character windows.
Fixed-size and semantic/ML-based chunking were both rejected as
non-deterministic and legally indefensible. See `05_chunking_strategy.md`.

## Per-regulator FAISS vector stores (segmented, not unified)
Separate `cssf` / `dora` / `eba` FAISS `IndexFlatIP` indexes over L2-normalized
`text-embedding-3-small` vectors, rather than one merged index. Prevents
cross-authority contamination and keeps normative hierarchy explicit.

## Two-phase retrieval: symbolic filter before semantic search
Authority/jurisdiction/binding-level filtering is applied before vector
search, not after. Semantic similarity is never allowed to override legal
applicability — a chunk from the wrong authority cannot surface just because
it scores well.

## GPT-5 mini for citation-bound generation, strict grounding prompt
The generation prompt forces inline `[REGULATION chunk_id / article]`
citations and an explicit "Information not available" fallback instead of
guessing, to prevent hallucinated obligations.

## LangChain used only as a Runnable wrapper, never for orchestration logic
Agents are plain async Python functions. LangChain's `RunnableLambda` is used
solely to get a uniform async-invoke interface and clean test-mocking points
(`make_chain` in `src/orchestrator/langchain_wrappers.py`). No `LLMChain`,
`ConversationBufferMemory`, `RunnableParallel`, or LangGraph — orchestration
control flow is hand-written in `MultiAgentOrchestrator` so execution order,
fail-fast behavior, and confidence fusion stay explicit and auditable.

## MLflow for per-agent lineage logging, not experiment tuning
`src/chains/step6_agent_wrappers_mlflow.py` logs each agent's input/output
payload as an MLflow artifact per run. This is used for audit trail /
reproducibility, not model comparison or hyperparameter tracking.

## Conservative confidence fusion in the orchestrator
Final confidence = `min(citation_confidence, risk_confidence)`, further
discounted 20% if the risk agent raised any warnings. The system is designed
to under-claim confidence rather than over-claim it.

## GDPR reuses DORA's parser via parameterization, not a shared base-parser class
GDPR is structurally identical to DORA (Article-based EU regulation, same
Official Journal noise format). `dora_parser.build_article_chunks` and
`dora_validate_chunks.run_validation` were parameterized (a document-metadata
dict / id-prefix argument) rather than copy-pasted into new GDPR-specific
files, since the only real duplication was in per-document metadata, not
parsing logic. A fuller `BaseParser` class hierarchy (reviving the intent
behind the archived `cssf_parser.py`) was deliberately deferred: with only
one example of the Article-based pattern (DORA/GDPR) to generalize from,
building a class hierarchy now risks guessing the wrong seams for structures
not yet seen (NIS2, MiCA). Revisit once a third Article-based source exists.

## GDPR indexed standalone, not added to the default multi-regulator fan-out
`retrieval_agent.VECTOR_STORES` and `citation_bound_answer_generation.py`'s
`regulators` dict still only list CSSF/DORA/EBA. GDPR is chunked, embedded,
and queryable via `retrieve(..., vector_store_key="gdpr")`, but joining the
live orchestrator/API default fan-out is a separate decision (it implies an
eval-baseline refresh and a frontend update) deliberately left for later
rather than bundled into the chunking/indexing work. See `docs/09`'s Phase 5
section.

## New documents for existing authorities merge into the same store, unlike GDPR
When "add more sources" means more documents for an *existing* authority
(e.g. a second CSSF circular) rather than a new authority, the new
document's chunks are concatenated into that authority's existing FAISS
store (`load_chunk_files` in `run_embeddings_retrieval.py`), not given a
separate store key the way GDPR was. This is the structurally correct
choice, not just the simpler one: GDPR's separate store was deliberately
excluded from the live default fan-out as its own decision, but "more CSSF
resources" only means something if CSSF queries actually search the new
content — so unlike GDPR, these documents are unavoidably live from the
moment they're indexed, and ship with a mandatory eval-baseline refresh
(query set size changed, so the baseline must be regenerated regardless of
whether metrics moved) rather than an optional one.

## New authority documents get their own parser only when the structure actually differs
Before writing a new parser for a second document under an existing
authority, its actual extracted text is checked against the existing
parser's regex — not assumed compatible because it's the "same authority."
Of four new CSSF/DORA/EBA documents added in one pass, only one (a DORA
RTS) was a clean drop-in reuse of the existing DORA parser; the other two
CSSF circulars each used numbering schemes distinct from Circular 20/750
and from each other, and got small dedicated parsers. Reason: `docs/09`'s
Phase 5 CSSF work found real bugs (a table-of-contents/body regex collision,
a body sentence misread as a section heading) that surfaced specifically
because the document's actual structure wasn't what the "same authority
should mean same format" assumption predicted — validating against real
extracted text before writing chunking code catches this; assuming
sameness from the authority name does not.

## NIS2 joins the live default fan-out, unlike GDPR — because the reason for picking it requires that
GDPR (a new authority) was deliberately kept out of `retrieval_agent.VECTOR_STORES`/
`citation_bound_answer_generation.py`'s `regulators` dict when it was added — see
above. NIS2 (also a new authority) was added *into* both, at the user's
explicit direction. The distinction isn't arbitrary: the roadmap's own
stated reason for recommending NIS2 first was "a good test of
cross-regulation risk detection" in `risk_assessment_agent.py` — a test
that's structurally impossible unless NIS2 and DORA are actually searched
together in the same query, i.e. unless NIS2 is live. Shipping it
standalone (GDPR's pattern) would have technically finished the roadmap
checkbox while quietly defeating the reason the checkbox existed.

## A new *live* regulator needs updating at four independent call sites — and nothing enforces that
Adding NIS2 to the live path meant updating
`retrieval_agent.VECTOR_STORES`, `citation_bound_answer_generation.py`'s
`regulators` dict, and `run_eval.py`'s `_REGULATOR_TO_STORE_KEY`, on top of
`run_embeddings_retrieval.py`'s `vector_store`/`faiss_indexes` dicts — four
separate hardcoded lists that all have to name the same set of regulators,
with no shared source of truth and no test that catches drift between them
structurally (only a test that happened to hardcode one list's *length* as
a literal, which broke the moment that length changed — see
`test_retrieval_agent_returns_documents` in `docs/09`). Not fixed here
(fixing it is a refactor, not a NIS2-shaped task), but flagged explicitly in
`docs/10` §7 as worth a single-source-of-truth registry before a fifth live
regulator makes the hand-sync burden worse.
