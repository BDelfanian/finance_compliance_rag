import type { RunState } from "../hooks/useQueryRun";

const STAGES: { key: "retrieval" | "citation" | "summary" | "risk"; label: string }[] = [
  { key: "retrieval", label: "Retrieval" },
  { key: "citation", label: "Citation-bound answer" },
  { key: "summary", label: "Executive summary" },
  { key: "risk", label: "Risk assessment" },
];

// Progress checklist for POST /query/stream's SSE stages, replacing one long
// spinner with a view of which agent stage has completed so far.
export function StageTimeline({ state }: { state: RunState }) {
  return (
    <ol className="stage-timeline">
      {STAGES.map((stage) => {
        const done = Boolean(state[stage.key]);
        const active = !done && state.status === "running";
        return (
          <li
            key={stage.key}
            className={`stage-timeline__item ${done ? "is-done" : active ? "is-active" : ""}`}
          >
            <span className="stage-timeline__marker">{done ? "✓" : active ? "…" : "○"}</span>
            {stage.label}
          </li>
        );
      })}
    </ol>
  );
}
