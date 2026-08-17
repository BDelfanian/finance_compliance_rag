import { useCallback, useState } from "react";
import "./App.css";
import { ApiError, fetchQueryByTraceId } from "./api/client";
import type { QueryResponse } from "./api/types";
import { viewModelFromQueryResponse, viewModelFromRunState } from "./api/viewModel";
import { HistorySidebar, type HistoryEntry } from "./components/HistorySidebar";
import { QueryForm } from "./components/QueryForm";
import { ResultView } from "./components/ResultView";
import { StageTimeline } from "./components/StageTimeline";
import { useQueryRun } from "./hooks/useQueryRun";

export default function App() {
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [selected, setSelected] = useState<QueryResponse | null>(null);
  const [lookupError, setLookupError] = useState<string | undefined>();

  const { state, submit } = useQueryRun((final) => {
    setHistory((prev) => [
      {
        traceId: final.audit_trail.trace_id,
        query: final.audit_trail.query,
        timestamp: final.audit_trail.timestamp,
        confidence: final.confidence,
      },
      ...prev,
    ]);
  });

  const handleSubmit = useCallback(
    (query: string) => {
      setSelected(null);
      setLookupError(undefined);
      submit(query);
    },
    [submit],
  );

  const handleSelectHistory = useCallback(async (traceId: string) => {
    setLookupError(undefined);
    try {
      const result = await fetchQueryByTraceId(traceId);
      setSelected(result);
    } catch (err) {
      setLookupError(err instanceof ApiError ? err.message : "Lookup failed.");
    }
  }, []);

  const handleClearHistory = useCallback(() => {
    setHistory([]);
    setSelected(null);
  }, []);

  const isRunning = state.status === "running";
  const vm = selected ? viewModelFromQueryResponse(selected) : viewModelFromRunState(state);
  const activeTraceId = selected?.audit_trail.trace_id ?? state.final?.audit_trail.trace_id;
  const showTimeline = !selected && (isRunning || state.status === "done" || state.status === "error");

  return (
    <div className="app-shell">
      <header className="app-header">
        <h1>Finance Compliance RAG</h1>
        <p className="app-subtitle">
          Retrieval-grounded answers over CSSF, DORA, EBA, and NIS2 regulatory text.{" "}
          <strong>Advisory only — not legal advice.</strong> Every statement stays traceable to a cited
          source below; review before acting on it.
        </p>
      </header>

      <div className="app-body">
        <main className="app-main">
          <QueryForm onSubmit={handleSubmit} disabled={isRunning} />
          {showTimeline && <StageTimeline state={state} />}
          <ResultView vm={vm} />
        </main>

        <aside className="app-sidebar">
          <HistorySidebar
            history={history}
            selectedTraceId={activeTraceId}
            onSelect={handleSelectHistory}
            onClear={handleClearHistory}
            lookupError={lookupError}
          />
        </aside>
      </div>
    </div>
  );
}
