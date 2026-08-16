import { useState, type FormEvent } from "react";
import { ConfidenceBadge } from "./ConfidenceBadge";

export interface HistoryEntry {
  traceId: string;
  query: string;
  timestamp: string;
  confidence: number;
}

interface HistorySidebarProps {
  history: HistoryEntry[];
  selectedTraceId?: string;
  onSelect: (traceId: string) => void;
  onClear: () => void;
  lookupError?: string;
}

// Session history (like step6_read_only_ui.py's sidebar) plus a trace_id
// lookup backed by GET /query/{trace_id}, for audit records outside this
// browser session (e.g. a trace_id shared by someone else, or after reload).
export function HistorySidebar({ history, selectedTraceId, onSelect, onClear, lookupError }: HistorySidebarProps) {
  const [lookupInput, setLookupInput] = useState("");

  function handleLookupSubmit(e: FormEvent) {
    e.preventDefault();
    const trimmed = lookupInput.trim();
    if (trimmed) onSelect(trimmed);
  }

  return (
    <div className="history-sidebar">
      <h2>Query History</h2>
      {history.length === 0 ? (
        <p className="muted">No queries yet this session.</p>
      ) : (
        <ul className="history-list">
          {history.map((entry) => (
            <li key={entry.traceId}>
              <button
                type="button"
                className={`history-list__item ${entry.traceId === selectedTraceId ? "is-active" : ""}`}
                onClick={() => onSelect(entry.traceId)}
              >
                <span className="history-list__query">
                  {entry.query.length > 60 ? `${entry.query.slice(0, 60)}…` : entry.query}
                </span>
                <ConfidenceBadge score={entry.confidence} />
              </button>
            </li>
          ))}
        </ul>
      )}
      {history.length > 0 && (
        <button type="button" className="history-clear" onClick={onClear}>
          Clear history
        </button>
      )}

      <hr />

      <h3>Look up by trace ID</h3>
      <form className="lookup-form" onSubmit={handleLookupSubmit}>
        <input
          type="text"
          placeholder="32-character trace id"
          value={lookupInput}
          onChange={(e) => setLookupInput(e.target.value)}
        />
        <button type="submit">Look up</button>
      </form>
      {lookupError && <p className="error-text">{lookupError}</p>}
    </div>
  );
}
