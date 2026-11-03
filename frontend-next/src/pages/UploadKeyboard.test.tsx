import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { expect, it, vi } from "vitest"
import { UploadPage } from "./UploadPage"

it("reaches the native file picker with Tab, retains its accessible name and queues without submitting", async () => {
  const fetch = vi.fn()
  vi.stubGlobal("fetch", fetch)
  try {
    render(<UploadPage go={vi.fn()} />)
    const user = userEvent.setup()
    await user.tab()
    const picker = screen.getByLabelText("Supplier files")
    expect(picker).toHaveFocus()
    expect(picker).toHaveAttribute("type", "file")
    await user.upload(picker, new File(["synthetic"], "keyboard.csv", { type: "text/csv" }))
    expect(screen.getByLabelText("File queue")).toHaveTextContent("keyboard.csv")
    expect(fetch).not.toHaveBeenCalled()
  } finally { vi.unstubAllGlobals() }
})
