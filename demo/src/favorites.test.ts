import { describe, expect, it } from "vitest"
import { favoriteKey, sourceIdOf } from "./favorites"

describe("batch-aware favorite identity", () => {
  it("scopes a key to run + source file + record, so identical recordRef across files stays distinct", () => {
    const keyA = favoriteKey("run-1", "file-a", "wm-0001")
    const keyB = favoriteKey("run-1", "file-b", "wm-0001")
    expect(keyA).not.toBe(keyB)
  })

  it("falls back to a stable 'legacy' source id for records saved before batch support existed", () => {
    expect(sourceIdOf({ sourceFileId: undefined })).toBe("legacy")
    expect(sourceIdOf({ sourceFileId: "file-a" })).toBe("file-a")
  })
})
