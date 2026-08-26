import "@testing-library/jest-dom/vitest"
import { cleanup } from "@testing-library/react"
import { afterEach } from "vitest"

// `globals: false` means Testing Library cannot install its own auto-cleanup,
// so renders would accumulate across tests and every getBy* would find the
// previous test's DOM as well as this one's.
afterEach(cleanup)
