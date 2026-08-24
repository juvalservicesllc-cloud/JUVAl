import { lazy, Suspense } from "react"
import { BrowserRouter, Route, Routes } from "react-router-dom"
import "./App.css"
import { AppLayout } from "./components/AppLayout"
import { DashboardPage } from "./pages/DashboardPage"
import { ProductsPage } from "./pages/ProductsPage"
import { ThemeProvider } from "./theme/ThemeProvider"

// Route-level code splitting: Upload's XLSX handling, Run Detail's results
// table, and Appearance's react-colorful picker ship as their own chunk
// instead of the initial bundle. Dashboard and Products stay eager --
// Dashboard is the index route (deferring it only moves its load delay to
// first paint), and Products is one of the two primary catalog surfaces.
const UploadPage = lazy(() => import("./pages/UploadPage").then((m) => ({ default: m.UploadPage })))
const RunsPage = lazy(() => import("./pages/RunsPage").then((m) => ({ default: m.RunsPage })))
const RunDetailPage = lazy(() => import("./pages/RunDetailPage").then((m) => ({ default: m.RunDetailPage })))
const ProductDetailPage = lazy(() => import("./pages/ProductDetailPage").then((m) => ({ default: m.ProductDetailPage })))
const BatchDetailPage = lazy(() => import("./pages/BatchDetailPage").then((m) => ({ default: m.BatchDetailPage })))
const AppearancePage = lazy(() => import("./pages/AppearancePage").then((m) => ({ default: m.AppearancePage })))

function RouteFallback() {
  return (
    <div className="status" aria-live="polite">
      <p>Loading…</p>
    </div>
  )
}

export default function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <Suspense fallback={<RouteFallback />}>
          <Routes>
            <Route element={<AppLayout />}>
              <Route index element={<DashboardPage />} />
              <Route path="upload" element={<UploadPage />} />
              <Route path="products" element={<ProductsPage />} />
              <Route path="runs" element={<RunsPage />} />
              <Route path="runs/:executionId" element={<RunDetailPage />} />
              <Route path="runs/:executionId/records/:recordRef" element={<ProductDetailPage />} />
              <Route path="batches/:batchId" element={<BatchDetailPage />} />
              <Route path="appearance" element={<AppearancePage />} />
            </Route>
          </Routes>
        </Suspense>
      </BrowserRouter>
    </ThemeProvider>
  )
}
