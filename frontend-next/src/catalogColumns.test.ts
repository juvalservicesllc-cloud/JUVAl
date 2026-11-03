import { afterEach, expect, it, vi } from "vitest"
import { CATALOG_COLUMNS, COLUMN_KEY, defaultColumns, loadColumns, saveColumns } from "./catalogColumns"

afterEach(() => { vi.restoreAllMocks(); localStorage.clear() })

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
