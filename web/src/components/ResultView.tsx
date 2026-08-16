import type { ResultViewModel } from "../api/viewModel";
import { ConfidenceBadge } from "./ConfidenceBadge";
import { CitationList } from "./CitationList";

export function ResultView({ vm }: { vm: ResultViewModel }) {
  if (vm.status === "idle") return null;

  return (
    <div className="result-view">
      {vm.error && <div className="error-banner">⚠ {vm.error}</div>}

      {vm.retrievedCount !== undefined && !vm.answer && (
        <section className="result-section">
          <h2>Retrieval</h2>
          <p className="muted">
            {vm.retrievedCount} regulatory chunk(s) retrieved. Generating a citation-bound answer…
          </p>
        </section>
      )}

      {vm.answer && (
        <section className="result-section">
          <h2>Answer</h2>
          <p className="answer-text">{vm.answer.text || "No answer returned."}</p>
          <ConfidenceBadge score={vm.confidence ?? vm.answer.confidence} />
        </section>
      )}

      {vm.answer && (
        <section className="result-section">
          <h2>Sources</h2>
          <CitationList sources={vm.sources} citedChunkIds={vm.citedChunkIds} />
        </section>
      )}

      {vm.answer && (
        <div className="result-columns">
          <section className="result-section">
            <h2>Executive Summary</h2>
            {vm.summary ? (
              <p className="summary-text">{vm.summary.text || "No summary available."}</p>
            ) : (
              <p className="muted">Summarizing…</p>
            )}
          </section>

          <section className="result-section">
            <h2>Risk Assessment</h2>
            {vm.risk ? (
              <>
                {vm.risk.warnings.length ? (
                  <ul className="risk-warnings">
                    {vm.risk.warnings.map((w) => (
                      <li key={w}>{w}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="risk-ok">No material regulatory risks detected.</p>
                )}
                <ConfidenceBadge score={vm.risk.confidence} />
              </>
            ) : (
              <p className="muted">Assessing risk…</p>
            )}
          </section>
        </div>
      )}

      {vm.auditTrail && (
        <footer className="result-footer">
          Trace <code>{vm.auditTrail.trace_id}</code> · model {vm.auditTrail.model_version} ·{" "}
          {new Date(vm.auditTrail.timestamp).toLocaleString()}
        </footer>
      )}
    </div>
  );
}
