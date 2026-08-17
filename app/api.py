"""
FastAPI service — thin HTTP layer over `MultiAgentOrchestrator`
(roadmap §3.4 / Phase 3).

Deliberately does not add any orchestration, retrieval, or generation logic
of its own: every request maps directly onto
`src.orchestrator.multi_agent_orchestrator.MultiAgentOrchestrator`, which is
now also the chain path the live Streamlit UI's future replacement will use
(see the module docstring in `multi_agent_orchestrator.py` for why the
orchestrator was switched onto the MLflow-wrapped chains as part of this
change) — this API and the UI are two callers of one orchestration path, not
two independent ones.

Run locally:
    uvicorn app.api:app --reload --port 8000

Endpoints:
    POST /query          — full orchestrated run, returns the final result
    POST /query/stream    — same run, but Server-Sent Events, one event per
                            agent stage (retrieval/citation/summarization/
                            risk_assessment/final), for progressive UI
                            rendering instead of one long spinner
    GET  /query/{trace_id} — look up a previously completed run's full
                            result by trace_id (audit lookup)
    GET  /health          — liveness/config check
"""

import json
from datetime import datetime, timezone
from typing import AsyncIterator, List

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.schemas import (
    ErrorResponse,
    HealthResponse,
    QueryRequest,
    QueryResponse,
    ReviewRecord,
    ReviewRequest,
)
from src.config import get_settings
from src.observability import audit_store, review_store
from src.observability.logging_config import get_logger, new_trace_id
from src.orchestrator.multi_agent_orchestrator import MultiAgentOrchestrator

settings = get_settings()
logger = get_logger(__name__)

app = FastAPI(
    title="Finance Compliance RAG API",
    description=(
        "Retrieval-grounded, multi-agent compliance answers over CSSF, DORA, "
        "EBA, and NIS2 regulatory text. Advisory only — not legal advice; every "
        "answer stays traceable to a cited source chunk."
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.api_cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        model_version=settings.model_version,
        llm_model=settings.llm_model,
        mlflow_tracking_uri=settings.mlflow_tracking_uri,
    )


@app.post(
    "/query",
    response_model=QueryResponse,
    responses={502: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def run_query(request: QueryRequest) -> QueryResponse:
    trace_id = new_trace_id()
    orchestrator = MultiAgentOrchestrator(model_version=request.model_version or settings.model_version)
    try:
        result = await orchestrator.run(request.query, trace_id=trace_id)
    except (RuntimeError, ValueError) as exc:
        # Fail-fast from the orchestrator (RuntimeError: empty retrieval, no
        # citation answer) or from an agent itself (ValueError:
        # retrieval_agent raises this directly when nothing clears the
        # similarity threshold — e.g. an out-of-domain query — rather than
        # returning a falsy result for the orchestrator's own check to
        # catch, so that check alone doesn't cover this in practice). Either
        # way this is a well-formed request the pipeline couldn't service,
        # not a server bug. 502: this API is a gateway in front of the agent
        # pipeline, and the pipeline is what failed.
        logger.warning("query failed (fail-fast)", extra={"trace_id": trace_id, "error": str(exc)})
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.error("query failed (unexpected)", extra={"trace_id": trace_id}, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error processing query.",
        ) from exc

    audit_store.save_audit_record(trace_id, result)
    return QueryResponse.model_validate(result)


@app.post("/query/stream")
async def run_query_stream(request: QueryRequest) -> StreamingResponse:
    trace_id = new_trace_id()
    orchestrator = MultiAgentOrchestrator(model_version=request.model_version or settings.model_version)

    async def event_source() -> AsyncIterator[str]:
        try:
            async for event in orchestrator.run_events(request.query, trace_id=trace_id):
                if event["stage"] == "final":
                    audit_store.save_audit_record(trace_id, event["data"])
                yield f"event: {event['stage']}\ndata: {json.dumps(event['data'], default=str)}\n\n"
        except (RuntimeError, ValueError) as exc:
            logger.warning("query failed (fail-fast)", extra={"trace_id": trace_id, "error": str(exc)})
            yield f"event: error\ndata: {json.dumps({'detail': str(exc), 'trace_id': trace_id})}\n\n"
        except Exception:
            logger.error("query failed (unexpected)", extra={"trace_id": trace_id}, exc_info=True)
            yield (
                "event: error\n"
                f"data: {json.dumps({'detail': 'Internal error processing query.', 'trace_id': trace_id})}\n\n"
            )

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={"X-Trace-Id": trace_id, "Cache-Control": "no-cache"},
    )


@app.get(
    "/query/{trace_id}",
    response_model=QueryResponse,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def get_query(trace_id: str) -> QueryResponse:
    if not audit_store.TRACE_ID_RE.match(trace_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Malformed trace_id.")

    record = audit_store.load_audit_record(trace_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No run found for this trace_id.")
    return QueryResponse.model_validate(record)


@app.post(
    "/query/{trace_id}/review",
    response_model=ReviewRecord,
    status_code=status.HTTP_201_CREATED,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def submit_review(trace_id: str, request: ReviewRequest) -> ReviewRecord:
    """Human-in-the-loop approve/reject/annotate action (roadmap §3.6) — can
    only be filed against a trace_id that actually completed a run, so a
    typo'd trace_id can't silently create an orphan review record."""
    if not audit_store.TRACE_ID_RE.match(trace_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Malformed trace_id.")

    if audit_store.load_audit_record(trace_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No run found for this trace_id.")

    record = ReviewRecord(
        trace_id=trace_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        **request.model_dump(),
    )
    review_store.append_review(trace_id, record.model_dump())
    logger.info(
        "review submitted",
        extra={"trace_id": trace_id, "decision": record.decision, "reviewer": record.reviewer_name},
    )
    return record


@app.get(
    "/query/{trace_id}/reviews",
    response_model=List[ReviewRecord],
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def get_reviews(trace_id: str) -> List[ReviewRecord]:
    if not audit_store.TRACE_ID_RE.match(trace_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Malformed trace_id.")

    if audit_store.load_audit_record(trace_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No run found for this trace_id.")

    return [ReviewRecord.model_validate(r) for r in review_store.load_reviews(trace_id)]
