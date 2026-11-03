import { render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { expect, it } from "vitest"
import { DEMO_MARKET, MarketDemo } from "./MarketDemo"

it("keeps 90 synthetic points, visible provenance and Line/Bar with an accessible value table", async () => {
  const before = JSON.stringify(DEMO_MARKET)
  render(<MarketDemo />)
  expect(DEMO_MARKET).toHaveLength(90)
  expect(screen.getByText(/DEMO_FIXTURE · NOT VERIFIED/)).toBeVisible()
  expect(screen.getByRole("img")).toHaveAccessibleName(/90-day line chart/)
  await userEvent.setup().click(screen.getByRole("button", { name: "Bar" }))
  expect(screen.getByRole("img")).toHaveAccessibleName(/90-day bar chart/)
  expect(document.querySelectorAll("svg rect")).toHaveLength(90)
  expect(JSON.stringify(DEMO_MARKET)).toBe(before)
  await userEvent.setup().click(screen.getByText("View all 90 DEMO values"))
  expect(within(screen.getByRole("table", { name: "DEMO market values" })).getAllByRole("row")).toHaveLength(91)
})
