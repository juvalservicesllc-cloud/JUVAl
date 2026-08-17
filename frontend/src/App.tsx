import { BrowserRouter, Route, Routes } from "react-router-dom"
import "./App.css"
import { AppLayout } from "./components/AppLayout"
import { AppearancePage } from "./pages/AppearancePage"
import { DashboardPage } from "./pages/DashboardPage"
import { ProductsPage } from "./pages/ProductsPage"
import { RunsPage } from "./pages/RunsPage"
import { UploadPage } from "./pages/UploadPage"
import { ThemeProvider } from "./theme/ThemeProvider"

export default function App() {
  return <ThemeProvider><BrowserRouter><Routes><Route element={<AppLayout />}><Route index element={<DashboardPage />} /><Route path="upload" element={<UploadPage />} /><Route path="products" element={<ProductsPage />} /><Route path="runs" element={<RunsPage />} /><Route path="appearance" element={<AppearancePage />} /></Route></Routes></BrowserRouter></ThemeProvider>
}
