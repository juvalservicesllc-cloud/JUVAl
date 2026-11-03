import { join } from "node:path"
import { DIR, apiRecord, expect, expectSameTab, fixtures, markTab, row, test } from "./support"

test("B3: seeded synthetic BUY keeps empty reasons and honest economic provenance", async ({ page }) => {
  // BUY cannot be reached by upload under ADR-052. This tests a persisted
  // rendering snapshot, not demand verification or a sourcing recommendation.
  fixtures("seed-buy", join(DIR, "juval.db"))
  await page.goto("/catalog?run=e2e-seeded-buy")
  const item = row(page, "E2E seeded BUY (synthetic)")
  const buy = item.getByText("● BUY", { exact: true })
  await expect(buy).toBeVisible()
  expect(await buy.evaluate((e) => {
    const expected = document.createElement("span")
    expected.style.color = "var(--success)"
    e.append(expected)
    const same = getComputedStyle(e).color === getComputedStyle(expected).color
    expected.remove()
    return same
  })).toBe(true)
  await expect(item.getByLabel("Status: INFERRED", { exact: true })).toHaveCount(4)
  await expect(item.getByLabel("Status: VERIFIED", { exact: true })).toHaveCount(0)
  const stored = await apiRecord(page, "e2e-seeded-buy")
  expect([stored.decision, stored.decision_reasons, stored.decision_reason_codes]).toEqual(["BUY", [], []])
  await markTab(page)
  await item.getByRole("link").click()
  await expectSameTab(page)
  const decision = page.getByRole("region", { name: "Decision", exact: true })
  await expect(decision.getByText("● BUY")).toBeVisible()
  await expect(decision).toContainText("No disqualifying or review reasons recorded.")
  await expect(decision.getByRole("listitem")).toHaveCount(0)
  const economics = page.getByRole("region", { name: "Economics", exact: true })
  for (const [label, amount] of [["Selling price", "$30.00"], ["Profit", "$15.00"], ["ROI", "125.0%"], ["Margin", "50.0%"], ["Break-even price", "$15.00"]]) {
    const card = economics.getByRole("article").filter({ has: page.getByText(label, { exact: true }) })
    await expect(card).toContainText(amount)
    await expect(card.getByLabel("Status: INFERRED", { exact: true })).toBeVisible()
  }
  // Plain amounts have no FieldValue status in the API: do not invent one.
  for (const [label, amount] of [["COG", "$10.00"], ["Shipping / unit", "$2.00"], ["Selling fees", "$3.00"], ["Seller proceeds", "$27.00"], ["Total landed cost", "$12.00"]]) {
    const card = economics.getByRole("article").filter({ has: page.getByText(label, { exact: true }) })
    await expect(card).toContainText(amount)
    await expect(card.getByLabel(/^Status:/)).toHaveCount(0)
  }
  const risks = page.getByRole("region", { name: "Risks", exact: true })
  for (const risk of ["HazMat", "Bulky"]) {
    await expect(risks.getByLabel(`${risk} severity provenance: INFERRED · USER_INPUT`)).toBeVisible()
  }
  const evidence = page.locator("details.evidence").filter({ has: page.getByText(/^Profit:/) })
  await evidence.locator("summary").click()
  await expect(evidence).toContainText("E2E synthetic BUY fixture (not market evidence)")
  await expect(evidence).toContainText("synthetic example: 30 - 3 - (10 + 2)")
})
