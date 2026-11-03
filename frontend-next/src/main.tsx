import { createRoot } from "react-dom/client"
import { App } from "./app/App"
import "./style.css"
import { registerPwa } from "./pwa"

createRoot(document.getElementById("root")!).render(<App />)
if (import.meta.env.PROD) void registerPwa()
