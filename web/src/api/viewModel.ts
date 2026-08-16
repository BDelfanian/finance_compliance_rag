import type { AuditTrail, Citation, QueryResponse } from "./types";
import type { RunState } from "../hooks/useQueryRun";

/**
 * Normalizes both a live streaming RunState and a fully-formed QueryResponse
 * (from history or a GET /query/{trace_id} lookup) into one shape ResultView
 * can render without caring which source it came from.
 */
export interface ResultViewModel {
  status: "idle" | "running" | "done" | "error";
  retrievedCount?: number;
  answer?: { text: string; confidence: number };
  sources: Citation[];
  citedChunkIds: Set<string>;
  summary?: { text: string };
  risk?: { warnings: string[]; confidence: number };
  confidence?: number;
  auditTrail?: AuditTrail;
  error?: string;
}

function chunkIdSet(citations: Citation[]): Set<string> {
  return new Set(citations.map((c) => c.chunk_id).filter((id): id is string => Boolean(id)));
}

export function viewModelFromQueryResponse(qr: QueryResponse): ResultViewModel {
  return {
    status: "done",
    answer: { text: qr.answer.answer, confidence: qr.answer.confidence },
    sources: qr.sources,
    citedChunkIds: chunkIdSet(qr.answer.citations),
    summary: { text: qr.summary.answer },
    risk: { warnings: qr.risk.warnings, confidence: qr.risk.confidence },
    confidence: qr.confidence,
    auditTrail: qr.audit_trail,
  };
}

export function viewModelFromRunState(state: RunState): ResultViewModel {
  if (state.final) return viewModelFromQueryResponse(state.final);

  return {
    status: state.status,
    retrievedCount: state.retrieval?.retrieved_chunks.length,
    answer: state.citation
      ? { text: state.citation.agent_result.answer, confidence: state.citation.agent_result.confidence }
      : undefined,
    sources: state.citation?.retrieved_chunks ?? [],
    citedChunkIds: chunkIdSet(state.citation?.agent_result.citations ?? []),
    summary: state.summary ? { text: state.summary.answer } : undefined,
    risk: state.risk ? { warnings: state.risk.warnings, confidence: state.risk.confidence } : undefined,
    error: state.error,
  };
}
