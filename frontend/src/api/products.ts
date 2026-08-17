import type { FieldValueOut, ProductListItem, ProductsResponse } from "../types"
import { requestJson } from "./client"

const provenanceStatuses = new Set(["VERIFIED", "INFERRED", "NOT_FOUND", "INVALID"])

function isFieldValue(value: unknown): value is FieldValueOut {
  if (!value || typeof value !== "object") return false
  const field = value as Record<string, unknown>
  return "value" in field && "status" in field
    && (field.value === null || ["string", "number", "boolean"].includes(typeof field.value))
    && (field.status === null || typeof field.status === "string" && provenanceStatuses.has(field.status))
}

function isProduct(value: unknown): value is ProductListItem {
  if (!value || typeof value !== "object") return false
  const product = value as Record<string, unknown>
  return typeof product.record_ref === "string"
    && (product.supplier_sku === null || typeof product.supplier_sku === "string")
    && isFieldValue(product.title)
    && isFieldValue(product.brand)
    && (product.cog === null || typeof product.cog === "string")
    && isFieldValue(product.asin)
    && (product.hazmat_status === null || typeof product.hazmat_status === "string")
    && (product.bulky_status === null || typeof product.bulky_status === "string")
    && (product.decision === null || typeof product.decision === "string")
}

export async function getProducts(signal?: AbortSignal): Promise<ProductsResponse> {
  const body = await requestJson("/api/v1/products", { signal })
  if (!body || typeof body !== "object" || !("items" in body) || !Array.isArray(body.items) || !body.items.every(isProduct)) {
    throw new Error("Products API returned an invalid response")
  }
  return { items: body.items }
}
