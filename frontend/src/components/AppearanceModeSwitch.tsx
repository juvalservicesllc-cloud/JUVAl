import type { AppearanceMode } from "../theme/types"

export function AppearanceModeSwitch({ mode, onChange }: { mode: AppearanceMode; onChange: (mode: AppearanceMode) => void }) {
  const isDark = mode === "dark"
  return <button type="button" role="switch" aria-checked={isDark} aria-label="Appearance mode: light or dark" className={`appearance-mode-switch ${isDark ? "is-dark" : "is-light"}`} onClick={() => onChange(isDark ? "light" : "dark")}><span className="appearance-mode-thumb" aria-hidden="true">{isDark ? "☾" : "☀"}</span><span>Light</span><span>Dark</span></button>
}
