import { useState } from "react"
import { importLegacyPreferences, legacyPreference, type PreferenceGroup } from "../legacyPreferences"

export function LegacyPreferences({ onImported }: { onImported: () => void }) {
  const [message, setMessage] = useState("")
  return <section className="panel">
    <h2>Import legacy browser preferences</h2>
    <p>Explicit import from this browser origin only. Current settings are never overwritten. Old keys are preserved; nothing moves between origins. Run IDs, records, credentials, page offsets and brands are excluded.</p>
    <p>Close other JUVAl tabs before importing so another tab cannot change preferences during this action.</p>
    {(["appearance", "columns", "filters"] as PreferenceGroup[]).map((group) => {
      const plan = legacyPreference(group)
      return <div key={group} className="appearance-inputs">
        <span>{group}: {plan.reason || `${Object.keys(plan.values).length} destination key(s) available from ${plan.source}`}</span>
        <button disabled={!!plan.reason} onClick={() => { const result = importLegacyPreferences(group); setMessage(result); if (group === "appearance" && result.startsWith("Imported.")) onImported() }}>Import legacy {group}</button>
      </div>
    })}
    {message && <p role="status">{message}</p>}
  </section>
}
