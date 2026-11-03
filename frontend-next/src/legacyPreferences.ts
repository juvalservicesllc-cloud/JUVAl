import { APPEARANCE_PREFIX, isAccent, validImage } from "./appearance"
import { CATALOG_COLUMNS, COLUMN_KEY } from "./catalogColumns"

export type PreferenceGroup = "appearance" | "columns" | "filters"
type Migration = { group: PreferenceGroup; source: string; destination: string; values: Record<string, string>; reason: string }
const QUERY_KEY = "juval.next.catalog.query.v1"
const sources = { appearance: "juval-theme-settings-v1", columns: "juval.catalog.columns.v4", filters: "juval.catalog.query.v1" }

/** Preview only, no writes. Never read browser run data, tokens or accounts. */
export function legacyPreference(group: PreferenceGroup): Migration {
  const destination = group === "appearance" ? APPEARANCE_PREFIX : group === "columns" ? COLUMN_KEY : QUERY_KEY
  const result: Migration = { group, source: sources[group], destination, values: {}, reason: "" }
  try {
    const store = group === "filters" ? sessionStorage : localStorage
    const occupied = group === "appearance" ? Object.keys(localStorage).some((key) => key.startsWith(APPEARANCE_PREFIX)) : store.getItem(destination) !== null
    if (occupied) return { ...result, reason: "Current preferences exist; they will not be overwritten." }
    const raw = store.getItem(sources[group])
    if (!raw || raw.length > 1600000) return { ...result, reason: "No usable legacy preferences on this origin." }
    const data = JSON.parse(raw)
    if (group === "appearance") {
      if (!data || typeof data !== "object" || !data.colors) throw new Error("Invalid legacy appearance")
      const mapping = { accent: "accent", background: "backgroundColor", sidebar: "sidebarColor", header: "headerColor", surface: "surfaceColor", text: "textColor", muted: "mutedColor", border: "borderColor" }
      for (const [old, current] of Object.entries(mapping)) {
        if (!isAccent(data.colors[old])) throw new Error("Invalid legacy color")
        result.values[APPEARANCE_PREFIX + current] = data.colors[old]
      }
      // Same legacy normalization as frontend/theme/storage.ts: older custom
      // and juval presets without appearanceMode used dark, light used light.
      const mode = data.appearanceMode ?? (data.preset === "light" ? "light" : ["dark", "custom", "juval"].includes(data.preset) ? "dark" : null)
      if (mode !== "light" && mode !== "dark") throw new Error("Unknown legacy theme")
      for (const [old, current] of [["logoDataUrl", "logo"], ["backgroundImageDataUrl", "background"]]) {
        if (data[old] !== null && !validImage(data[old])) throw new Error("Unsupported legacy image")
        result.values[APPEARANCE_PREFIX + current] = data[old] ?? ""
      }
      if (!["cover", "contain"].includes(data.backgroundSize) || !["center", "top", "bottom"].includes(data.backgroundPosition) || typeof data.overlayOpacity !== "number" || data.overlayOpacity < 0 || data.overlayOpacity > 0.9 || !Number.isFinite(data.overlayOpacity)) throw new Error("Invalid legacy background")
      Object.assign(result.values, { [APPEARANCE_PREFIX + "dark"]: String(mode === "dark"), [APPEARANCE_PREFIX + "backgroundFit"]: data.backgroundSize, [APPEARANCE_PREFIX + "backgroundPosition"]: data.backgroundPosition, [APPEARANCE_PREFIX + "overlayOpacity"]: String(data.overlayOpacity) })
    } else if (group === "columns") {
      const mapping: Record<string, string[]> = { image: ["image"], product: ["title", "sku"], record_ref: ["record_ref"], identity: ["identity"], price: ["selling"], cog: ["cog"], profit: ["profit"], roi: ["roi"], margin: ["margin"], hazmat: ["hazmat"], bulky: ["bulky"], decision: ["decision"], issues: ["issues"], favorite: ["favorite"], action: [] }
      if (!Array.isArray(data) || !data.length || data.some((key) => typeof key !== "string" || !Object.hasOwn(mapping, key))) throw new Error("Unknown legacy columns")
      const order: string[] = [...new Set((data as string[]).flatMap((key) => mapping[key]))]
      const knownLegacy = new Set(Object.values(mapping).flat())
      const columns = [...order.map((id) => ({ id, visible: true })), ...CATALOG_COLUMNS.filter(({ id }) => !order.includes(id)).map(({ id }) => ({ id, visible: id === "title" || !knownLegacy.has(id) }))]
      result.values[destination] = JSON.stringify(columns)
    } else {
      if (!data || typeof data !== "object" || Array.isArray(data)) throw new Error("Invalid legacy filters")
      // Whitelist only preference fields. The existing Catalog loader validates
      // enums/units; offset, run, brand and any server values are never copied.
      const fields = ["search", "decision", "sort", "direction", "limit", "minRoi", "minProfit", "minMargin", "confidence", "hazmat", "bulky", "provenanceField", "provenanceStatus"]
      result.values[destination] = JSON.stringify(Object.fromEntries(fields.filter((key) => Object.hasOwn(data, key) && (typeof data[key] === "string" || key === "limit" && typeof data[key] === "number")).map((key) => [key, typeof data[key] === "string" ? data[key].slice(0, key === "search" ? 200 : 24) : data[key]])))
    }
    return result
  } catch { return { ...result, values: {}, reason: "Legacy preferences are invalid or browser storage is unavailable; nothing was changed." } }
}

/** Re-read on explicit action; never overwrite a current destination. Originals
 * remain available. Roll back this attempt's writes if browser quota fails. */
export function importLegacyPreferences(group: PreferenceGroup): string {
  const plan = legacyPreference(group)
  if (plan.reason) return plan.reason
  const written: [string, string][] = []
  const store = group === "filters" ? sessionStorage : localStorage
  try {
    for (const [key, value] of Object.entries(plan.values)) {
      if (store.getItem(key) !== null) throw new Error("Destination changed")
      store.setItem(key, value); written.push([key, value])
    }
    return "Imported. Legacy originals are preserved. Filters apply on the next Catalog visit."
  } catch {
    for (const [key, value] of written) { try { if (store.getItem(key) === value) store.removeItem(key) } catch { /* report partial storage failure */ } }
    return "Import failed; check browser storage. Legacy originals were not changed."
  }
}
