import type {
  HealthResponse,
  QueryRequest,
  QueryResponse,
  ReviewRecord,
  ReviewRequest,
  StageEvent,
} from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  traceId?: string;

  constructor(message: string, status: number, traceId?: string) {
    super(message);
    this.status = status;
    this.traceId = traceId;
  }
}

async function readErrorDetail(res: Response, fallback: string): Promise<ApiError> {
  try {
    const body = await res.json();
    return new ApiError(body.detail ?? fallback, res.status, body.trace_id);
  } catch {
    return new ApiError(fallback, res.status);
  }
}

export async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE_URL}/health`);
  if (!res.ok) throw await readErrorDetail(res, "Health check failed.");
  return res.json();
}

export async function runQuery(request: QueryRequest): Promise<QueryResponse> {
  const res = await fetch(`${API_BASE_URL}/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!res.ok) throw await readErrorDetail(res, "Query failed.");
  return res.json();
}

export async function fetchQueryByTraceId(traceId: string): Promise<QueryResponse> {
  const res = await fetch(`${API_BASE_URL}/query/${encodeURIComponent(traceId)}`);
  if (!res.ok) throw await readErrorDetail(res, "Lookup failed.");
  return res.json();
}

export async function submitReview(traceId: string, request: ReviewRequest): Promise<ReviewRecord> {
  const res = await fetch(`${API_BASE_URL}/query/${encodeURIComponent(traceId)}/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!res.ok) throw await readErrorDetail(res, "Review submission failed.");
  return res.json();
}

export async function fetchReviews(traceId: string): Promise<ReviewRecord[]> {
  const res = await fetch(`${API_BASE_URL}/query/${encodeURIComponent(traceId)}/reviews`);
  if (!res.ok) throw await readErrorDetail(res, "Fetching reviews failed.");
  return res.json();
}

/**
 * Streams POST /query/stream as an async generator of stage events.
 *
 * The browser's native EventSource only supports GET requests, and this
 * endpoint is POST, so SSE frames ("event: X\ndata: Y\n\n") are parsed by
 * hand off a fetch() ReadableStream reader instead.
 */
export async function* runQueryStream(
  request: QueryRequest,
  signal?: AbortSignal,
): AsyncGenerator<StageEvent> {
  const res = await fetch(`${API_BASE_URL}/query/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
    signal,
  });

  if (!res.ok || !res.body) {
    throw await readErrorDetail(res, `Stream request failed (${res.status}).`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const frame = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const event = parseFrame(frame);
      if (event) yield event;
      boundary = buffer.indexOf("\n\n");
    }
  }
}

function parseFrame(frame: string): StageEvent | null {
  let stage: string | null = null;
  let dataLine = "";
  for (const line of frame.split("\n")) {
    if (line.startsWith("event:")) stage = line.slice("event:".length).trim();
    else if (line.startsWith("data:")) dataLine += line.slice("data:".length).trim();
  }
  if (!stage || !dataLine) return null;
  return { stage, data: JSON.parse(dataLine) } as StageEvent;
}
