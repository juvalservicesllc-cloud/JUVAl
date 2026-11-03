import { readFileSync } from "node:fs"
import { createElement } from "react"
import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"
import { App } from "../app/App"

// Import the real sheets as text: component CSS imports are stubbed by Vitest.
// jsdom exposes the winning custom-property declaration, not resolved RGB.
const sheets = {
  base: readFileSync("src/style.css", "utf8"),
  appearance: readFileSync("src/pages/appearance.css", "utf8"),
}
const styles = []
afterEach(() => {
  cleanup()
  for (const sheet of styles.splice(0)) sheet.remove()
  localStorage.clear()
  history.replaceState({}, "", "/")
})

describe.each([["appearance", "base"], ["base", "appearance"]])("appearance cascade, %s then %s", (first, second) => {
  function open(dark, custom) {
    for (const name of [first, second]) {
      const sheet = document.createElement("style")
      sheet.textContent = sheets[name]
      document.head.append(sheet)
      styles.push(sheet)
    }
    localStorage.setItem("juval.appearance.dark", String(dark))
    if (custom) {
      localStorage.setItem("juval.appearance.backgroundColor", "#111111")
      localStorage.setItem("juval.appearance.textColor", "#abcdef")
    }
    history.replaceState({}, "", "/appearance")
    render(createElement(App))
    return document.querySelector(".app")
  }

  it.each([true, false])("keeps readable custom page text when dark=%s regardless of sheet order", (dark) => {
    const app = open(dark, true)
    expect(app).toHaveClass("has-custom-colors")
    expect(app.style.getPropertyValue("--page-text")).toBe("#abcdef")
    expect(getComputedStyle(app).getPropertyValue("--text").trim()).toBe("var(--page-text)")
    expect(getComputedStyle(app.querySelector("header > span")).color).toBe("var(--panel-text)")
    expect(screen.getByLabelText("Text hex")).toHaveValue("#abcdef")
    expect(localStorage.getItem("juval.appearance.textColor")).toBe("#abcdef")
  })

  it.each([true, false])("keeps the default palette when dark=%s and no colors were customized", (dark) => {
    const app = open(dark, false)
    expect(app).not.toHaveClass("has-custom-colors")
    expect(app.style.getPropertyValue("--page-text")).toBe("")
    // jsdom may leave inherited custom properties on :root rather than copying
    // them to the element; use the ordinary inheritance fallback for light.
    const text = getComputedStyle(app).getPropertyValue("--text") || getComputedStyle(document.documentElement).getPropertyValue("--text")
    expect(text.trim()).toBe(dark ? "#f1f5f9" : "#172033")
  })
})
