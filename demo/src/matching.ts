import type { DemoRecord } from "./demo-engine"
import { sourceIdOf } from "./favorites"

export type MatchStatus = "EXACT_IDENTIFIER_MATCH" | "POSSIBLE_MATCH" | "NO_MATCH"
export type MatchGroup = { identifier: string; records: DemoRecord[] }

// The only stable, real (VERIFIED_SOURCE) cross-file identifier this demo's West Marine
// export carries is the supplier product URL — ASIN here is a DEMO_FIXTURE, not a real
// identifier, so it must not drive matching. No SKU/UPC exist in this source.
export const identifierOf = (record: DemoRecord): string => (record.url || record.raw["position-relative href"] || "").trim().toLowerCase()

// ponytail: single-pass map keyed by identifier keeps this O(n) instead of comparing every pair.
export function findExactMatches(records: DemoRecord[]): MatchGroup[] {
  const byIdentifier = new Map<string, DemoRecord[]>()
  for (const record of records) {
    const identifier = identifierOf(record)
    if (!identifier) continue
    const group = byIdentifier.get(identifier)
    if (group) group.push(record); else byIdentifier.set(identifier, [record])
  }
  return [...byIdentifier.entries()]
    .filter(([, group]) => new Set(group.map(sourceIdOf)).size >= 2)
    .map(([identifier, group]) => ({ identifier, records: group }))
    .sort((a, b) => b.records.length - a.records.length || a.identifier.localeCompare(b.identifier))
}

// Fuzzy matching is explicitly out of scope; anything without a shared exact identifier is NO_MATCH.
export const matchStatus = (identifier: string, groupSize: number): MatchStatus => (!identifier ? "NO_MATCH" : groupSize >= 2 ? "EXACT_IDENTIFIER_MATCH" : "NO_MATCH")
