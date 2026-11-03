import { render, screen } from "@testing-library/react"
import { afterEach, expect, it, vi } from "vitest"
import { RunContext } from "./RunContext"

afterEach(() => vi.unstubAllGlobals())
const preview = { records: [{ record_ref: "row:1", title: { value: "Supplier title", status: "INFERRED" }, decision: "REVIEW", issue_count: 2 }], pagination: { total: 26 } }

it("loads only a bounded first page and the actual batch, with scoped links/provenance", async () => {
  const fetch = vi.fn((url: string) => Promise.resolve(new Response(JSON.stringify(String(url).includes("/batch") ? { batch_id: "b-1", total_files: 1, status: "SUCCESS", files: [{ ordinal: 0, filename: "source.csv", status: "SUCCESS", execution_id: "r-1" }] } : preview))))
  vi.stubGlobal("fetch", fetch)
  render(<RunContext executionId="r-1" />)
  expect(await screen.findByRole("link", { name: "Open batch" })).toHaveAttribute("href", "/batch/b-1")
  expect(await screen.findByRole("link", { name: "Supplier title" })).toHaveAttribute("href", "/run/r-1/product/row%3A1")
  expect(screen.getByLabelText("Status: INFERRED")).toBeInTheDocument()
  const request = new URL(fetch.mock.calls.find(([url]) => String(url).includes("/records"))![0])
  expect(request.searchParams.get("limit")).toBe("25")
  expect(request.searchParams.get("offset")).toBe("0")
  expect(request.searchParams.has("decision")).toBe(false)
  expect(fetch).toHaveBeenCalledTimes(2)
})

it("keeps the preview when the batch fails and offers retry instead of inventing context", async () => {
  vi.stubGlobal("fetch", vi.fn((url: string) => Promise.resolve(new Response(JSON.stringify(String(url).includes("/batch") ? { detail: "unavailable" } : preview), { status: String(url).includes("/batch") ? 500 : 200 }))))
  render(<RunContext executionId="r-1" />)
  expect(await screen.findByRole("alert")).toHaveTextContent("Batch context unavailable")
  expect(await screen.findByRole("link", { name: "Supplier title" })).toBeInTheDocument()
  expect(screen.getByRole("button", { name: "Retry context and preview" })).toBeInTheDocument()
})
