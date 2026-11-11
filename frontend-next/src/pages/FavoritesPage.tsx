import { useEffect, useMemo, useState } from "react"
import { getRuns } from "../api/catalog"
import { ApiError, apiErrorMessage, canRetryApiError } from "../api/client"
import { getRunRecord } from "../api/records"
import type { FieldValueOut, RecordOut, RunSummaryOut } from "../api/types"
import { favoriteKey, loadFavorites, parseFavoriteKey, saveFavorites, toggleFavorite } from "../favorites"
import { count, fieldMoney, fieldPercent } from "../format"
import { Badge, ProvenanceBadge } from "./shared"

/**
 * Favorites — the records starred in Catalog, for one run at a time.
 *
 * Stars live in this browser only (`favorites.ts`); there is no server-side
 * favourite and no sync between devices. Each starred record is resolved by
 * its own `(execution_id, record_ref)` lookup within the selected run, so no
 * cross-run query exists. A record that no longer resolves is shown as such,
 * never hidden and never allowed to block the others.
 */
const MAX_RESOLVED = 50

type RunsState = { kind: "loading" } | { kind: "error"; message: string; retryable: boolean } | { kind: "ready"; runs: RunSummaryOut[] }
type Item = { kind: "loading" } | { kind: "missing" } | { kind: "error"; message: string } | { kind: "ready"; record: RecordOut }

const text = (value: FieldValueOut | undefined) => value?.value === null || value?.value === undefined ? "" : String(value.value)

function Figure({ label, value, format }: { label: string; value: FieldValueOut; format: (v: string | number | null) => string }) {
  return <span><small>{label}</small> {value.status === null ? <span className="local-note">not recorded</span> : <span className="fv">{format(value.value)} <ProvenanceBadge status={value.status} /></span>}</span>
}

