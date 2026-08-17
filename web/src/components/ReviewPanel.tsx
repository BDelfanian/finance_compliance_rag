import { useEffect, useState, type FormEvent } from "react";
import { ApiError, fetchReviews, submitReview } from "../api/client";
import type { ReviewRecord } from "../api/types";

// Human-in-the-loop approve/reject/annotate action on a completed run
// (roadmap §3.6) — doubles as the per-answer compliance sign-off record
// docs/06's MRM section calls for. There is no auth in this app, so
// reviewer name/role are self-reported free text, not a verified identity.
export function ReviewPanel({ traceId }: { traceId: string }) {
  const [reviews, setReviews] = useState<ReviewRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | undefined>();
  const [submitting, setSubmitting] = useState(false);

  const [reviewerName, setReviewerName] = useState("");
  const [reviewerRole, setReviewerRole] = useState("");
  const [annotation, setAnnotation] = useState("");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(undefined);
    fetchReviews(traceId)
      .then((r) => {
        if (!cancelled) setReviews(r);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof ApiError ? err.message : "Failed to load reviews.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [traceId]);

  async function handleDecision(decision: "approved" | "rejected", e: FormEvent) {
    e.preventDefault();
    if (!reviewerName.trim()) {
      setError("Reviewer name is required.");
      return;
    }
    setSubmitting(true);
    setError(undefined);
    try {
      const record = await submitReview(traceId, {
        decision,
        reviewer_name: reviewerName.trim(),
        reviewer_role: reviewerRole.trim() || null,
        annotation: annotation.trim() || null,
      });
      setReviews((prev) => [...prev, record]);
      setAnnotation("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Review submission failed.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="result-section review-panel">
      <h2>Review</h2>

      {loading ? (
        <p className="muted">Loading reviews…</p>
      ) : (
        reviews.length > 0 && (
          <ul className="review-list">
            {reviews.map((r, i) => (
              <li key={i} className={`review-list__item review-list__item--${r.decision}`}>
                <strong>{r.decision === "approved" ? "✓ Approved" : "✗ Rejected"}</strong> by{" "}
                {r.reviewer_name}
                {r.reviewer_role ? ` (${r.reviewer_role})` : ""} ·{" "}
                {new Date(r.timestamp).toLocaleString()}
                {r.annotation && <p className="review-list__annotation">{r.annotation}</p>}
              </li>
            ))}
          </ul>
        )
      )}

      <form className="review-form">
        <input
          type="text"
          placeholder="Your name"
          value={reviewerName}
          onChange={(e) => setReviewerName(e.target.value)}
          disabled={submitting}
        />
        <input
          type="text"
          placeholder="Role (optional, e.g. Compliance Officer)"
          value={reviewerRole}
          onChange={(e) => setReviewerRole(e.target.value)}
          disabled={submitting}
        />
        <textarea
          placeholder="Annotation (optional)"
          value={annotation}
          onChange={(e) => setAnnotation(e.target.value)}
          disabled={submitting}
          rows={2}
        />
        <div className="review-form__actions">
          <button type="submit" onClick={(e) => handleDecision("approved", e)} disabled={submitting}>
            Approve
          </button>
          <button
            type="submit"
            className="review-form__reject"
            onClick={(e) => handleDecision("rejected", e)}
            disabled={submitting}
          >
            Reject
          </button>
        </div>
      </form>

      {error && <p className="error-text">{error}</p>}
    </section>
  );
}
