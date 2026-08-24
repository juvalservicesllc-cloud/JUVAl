import { describe, expect, it } from "vitest"
import { normalize, parseCsv } from "./engine"
import { findExactMatches, identifierOf } from "./matching"

const headers = "position-relative href,img-fluid src,product-brand-name,link,item-price,item-price (2)"
const recordFor = (href: string, sourceFileId: string) => ({ ...normalize(parseCsv(`${headers}\n${href},,Brand,Title,$10,$20`))[0], sourceFileId })

describe("cross-file exact matching", () => {
  it("groups records sharing the same supplier URL across two different source files", () => {
    const a = recordFor("/products/shared", "file-a")
    const b = recordFor("/products/shared", "file-b")
    const groups = findExactMatches([a, b])
    expect(groups).toHaveLength(1)
    expect(groups[0].records.map(r => r.sourceFileId).sort()).toEqual(["file-a", "file-b"])
  })

  it("does not match records with different identifiers", () => {
    const a = recordFor("/products/one", "file-a")
    const b = recordFor("/products/two", "file-b")
    expect(findExactMatches([a, b])).toHaveLength(0)
  })

  it("does not match same-URL records within a single file (needs >=2 distinct files)", () => {
    const a = recordFor("/products/shared", "file-a")
    const b = recordFor("/products/shared", "file-a")
    expect(findExactMatches([a, b])).toHaveLength(0)
  })

  it("never groups records with a missing identifier", () => {
    const a = { ...recordFor("/products/x", "file-a"), url: "", raw: { ...recordFor("/products/x", "file-a").raw, "position-relative href": "" } }
    const b = { ...recordFor("/products/x", "file-b"), url: "", raw: { ...recordFor("/products/x", "file-b").raw, "position-relative href": "" } }
    expect(identifierOf(a)).toBe("")
    expect(findExactMatches([a, b])).toHaveLength(0)
  })

  it("scales linearly (index-based), not quadratically, for the matching index", () => {
    const fileA = Array.from({ length: 250 }, (_, i) => recordFor(`/products/${i}`, "file-a"))
    const fileB = Array.from({ length: 250 }, (_, i) => recordFor(`/products/${i}`, "file-b"))
    const groups = findExactMatches([...fileA, ...fileB])
    expect(groups).toHaveLength(250)
    expect(groups.every(g => new Set(g.records.map(r => r.sourceFileId)).size === 2)).toBe(true)
  })
})
