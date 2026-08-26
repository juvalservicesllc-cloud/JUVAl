/**
 * "What does this mean?" disclosure, recovered from the Golden Product
 * Experience (ADR-029, `demo/src/pages/ExplainableMetricCard.tsx`).
 *
 * It explains what a metric *is* and how the backend derived it. It never
 * recommends, never scores, and never recomputes: the value beside it comes
 * straight from the persisted snapshot (ADR-006 keeps every calculation in the
 * deterministic backend), and this component receives only text.
 *
 * `<details>` is the native disclosure -- keyboard operable, screen-reader
 * announced and usable on touch without a hover state, which a tooltip is not.
 */
export function MetricExplainer({ label, description }: { label: string; description: string }) {
  return (
    <details className="metric-explainer">
      <summary aria-label={`What does ${label} mean?`}>What does this mean?</summary>
      <p>{description}</p>
    </details>
  )
}
