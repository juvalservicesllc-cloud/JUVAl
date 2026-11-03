import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, expect, it, vi } from "vitest"
import { App } from "../app/App"

const png = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a9xkAAAAASUVORK5CYII="
function open() { history.pushState({}, "", "/appearance"); return render(<App />) }
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); localStorage.clear(); history.pushState({}, "", "/") })

it("applies accent, validates hex, warns on contrast and restores the preference", async () => {
  const view = open()
  const user = userEvent.setup()
  fireEvent.change(screen.getByLabelText("Accent hex"), { target: { value: "#ffffff" } })
  expect(screen.getByRole("status")).toHaveTextContent(/Insufficient contrast/)
  expect(document.querySelector(".app")).toHaveStyle({ "--accent": "#ffffff" })
  expect(document.querySelector(".app")).toHaveStyle({ "--on-accent": "#000000" })
  expect(screen.getByText(/The selected accent is kept for fills/)).toBeInTheDocument()
  fireEvent.change(screen.getByLabelText("Accent hex"), { target: { value: "bad" } })
  expect(screen.getByRole("alert")).toHaveTextContent(/last valid accent/)
  expect(localStorage.getItem("juval.appearance.accent")).toBe("#ffffff")
  expect(screen.getAllByRole("combobox", { name: "Theme" })).toHaveLength(1)
  await user.selectOptions(screen.getByRole("combobox", { name: "Theme" }), "false")
  expect(document.querySelector(".app")).not.toHaveClass("dark")
  expect(document.querySelector(".app")).toHaveStyle({ "--accent-text": "#172033" })
  view.unmount()
  open()
  expect(screen.getByLabelText("Accent hex")).toHaveValue("#ffffff")
  expect(screen.getByRole("switch")).toHaveAttribute("aria-checked", "false")
})

it("uploads logo/background locally with preview, persists them and resets only appearance", async () => {
  const fetch = vi.fn()
  vi.stubGlobal("fetch", fetch)
  localStorage.setItem("juval.catalog.columns.v1", "keep-columns")
  localStorage.setItem("juval.catalog.favorites.v1", "keep-favorites")
  const user = userEvent.setup()
  const view = open()
  const file = new File([Uint8Array.from(atob(png), (c) => c.charCodeAt(0))], "logo.png", { type: "image/png" })
  await user.upload(screen.getByLabelText("Logo image"), file)
  expect(await screen.findByAltText("Custom JUVAl logo")).toHaveAttribute("src", `data:image/png;base64,${png}`)
  expect(screen.getByAltText("Logo preview")).toBeInTheDocument()
  await user.upload(screen.getByLabelText("Background image"), file)
  await waitFor(() => expect(localStorage.getItem("juval.appearance.background")).toContain(png))
  expect(document.querySelector(".app")).toHaveClass("has-custom-background")
  view.unmount(); open()
  expect(screen.getByAltText("Logo preview")).toBeInTheDocument()
  await user.click(screen.getByRole("button", { name: "Reset appearance defaults" }))
  expect(screen.queryByAltText("Logo preview")).not.toBeInTheDocument()
  expect(document.querySelector(".app")).toHaveClass("dark")
  expect(document.querySelector(".app")).not.toHaveClass("has-custom-background")
  expect(localStorage.length).toBe(2)
  expect(localStorage.getItem("juval.catalog.columns.v1")).toBe("keep-columns")
  expect(localStorage.getItem("juval.catalog.favorites.v1")).toBe("keep-favorites")
  expect(fetch).not.toHaveBeenCalled()
})

it("shows file rejection and still works when browser storage is unavailable", async () => {
  vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("blocked") })
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("quota") })
  open()
  const user = userEvent.setup({ applyAccept: false })
  await user.upload(screen.getByLabelText("Logo image"), new File(["<svg/>"], "logo.svg", { type: "image/svg+xml" }))
  expect(await screen.findByRole("alert")).toHaveTextContent(/SVG is not supported/)
  await user.click(screen.getByRole("switch"))
  expect(screen.getByRole("switch")).toHaveAttribute("aria-checked", "false")
  fireEvent.change(screen.getByLabelText("Accent color"), { target: { value: "#abcdef" } })
  expect(document.querySelector(".app")).toHaveStyle({ "--accent": "#abcdef" })
})
