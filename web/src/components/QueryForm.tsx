import { useState, type FormEvent } from "react";

interface QueryFormProps {
  onSubmit: (query: string) => void;
  disabled: boolean;
}

// The API currently has no per-regulator filter (QueryRequest is just
// {query, model_version}) — retrieval_agent.py always searches all three
// vector stores. This lists them as informational context (mirroring
// ui_rag_full_advanced.py's regulator multiselect in spirit) rather than
// offering a filter control the backend can't honor yet.
const REGULATORS = ["CSSF", "DORA", "EBA"];

export function QueryForm({ onSubmit, disabled }: QueryFormProps) {
  const [query, setQuery] = useState("");

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const trimmed = query.trim();
    if (!trimmed || disabled) return;
    onSubmit(trimmed);
  }

  return (
    <form className="query-form" onSubmit={handleSubmit}>
      <label htmlFor="query-input">Regulatory query</label>
      <textarea
        id="query-input"
        rows={4}
        placeholder="e.g. What are the management body's responsibilities for ICT risk governance under CSSF, DORA, and EBA?"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        disabled={disabled}
      />
      <div className="query-form__footer">
        <div className="query-form__regulators">
          Searches together:{" "}
          {REGULATORS.map((r) => (
            <span key={r} className="regulator-chip">
              {r}
            </span>
          ))}
        </div>
        <button type="submit" disabled={disabled || !query.trim()}>
          {disabled ? "Running…" : "Submit"}
        </button>
      </div>
    </form>
  );
}
