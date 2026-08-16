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