export function FavoritesPage({ initialRunId = "", go }: { initialRunId?: string; go: (path: string) => void }) {
  const [favorites, setFavorites] = useState<string[]>(loadFavorites)
  const [runs, setRuns] = useState<RunsState>({ kind: "loading" })
  const [runId, setRunId] = useState(initialRunId)
  const [items, setItems] = useState<Record<string, Item>>({})
  const [reload, setReload] = useState(0)

  // Starred refs grouped by run, from the stored keys alone.
  const byRun = useMemo(() => {
    const groups = new Map<string, string[]>()
    for (const key of favorites) {
      const parsed = parseFavoriteKey(key)
      if (parsed) groups.set(parsed.executionId, [...(groups.get(parsed.executionId) ?? []), parsed.recordRef])
    }
    return groups
  }, [favorites])

  useEffect(() => {
    const controller = new AbortController()
    setRuns({ kind: "loading" })
    getRuns(controller.signal)
      .then(({ items: list }) => setRuns({ kind: "ready", runs: list }))
      .catch((error: unknown) => { if (!controller.signal.aborted) setRuns({ kind: "error", message: apiErrorMessage(error), retryable: canRetryApiError(error) }) })
    return () => controller.abort()
  }, [reload])

  const starredRuns = runs.kind === "ready" ? runs.runs.filter((r) => byRun.has(r.execution_id)) : []
  const activeRunId = starredRuns.some((r) => r.execution_id === runId) ? runId : starredRuns[0]?.execution_id ?? ""
  const refs = useMemo(() => (byRun.get(activeRunId) ?? []).slice(0, MAX_RESOLVED), [byRun, activeRunId])

  // Resolve when the run (or a retry) changes. Removing a star only drops it
  // from `refs`; the other records are not fetched again.
  useEffect(() => {
    const toLoad = (byRun.get(activeRunId) ?? []).slice(0, MAX_RESOLVED)
    if (!activeRunId || !toLoad.length) return
    const controller = new AbortController()
    setItems(Object.fromEntries(toLoad.map((ref) => [ref, { kind: "loading" } as Item])))
    for (const ref of toLoad) {
      getRunRecord(activeRunId, ref, controller.signal)
        .then((record) => setItems((current) => ({ ...current, [ref]: { kind: "ready", record } })))
        .catch((error: unknown) => {
          if (controller.signal.aborted) return
          const item: Item = error instanceof ApiError && error.status === 404 ? { kind: "missing" } : { kind: "error", message: apiErrorMessage(error) }
          setItems((current) => ({ ...current, [ref]: item }))
        })
    }
    return () => controller.abort()
  }, [activeRunId, reload]) // eslint-disable-line react-hooks/exhaustive-deps

  const remove = (key: string) => setFavorites((current) => { const next = toggleFavorite(current, key); saveFavorites(next); return next })
  const unlisted = runs.kind === "ready" ? [...byRun.keys()].filter((id) => !runs.runs.some((r) => r.execution_id === id)) : []
  const forgetUnlisted = () => setFavorites((current) => {
    const next = current.filter((key) => { const p = parseFavoriteKey(key); return p !== null && !unlisted.includes(p.executionId) })
    saveFavorites(next); return next
  })

  const header = <>
    <h1>Favorites</h1>
    <p className="local-note">Starred in this browser only — not saved on the server and not shared with other devices.</p>
  </>

  if (runs.kind === "loading") return <section className="panel">{header}<p aria-live="polite">Loading runs…</p></section>
  if (runs.kind === "error") return <section className="panel">{header}<p role="alert" className="notice">{runs.message}</p>{runs.retryable && <button onClick={() => setReload((n) => n + 1)}>Retry</button>}</section>
  if (!starredRuns.length) return <section className="panel">
    {header}
    <p>No favorites{unlisted.length ? " in the runs available here" : " yet"}. Star records in Catalog to collect them here.</p>
    {unlisted.length > 0 && <p className="local-note">{count(unlisted.length)} starred run{unlisted.length === 1 ? " is" : "s are"} not in the run list. <button onClick={forgetUnlisted}>Forget those stars</button></p>}
    <button onClick={() => go("/catalog")}>Browse Catalog</button>
  </section>

  const run = starredRuns.find((r) => r.execution_id === activeRunId)!
  const total = byRun.get(activeRunId)?.length ?? 0
  return <>
    {header}
    <section className="panel">
      <label>Run <select aria-label="Run" value={activeRunId} onChange={(e) => setRunId(e.target.value)}>
        {starredRuns.map((r) => <option key={r.execution_id} value={r.execution_id}>{r.input_filename} — {new Date(r.started_at).toLocaleString()} ({byRun.get(r.execution_id)!.length})</option>)}
      </select></label>{" "}
      <button onClick={() => go(`/catalog?run=${encodeURIComponent(activeRunId)}`)}>Open in Catalog</button>
      {total > MAX_RESOLVED && <p className="local-note">Showing the first {MAX_RESOLVED} of {count(total)} starred records of this run.</p>}
      {unlisted.length > 0 && <p className="local-note">{count(unlisted.length)} other starred run{unlisted.length === 1 ? " is" : "s are"} not in the run list. <button onClick={forgetUnlisted}>Forget those stars</button></p>}
    </section>

    <ul className="favorites" aria-label={`Favorites in ${run.input_filename}`}>
      {refs.map((ref) => {
        const key = favoriteKey(activeRunId, ref)
        const item = items[ref] ?? { kind: "loading" }
        const label = item.kind === "ready" ? text(item.record.title) || item.record.supplier_sku || ref : ref
        return <li key={ref} className="panel">
          {item.kind === "loading" && <p aria-live="polite">Loading <span className="mono">{ref}</span>…</p>}
          {item.kind === "missing" && <p>This record no longer exists in this run: <span className="mono">{ref}</span>.</p>}
          {item.kind === "error" && <p role="alert" className="notice">{ref}: {item.message}</p>}
          {item.kind === "ready" && <>
            <h2><a href={`/run/${encodeURIComponent(activeRunId)}/product/${encodeURIComponent(ref)}`}>{label}</a> {item.record.decision ? <Badge>{item.record.decision}</Badge> : <span className="local-note">no decision</span>}</h2>
            <p className="favorite-figures">
              <span><small>SKU</small> {item.record.supplier_sku ?? "—"}</span>
              <span><small>Source</small> {run.input_filename}</span>
              <Figure label="Profit" value={item.record.profit} format={fieldMoney} />
              <Figure label="ROI" value={item.record.roi} format={fieldPercent} />
            </p>
          </>}
          <button className="favorite-button" aria-pressed="true" aria-label={`Remove ${label} from favorites`} onClick={() => remove(key)}>★ Remove</button>
        </li>
      })}
    </ul>
  </>
}
