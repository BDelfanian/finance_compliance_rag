// Type-only import: erased at build time, so Vite never needs to serve
// client/api-types.ts (outside this app's root) over the dev server — only
// `tsc -b` reads it directly from disk during `npm run build`.
import type { components } from "../../../client/api-types";

export type Citation = components["schemas"]["Citation"];
export type AgentResultResponse = components["schemas"]["AgentResultResponse"];
export type AuditTrail = components["schemas"]["AuditTrail"];
export type TokenUsage = components["schemas"]["TokenUsage"];
export type QueryResponse = components["schemas"]["QueryResponse"];
export type QueryRequest = components["schemas"]["QueryRequest"];
export type HealthResponse = components["schemas"]["HealthResponse"];
export type ReviewRequest = components["schemas"]["ReviewRequest"];
export type ReviewRecord = components["schemas"]["ReviewRecord"];

/**
 * Raw per-stage SSE payloads from POST /query/stream. These are the
 * orchestrator's internal chain envelopes (`_run_stages` in
 * multi_agent_orchestrator.py) — not part of the OpenAPI contract, since
 * only the aggregated "final" event is shaped like QueryResponse. Shapes
 * below are taken directly from what retrieval_agent.py / citation_agent.py
 * / summarization_agent.py / risk_assessment_agent.py actually return.
 */
export interface RetrievalStageData {
  agent_result: {
    agent_name: string;
    answer: string;
    citations: string[];
    confidence: number;
    warnings: string[];
  };
  retrieved_chunks: Citation[];
}

export interface CitationStageData {
  agent_result: AgentResultResponse;
  retrieved_chunks: Citation[];
  timestamp: string;
}

export type SummarizationStageData = AgentResultResponse;
export type RiskStageData = AgentResultResponse;
export type FinalStageData = QueryResponse;

export interface StreamErrorData {
  detail: string;
  trace_id?: string;
}

export type StageEvent =
  | { stage: "retrieval"; data: RetrievalStageData }
  | { stage: "citation"; data: CitationStageData }
  | { stage: "summarization"; data: SummarizationStageData }
  | { stage: "risk_assessment"; data: RiskStageData }
  | { stage: "final"; data: FinalStageData }
  | { stage: "error"; data: StreamErrorData };
