import { afterEach, expect, it } from "vitest"
import { canonicalRoute, currentRoute } from "./routes"
afterEach(() => history.replaceState({}, "", "/"))
it.each([
  ["/upload", "/import"], ["/products?run=a%2Fb&search=kept", "/catalog?run=a%2Fb&search=kept"],
  ["/batches/b%3A1", "/batch/b%3A1"], ["/runs/r%2F1/records/row%3A2?x=1", "/run/r%2F1/product/row%3A2?x=1"],
  ["/runs/r-1", "/runs/r-1"], ["/upload/unknown", "/upload/unknown"],
])("maps only an unambiguous alias %s", (old, expected) => expect(canonicalRoute(old)).toBe(expected))
it("replaces the alias without adding history entries and preserves query/hash", () => {
  history.pushState({ marker: true }, "", "/products?run=run-1#section")
  const length = history.length
  expect(currentRoute()).toBe("/catalog?run=run-1")
  expect(location.hash).toBe("#section")
  expect(history.length).toBe(length)
  expect(history.state.marker).toBe(true)
})
