import { useState, type ChangeEvent, type FormEvent } from "react";

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

// Each of these was confirmed live against the real FAISS indexes (see
// docs/09) to retrieve strong, relevant chunks — not just plausible-sounding
// questions. Picked to span all three live-searched regulators plus one
// cross-regulatory example, so the dropdown doubles as a working demo of
// what the system actually covers.
const SAMPLE_QUERIES = [
  "What are the management body's responsibilities for ICT risk governance under CSSF, DORA, and EBA?",
  "What are the reporting obligations for major ICT-related incidents under DORA?",
  "What are the requirements for the ICT risk management framework under DORA?",
  "What classification criteria and deadlines apply when notifying the CSSF of a major ICT-related incident?",
  "What due diligence and risk assessment is required before entering into an outsourcing arrangement?",
  "What ICT asset management and cryptographic control requirements apply under the DORA RTS on ICT risk management tools and methods?",
];

export function QueryForm({ onSubmit, disabled }: QueryFormProps) {
  const [query, setQuery] = useState("");

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const trimmed = query.trim();
    if (!trimmed || disabled) return;
    onSubmit(trimmed);
  }

  function handleSampleSelect(e: ChangeEvent<HTMLSelectElement>) {
    const sample = e.target.value;
    if (sample) setQuery(sample);
    e.target.selectedIndex = 0;
  }

  return (
    <form className="query-form" onSubmit={handleSubmit}>
      <label htmlFor="query-input">Regulatory query</label>
      <select
        className="query-form__samples"
        aria-label="Sample queries"
        defaultValue=""
        onChange={handleSampleSelect}
        disabled={disabled}
      >
        <option value="" disabled>
          Try a sample query…
        </option>
        {SAMPLE_QUERIES.map((sample) => (
          <option key={sample} value={sample}>
            {sample}
          </option>
        ))}
      </select>
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
