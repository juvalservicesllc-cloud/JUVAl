import type { ImportPreviewResponse, PreviewColumnOut } from "../api/types"
import { count } from "../format"

/**
 * The server importer's verdict on one queued file (Golden's pre-submit
 * preview and column classification, ADR-030). Golden parsed the file in the
 * browser and guessed a supplier format; here every line comes from
 * `POST /api/v1/runs/preview`, which runs the real importer and stores nothing.
 * It is labelled PREVIEW throughout so it is never mistaken for a processed run:
 * no decision, profit or risk exists yet.
 */
export function ImportPreview({ preview, onClose }: { preview: ImportPreviewResponse; onClose: () => void }) {
  const byStatus = (status: PreviewColumnOut["status"]) => preview.columns.filter((c) => c.status === status)
  const mapped = byStatus("MAPPED")
  const unknown = byStatus("UNKNOWN")
  const duplicate = byStatus("DUPLICATE")
  const blank = byStatus("BLANK")

  return <section className="panel import-preview" aria-label={`Import preview of ${preview.input_filename}`}>
    <h2><span className="preview-tag">PREVIEW</span> {preview.input_filename}</h2>
    <p>Validation only — nothing was processed or stored and no run was created. Decisions, profit and risk are calculated only when you process the file.</p>

    {preview.fatal
      ? <p role="alert" className="notice">The importer cannot read records from this file as it is{preview.missing_required_columns.length ? ": required columns are missing" : ""}. Processing it would fail.</p>
      : <p className="preview-ok">The importer can read this file.</p>}

    <div className="kpis">
      <article><small>Rows read</small><strong>{count(preview.rows_scanned)}</strong></article>
      <article><small>Importable records</small><strong>{count(preview.records_importable)}</strong></article>
      <article><small>Blank rows skipped</small><strong>{count(preview.rows_skipped_blank)}</strong></article>
      <article><small>Issues</small><strong>{count(preview.issues_total)}</strong></article>
    </div>

    {preview.missing_required_columns.length > 0 && <>
      <h3>Missing required columns</h3>
      <ul>{preview.missing_required_columns.map((c) => <li key={c.canonical}><b className="mono">{c.canonical}</b> — {c.target}</li>)}</ul>
    </>}

    <h3>Recognized columns ({count(mapped.length)})</h3>
    {mapped.length === 0 ? <p>None.</p> : <div className="table"><table>
      <thead><tr><th>Column</th><th>Header</th><th>Read as</th><th>Destination</th><th>Required</th></tr></thead>
      <tbody>{mapped.map((c) => <tr key={c.position}>
        <td>{c.position}</td>
        <td>{c.header}</td>
        <td className="mono">{c.canonical}{c.alias_of ? " (alias)" : ""}</td>
        <td>{c.target}{c.group === "native_financial_evidence" ? " · financial evidence, does not affect decisions" : ""}</td>
        <td>{c.required ? "Required" : "Optional"}</td>
      </tr>)}</tbody>
    </table></div>}

    <h3>Unknown columns — ignored ({count(unknown.length)})</h3>
    {unknown.length === 0 ? <p>None.</p> : <ul>{unknown.map((c) => <li key={c.position}>Column {c.position}: <b>{c.header}</b></li>)}</ul>}

    <h3>Duplicate columns — ignored ({count(duplicate.length)})</h3>
    {duplicate.length === 0 ? <p>None.</p> : <ul>{duplicate.map((c) => <li key={c.position}>Column {c.position}: <b>{c.header}</b> repeats <span className="mono">{c.canonical}</span>; the first occurrence is used</li>)}</ul>}

    {blank.length > 0 && <p className="local-note">{count(blank.length)} column{blank.length === 1 ? " has" : "s have"} no header and {blank.length === 1 ? "is" : "are"} ignored.</p>}

    <h3>Issues by type</h3>
    {preview.issue_counts.length === 0 ? <p>No issues reported by the importer.</p> : <div className="table"><table>
      <thead><tr><th>Level</th><th>Code</th><th>Count</th></tr></thead>
      <tbody>{preview.issue_counts.map((c) => <tr key={`${c.level}-${c.code}`}><td>{c.level}</td><td className="mono">{c.code}</td><td>{count(c.count)}</td></tr>)}</tbody>
    </table></div>}

    {preview.issues.length > 0 && <details>
      <summary>Issue details ({preview.issues_truncated ? `first ${count(preview.issues.length)} of ${count(preview.issues_total)}` : count(preview.issues.length)})</summary>
      <ul>{preview.issues.map((issue, index) => <li key={index}>
        <b>{issue.level}</b> <span className="mono">{issue.code}</span>{issue.record_ref ? ` · ${issue.record_ref}` : ""}: {issue.message}
      </li>)}</ul>
      {preview.issues_truncated && <p className="local-note">Only the first {count(preview.issues.length)} issues are listed; the counts above include all {count(preview.issues_total)}.</p>}
    </details>}

    <p><small>Input hash <span className="mono">{preview.input_hash}</span></small></p>
    <button onClick={onClose}>Close preview</button>
  </section>
}
