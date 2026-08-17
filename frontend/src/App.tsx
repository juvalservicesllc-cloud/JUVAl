import { BrowserRouter, Route, Routes } from "react-router-dom"
import "./App.css"
import { AppLayout } from "./components/AppLayout"
import { DashboardPage } from "./pages/DashboardPage"
import { ProductsPage } from "./pages/ProductsPage"
import { RunsPage } from "./pages/RunsPage"
import { UploadPage } from "./pages/UploadPage"

export default function App() {
  return <BrowserRouter><Routes><Route element={<AppLayout />}><Route index element={<DashboardPage />} /><Route path="upload" element={<UploadPage />} /><Route path="products" element={<ProductsPage />} /><Route path="runs" element={<RunsPage />} /></Route></Routes></BrowserRouter>
}
