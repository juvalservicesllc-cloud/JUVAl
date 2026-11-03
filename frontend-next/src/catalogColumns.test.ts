import { afterEach, expect, it, vi } from "vitest"
import { CATALOG_COLUMNS, COLUMN_KEY, defaultColumns, loadColumns, saveColumns } from "./catalogColumns"

afterEach(() => { vi.restoreAllMocks(); localStorage.clear() })

const historical = ["image", "source", "brand", "title", "cog", "suggested", "selling", "profit", "roi", "margin", "hazmat", "bulky", "decision", "demand", "favorite"]
const additions = ["sku", "identity", "record_ref", "issues"]

it("preserves the complete initial historical layout and appends visible identity/issues columns", () => {
  expect(defaultColumns().map((column) => column.id)).toEqual([...historical, ...additions])
  expect(loadColumns()).toEqual(defaultColumns())
  expect(defaultColumns().every((column) => column.visible)).toBe(true)
  expect(localStorage.getItem(COLUMN_KEY)).toBeNull() // read/defaults never write preferences
})

it("keeps an existing historical order and hidden columns, adding missing columns without a storage write", () => {
  const saved = historical.map((id) => ({ id, visible: id !== "cog" })).reverse()
  const raw = JSON.stringify(saved)
  localStorage.setItem(COLUMN_KEY, raw)
  expect(loadColumns()).toEqual([...saved, ...additions.map((id) => ({ id, visible: true }))])
  expect(localStorage.getItem(COLUMN_KEY)).toBe(raw)
})

it("retains explicitly reordered and hidden new columns instead of imposing the default order", () => {
  const saved = [{ id: "issues", visible: false }, { id: "sku", visible: true }, { id: "title", visible: true }, { id: "identity", visible: false }, { id: "record_ref", visible: true }] as const
  saveColumns([...saved])
  const raw = localStorage.getItem(COLUMN_KEY)
  expect(loadColumns().slice(0, saved.length)).toEqual(saved)
  expect(localStorage.getItem(COLUMN_KEY)).toBe(raw)
  expect(loadColumns()).toHaveLength(CATALOG_COLUMNS.length)
})

it("restores valid order and visibility, drops unknown and duplicate ids and adds new columns", () => {
  localStorage.setItem(COLUMN_KEY, JSON.stringify([{ id: "roi", visible: false }, { id: "title", visible: false }, { id: "obsolete" }, null, { id: "roi" }]))
  const columns = loadColumns()
  expect(columns.slice(0, 2)).toEqual([{ id: "roi", visible: false }, { id: "title", visible: true }])
  expect(columns).toHaveLength(CATALOG_COLUMNS.length)
  expect(columns.slice(2)).toEqual(defaultColumns().filter((c) => !["roi", "title"].includes(c.id)))
})

it.each(["null", "false", "{}", "{broken"])("ignores corrupt preferences: %s", (value) => {
  localStorage.setItem(COLUMN_KEY, value)
  expect(loadColumns()).toEqual(defaultColumns())
})

it("continues without storage access or quota", () => {
  vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("unavailable") })
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("quota") })
  expect(loadColumns()).toEqual(defaultColumns())
  expect(() => saveColumns(defaultColumns())).not.toThrow()
})
