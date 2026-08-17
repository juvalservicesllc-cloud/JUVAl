import { describe, expect, it, vi } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { BrandAssetControl } from "./BrandAssetControl"

vi.mock("../theme/storage", () => ({
  validateBrandAsset: () => null,
  readBrandAsset: async () => "data:image/png;base64,AA==",
}))

describe("BrandAssetControl", () => {
  it("adds a local asset preview and removes it", async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    const { rerender } = render(<BrandAssetControl label="Workspace logo" value={null} onChange={onChange} description="Test asset" />)
    await user.upload(screen.getByLabelText("Upload"), new File(["image"], "logo.png", { type: "image/png" }))
    await waitFor(() => expect(onChange).toHaveBeenCalledWith("data:image/png;base64,AA=="))
    rerender(<BrandAssetControl label="Workspace logo" value="data:image/png;base64,AA==" onChange={onChange} description="Test asset" />)
    expect(screen.getByAltText("Workspace logo preview")).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Remove" }))
    expect(onChange).toHaveBeenLastCalledWith(null)
  })
})
