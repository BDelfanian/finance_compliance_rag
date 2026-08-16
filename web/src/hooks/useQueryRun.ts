import { useCallback, useRef, useState } from "react";
import { ApiError, runQueryStream } from "../api/client";
import type {
  CitationStageData,
  FinalStageData,
  RetrievalStageData,
  RiskStageData,
  StageEvent,
  SummarizationStageData,
} from "../api/types";

export interface RunState {
  status: "idle" | "running" | "done" | "error";
  query?: string;
  retrieval?: RetrievalStageData;
  citation?: CitationStageData;
  summary?: SummarizationStageData;
  risk?: RiskStageData;
  final?: FinalStageData;
  error?: string;
}

const INITIAL_STATE: RunState = { status: "idle" };

/**
 * Drives POST /query/stream and exposes one RunState that fills in as each
 * SSE stage arrives (retrieval -> citation -> summarization -> risk_assessment
 * -> final), so the UI can render progressively instead of behind one long
 * spinner.
 */
export function useQueryRun(onComplete?: (final: FinalStageData) => void) {
  const [state, setState] = useState<RunState>(INITIAL_STATE);
  const abortRef = useRef<AbortController | null>(null);

  const submit = useCallback(
    async (query: string, modelVersion?: string) => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      setState({ status: "running", query });

      try {
        for await (const event of runQueryStream(
          { query, model_version: modelVersion || undefined },
          controller.signal,
        )) {
          applyEvent(event);
        }
      } catch (err) {
        if (controller.signal.aborted) return;
        const message = err instanceof ApiError ? err.message : "Unexpected error contacting the API.";
        setState((prev) => ({ ...prev, status: "error", error: message }));
      }

      function applyEvent(event: StageEvent) {
        switch (event.stage) {
          case "retrieval":
            setState((prev) => ({ ...prev, retrieval: event.data }));
            break;
          case "citation":
            setState((prev) => ({ ...prev, citation: event.data }));
            break;
          case "summarization":
            setState((prev) => ({ ...prev, summary: event.data }));
            break;
          case "risk_assessment":
            setState((prev) => ({ ...prev, risk: event.data }));
            break;
          case "final":
            setState((prev) => ({ ...prev, status: "done", final: event.data }));
            onComplete?.(event.data);
            break;
          case "error":
            setState((prev) => ({ ...prev, status: "error", error: event.data.detail }));
            break;
        }
      }
    },
    [onComplete],
  );

  const reset = useCallback(() => {
    abortRef.current?.abort();
    setState(INITIAL_STATE);
  }, []);

  return { state, submit, reset };
}
