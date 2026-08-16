import type { Citation } from "../api/types";

interface CitationListProps {
  sources: Citation[];
  citedChunkIds: Set<string>;
  emptyLabel?: string;
}

// Mirrors step6_read_only_ui.py's render_citations(): every retrieved
// source is shown, labeled "cited" vs "retrieved, not cited" rather than
// only showing the narrower cited subset. Unlike the Streamlit version this
// doesn't need a text heuristic (_is_cited_in_answer) — the API already
// tells cited (answer.citations) and retrieved (sources) apart structurally.
export function CitationList({ sources, citedChunkIds, emptyLabel = "No sources returned." }: CitationListProps) {
  if (!sources.length) return <p className="muted">{emptyLabel}</p>;

  return (
    <ul className="citation-list">
      {sources.map((c, i) => {
        const cited = c.chunk_id ? citedChunkIds.has(c.chunk_id) : false;
        const reference = c.source_reference ?? c.chunk_id ?? "?";
        const label = c.source_regulation ? `${c.source_regulation} ${reference}` : reference;
        return (
          <li key={c.chunk_id ?? `${reference}-${i}`} className="citation-list__item">
            <span className="citation-list__label">{label}</span>
            {typeof c.similarity_score === "number" && (
              <span className="citation-list__score"> · similarity {c.similarity_score.toFixed(2)}</span>
            )}
            <span
              className={`citation-list__status ${
                cited ? "citation-list__status--cited" : "citation-list__status--uncited"
              }`}
            >
              {cited ? "✓ cited in answer" : "retrieved, not cited"}
            </span>
            {c.excerpt && <p className="citation-list__excerpt">{c.excerpt}</p>}
          </li>
        );
      })}
    </ul>
  );
}
