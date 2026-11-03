import { afterEach, expect, it, vi } from "vitest"
import { registerPwa } from "./pwa"
afterEach(() => vi.unstubAllGlobals())
it("registers a same-origin worker without takeover and tolerates registration failure", async () => {
  const register = vi.fn().mockResolvedValue({})
  vi.stubGlobal("navigator", { serviceWorker: { register } })
  await registerPwa()
  expect(register).toHaveBeenCalledWith("/sw.js", { scope: "/", updateViaCache: "none" })
  register.mockRejectedValue(new Error("blocked"))
  await expect(registerPwa()).resolves.toBeUndefined()
})
