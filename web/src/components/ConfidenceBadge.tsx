interface ConfidenceBadgeProps {
  score: number;
  label?: string;
}

// Same thresholds as step6_read_only_ui.py's confidence_badge(): >=0.75
// green, >=0.5 orange, else red.
export function ConfidenceBadge({ score, label }: ConfidenceBadgeProps) {
  const value = score || 0;
  const pct = Math.round(value * 100);
  const tier = value >= 0.75 ? "high" : value >= 0.5 ? "medium" : "low";
  return (
    <span className={`confidence-badge confidence-badge--${tier}`}>
      {label ? `${label}: ` : ""}
      {pct}% confidence
    </span>
  );
}
