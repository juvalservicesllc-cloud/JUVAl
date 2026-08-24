import { describe, expect, it } from "vitest"
import { count, money, percent } from "./format"

// These assertions are deliberately literal. Under a non-English default
// locale -- the operator server runs es_ES.UTF-8 -- an implementation that
// forwards `undefined` to toLocaleString renders "5,00 $" and "10,00 %" and
// fails here. That is the point: the suite must fail on the machine where
// the rendering is wrong, not pass everywhere and be wrong somewhere.
describe("deterministic formatting", () => {
  it("renders money as US dollars regardless of the host locale", () => {
    expect(money(5)).toBe("$5.00")
    expect(money(0)).toBe("$0.00")
    expect(money(1234.5)).toBe("$1,234.50")
    expect(money(-12.345)).toBe("-$12.35")
  })

  it("renders a ratio as a percentage, not a ratio", () => {
    // The backend stores ROI/margin as ratios; the UX contract is percent.
    expect(percent(0.1)).toBe("10.00%")
    expect(percent(0.5)).toBe("50.00%")
    expect(percent(0)).toBe("0.00%")
    expect(percent(0.125, 1)).toBe("12.5%")
  })

  it("groups counts with the same fixed locale", () => {
    expect(count(0)).toBe("0")
    expect(count(1234)).toBe("1,234")
    expect(count(1234567)).toBe("1,234,567")
  })

  it("does not round a money value away from its true magnitude", () => {
    // Display-only rounding must not turn a loss into a break-even.
    expect(money(-0.004)).not.toBe("$0.00")
    expect(money(0.005)).toBe("$0.01")
  })
})
