# JUVAl — Data Acquisition Matrix

**Status:** research baseline; no provider is integrated by this document.
**Scope:** supplier-catalog enrichment for Amazon sourcing decisions.
**Owner split:** backend/domain integrations are owned by Claude Code; frontend rendering is owned by Codex.
**Last researched:** 2026-08-17. Prices, entitlements and rate headers must be rechecked immediately before a procurement or implementation decision.

## 1. Purpose and non-negotiable rules

This is the source of truth for *where* JUVAl may obtain commercial data. It is deliberately not an implementation plan, vendor commitment, fee schedule, or legal opinion.

### Documentation hierarchy

| Document | Owns | Must not become |
| --- | --- | --- |
| `docs/PRODUCT_CAPABILITY_MATRIX.md` | What JUVAl should enable for an operator: purpose, priority, current backend/frontend support and data dependency. | Provider/manual/API reference. |
| **This document** | Field-level data requirement, source facts, access, status, provenance, fallback, conflicts and operational policies. | An implementation commitment or provider selection. |
| `docs/architecture/DATA_SOURCES.md` | Cross-cutting source and operational safety rules. | A duplicate field inventory. |
| Provider documentation | Vendor-specific capabilities, terms, rates and responses. | A JUVAl domain contract. |

The current capability matrix is intentionally read together with this one: “data source missing” in a capability never authorizes a source merely because it was named in a benchmark.

- A field is **not obtainable** merely because it appears on an Amazon page.
- Amazon facts, supplier declarations, account-specific outcomes, third-party observations and derived values remain separate.
- No Amazon or provider scraping is approved. `docs/architecture/DATA_SOURCES.md` already prohibits it.
- `VERIFIED` means the stated source returned the value under its documented access model; it does **not** mean the value is eternally correct or applies to every seller.
- `estimated sales`, trend, stability and any result of a JUVAl rule are **INFERRED**, never VERIFIED merely because a provider supplied a number.
- `NOT_FOUND` means a specific source/query returned no usable value. `INVALID` preserves the raw value and validation evidence. Neither means a negative business fact.

The existing domain contract is the implementation target: `FieldValue[T]` + `Provenance` (`source`, `source_type`, `verification_status`, `retrieved_at`, `method`, optional `confidence`, `evidence`, `source_reference`). See `docs/architecture/DATA_PROVENANCE.md`, `src/juval/domain/provenance.py`, and ADR-003/004. This document does not create a second provenance model.

## 2. Research method and evidence standard

Each field was assessed through: need → candidates → primary documentation → access model → documented response/model → rate/batch → public cost → freshness/history → technical policy constraints → normalization → provenance → fallback → final classification.

Primary documentation was preferred. A missing public price, quota, retention term, or live response is written as such; it is not estimated. No credentials, paid plans, signup, or live authenticated calls were used.

### Evidence ledger

| ID | Primary source | What it verifies |
| --- | --- | --- |
| A1 | [SP-API Catalog Items v2022-04-01 reference](https://developer-docs.amazon.com/sp-api/docs/catalog-items-api-v2022-04-01-reference) | Identifier search, ASIN, identifiers, summaries, dimensions, images, relationships, sales ranks; max 20 identifiers/request. The current reference and a historical throttling notice differ on the default rate; the applied response header is authoritative. |
| A2 | [SP-API Catalog Items guide](https://developer-docs.amazon.com/sp-api/lang-en_US/docs/catalog-items-api) | Seller/vendor availability, Product Listing role, NA/EU/FE coverage. |
| A3 | [SP-API onboarding](https://developer-docs.amazon.com/sp-api/docs/onboarding-overview) | Registration/authorization, roles, static sandbox, individual/batch/bulk concepts. |
| A4 | [Product Pricing `getItemOffersBatch`](https://developer-docs.amazon.com/sp-api/reference/getitemoffersbatch) | Current lowest offers, 1–20 requests/batch, default 0.1 rps / burst 1. |
| A5 | [Product Pricing `getCompetitiveSummary`](https://developer-docs.amazon.com/sp-api/reference/getcompetitivesummary) | Featured buying options/current competitive summary, default 0.033 rps / burst 1. |
| A6 | [Featured Offer Expected Price batch](https://developer-docs.amazon.com/sp-api/reference/getfeaturedofferexpectedpricebatch) | Account/SKU-specific expected featured-offer price; up to 40; default 0.033 rps / burst 1; not a guarantee. |
| A7 | [Product Fees `getMyFeesEstimates`](https://developer-docs.amazon.com/sp-api/reference/getmyfeesestimates) and [ASIN estimate guide](https://developer-docs.amazon.com/sp-api/lang-en_EN/docs/get-product-fee-estimates-asin) | Official seller fee estimates; seller authorization and Pricing/Product Listing roles. |
| A8 | [Listings Restrictions rate limits](https://developer-docs.amazon.com/sp-api/lang-tr_TR/docs/listings-restrictions-api-rate-limits) | Account-specific restriction request: default 5 rps/account-app, 100 rps/application, burst 10. |
| A9 | [FBA Inbound Eligibility reference](https://developer-docs.amazon.com/sp-api/lang-pt_BR/reference/getitemeligibilitypreview) and [role mapping](https://developer-docs.amazon.com/sp-api/lang-fr_FR/docs/role-mappings) | Account-specific inbound/commingling preview; Amazon Fulfillment role; default 1 rps / burst 1. |
| A10 | [FBA report type values](https://developer-docs.amazon.com/sp-api/lang-en_EN/docs/report-type-values-fba) | Seller-inventory reports can expose size tier, storage fee and dangerous-goods storage type; they are not catalog-wide sourcing data. |
| A11 | [Keepa official API model](https://github.com/keepacom/api_backend/blob/master/src/main/java/com/keepa/api/backend/structs/Product.java), [request model](https://github.com/keepacom/api_backend/blob/master/src/main/java/com/keepa/api/backend/structs/Request.java), and [offer model](https://github.com/keepacom/api_backend/blob/master/src/main/java/com/keepa/api/backend/structs/Offer.java) | Candidate paid product/history/offer data; identifiers, parent ASIN, product/history requests, update age and offer-history caveats. |
| A12 | [Amazon Creators API introduction](https://affiliate-program.amazon.com/creatorsapi/docs/en-us/introduction) | Catalog-oriented affiliate API, requires Associates enrollment, qualifying sales and credentials; not selected for seller-account decisions. |
| A13 | [Amazon seller pricing](https://sell.amazon.com/pricing?mons_sel_locale=en_US) | Public seller-plan reference only; it is not a programmatic per-ASIN fee calculator. |
| A14 | [SellerAmp pricing](https://selleramp.com/pricing/) and [lookup allocation help](https://support.selleramp.com/portal/en/kb/sign-up-for-sas) | Benchmark-tool commercial pricing/lookup allocation; no documented integration API was found in this research. |

`x-amzn-RateLimit-Limit`, when returned by SP-API, is authoritative for the account/application actually making a call. Published defaults are planning baselines only.

## 3. Recommended source architecture — **proposed, not approved**

1. **Supplier file / supplier-authorized feed** is authoritative for offer identity, COG, supplier shipping and supplier-declared package facts.
2. **Amazon SP-API Catalog Items** is the preferred official source for catalog identity and current catalog facts after seller authorization is available.
3. **Amazon SP-API Product Pricing, Product Fees, Listings Restrictions and FBA eligibility** are preferred for current/account-specific commercial feasibility. They must run for the authorized seller and marketplace.
4. **A licensed historical provider (Keepa is the researched candidate)** is required for price/BSR/offer history. Its contract, token pricing, retention/reuse rights and actual payload must be verified before selection.
5. **Derived JUVAl values** only consume explicitly sourced inputs and preserve weakest-link verification. They do not replace source facts.

This is a recommendation to evaluate, not a vendor selection. The existing `infrastructure/enrichment/` remains unimplemented.

## 4. Master data inventory

Abbreviations: **P0** core sourcing/profitability gate; **P1** strongly improves decision/risk; **P2** enrichment; **P3** optional. Impact: Display, Filter, Profitability, Risk, Decision, Future. Access: `SF` supplier file, `SP` authorized Selling Partner API, `KP` licensed Keepa candidate. “API” below means an integration not yet implemented.

### Master-row control fields

For readability, the inventory groups related fields in a cell, but every row
is governed by the following fixed schema. `Candidate / selected` never means
that a provider has been procured or approved; the selected value means only
the preferred source *if* the documented access conditions are met.

| Required control | Where it is recorded in each inventory row |
| --- | --- |
| FIELD; BUSINESS PURPOSE; CRITICALITY | `Field` and `Purpose / criticality / impact` |
| CURRENT SOURCE; PRIMARY SOURCE; SECONDARY SOURCE; SOURCE TYPE | `Current source and status` and `Candidate / selected source` |
| ACCESS MODEL; BATCH SIZE; RATE-LIMIT MODEL; FRESHNESS; HISTORY | `Access, cost, batch, freshness/history` |
| PROVENANCE RULE; FALLBACK; CONFLICT POLICY | `Provenance, validation and fallback`, plus §§10–11 |
| CURRENT STATUS | `Final status` using the controlled vocabulary in §14 |

| Field | Purpose / criticality / impact | Current source and status | Candidate / selected source | Access, cost, batch, freshness/history | Provenance, validation and fallback | Final status |
| --- | --- | --- | --- | --- | --- | --- |
| supplier_sku | Identity; P0; Display/trace | Supplier Excel; current | SF / SF | File; no external cost; catalog batch | Plain supplier identifier; non-empty + duplicate policy; no fallback | VERIFIED SOURCE |
| UPC / EAN / GTIN | Match key; P0; Filter/Decision | Supplier Excel only when supplied; EAN/GTIN column gaps exist | SF → SP Catalog identifier search / SF then SP | SP accepts UPC/EAN/GTIN, max 20 IDs; current only; rate is provider+operation and the applied header prevails | Verify checksum before query; retain raw supplier ID; no match → NOT_FOUND | MULTIPLE VALID SOURCES |
| ISBN | Matching only where product type applies; P2 | Not imported | SF → SP Catalog ISBN / SF then SP | Same Catalog constraints | Format/type validation; no ISBN on non-book is NOT NEEDED | VERIFIED SOURCE |
| supplier title / brand / category | Supplier description; P1; Display/match | SF; imported | SF / SF | File; slow-changing | `SUPPLIER_FILE`, VERIFIED only as supplier declaration; no overwrite by Amazon fields | VERIFIED SOURCE |
| COG | Profitability; P0; Profitability/Decision | SF | SF / SF | File; per catalog | Decimal/currency/non-negative validation; absent blocks profitability; no default 0 | VERIFIED SOURCE |
| supplier shipping | Profitability; P0; Profitability/Decision | SF | SF / SF | File; per catalog | Unit/currency basis must be explicit; absent requires user input, not estimate | VERIFIED SOURCE |
| supplier package weight / H/W/L | FBA cost/risk; P0/P1; Profitability/Risk | SF | SF / SF | File; slow-changing | Preserve as supplier package values; normalize lb/in; invalid raw retained; no replacement fallback | VERIFIED SOURCE |
| Amazon ASIN / marketplace | Catalog identity; P0; all | Supplier-declared ASIN may be present but not remotely confirmed | SP Catalog search/get / SP | Seller/vendor + Product Listing role; marketplace required; current only | Exact identifier candidate becomes VERIFIED only after deterministic reconciliation; no result → NOT_FOUND | VERIFIED SOURCE (after authorized query) |
| Amazon title / brand / category / product type | Match confirmation, display; P1 | No Amazon source current | SP Catalog summaries/attributes/classifications / SP | Catalog current response; up to 20 identifiers/search; rate is operation-specific and header-controlled | Store separately from supplier declarations; source response reference + marketplace | VERIFIED SOURCE |
| Amazon images | Display/enrichment; P3 | None | SP Catalog `images` / SP | Current; URL only, no automatic download | `OFFICIAL_API`; allow missing; policy before asset storage | VERIFIED SOURCE |
| Parent/child ASIN, variation family, attributes | Variation risk; P1; Risk/Filter | None | SP Catalog `relationships` / SP | Current; operation-specific rate and applied header control | Preserve parent/children/theme and marketplace; no relation is not necessarily invalid | VERIFIED SOURCE |
| Matching by UPC/EAN/GTIN/ISBN | High-precision candidate generation; P0 | Not performed | SP Catalog IDs / SP | 20 IDs/request; identifier type mandatory | Exact identifier + catalog response; if multiple candidates, do not auto-choose without policy | VERIFIED SOURCE |
| Matching by supplier SKU | Seller listing lookup; P1 | Not performed | SP Catalog `SKU` + sellerId / SP | Account-specific; sellerId required | Only verifies the authorized seller's SKU mapping; not universal supplier-SKU matching | ACCOUNT-SPECIFIC |
| Matching by title + brand + model/MPN | Candidate discovery; P1 | Not performed | SP Catalog keyword search, supplier facts / SP + derived resolver | No documented exact precision/recall; result may be paginated | Candidate generation is VERIFIED source data; final selected match is INFERRED until business-approved deterministic policy/evidence | BUSINESS DECISION REQUIRED |
| Current price / Buy Box price | Profitability; P0; Profitability/Decision | Supplier manual observation may exist | SP Pricing current summary/offers / SP | Account authorization; low throughput; current snapshot, no history | Capture condition, marketplace, fulfillment, timestamp; no current price → NOT_FOUND, never prior price as current | VERIFIED SOURCE |
| Lowest FBA / FBM offer | Profitability/competition; P0/P1 | None | SP `getItemOffersBatch` / SP | 1–20 ASINs; default 0.1 rps; output is lowest offers | Persist condition + fulfillment selector; API response proves observed offer, not global price history | VERIFIED SOURCE |
| Buy Box seller / fulfillment / Amazon owns Buy Box | Competition/risk; P1; Risk/Decision | None | SP competitive summary/offers; KP candidate history / SP now, KP history | Competitive Summary 0.033 rps default; exact seller visibility/payload must be validated with authorized account | Current observation VERIFIED; Amazon-owned flag only when seller identity has documented mapping; missing ≠ no Amazon | VERIFIED SOURCE for current; PAID SOURCE REQUIRED for history |
| Buy Box history / percentage | Risk/price stability; P1/P2 | None | KP candidate / KP | Paid entitlement/token cost and retention not publicly verified | Historical provider observations VERIFIED as provider observations; percentage/aggregation INFERRED; fallback NOT_FOUND | PAID SOURCE REQUIRED |
| Historical price / trend / stability | Profitability/risk; P1 | None | KP candidate; JUVAl own future snapshots / KP then own store | Keepa request model supports history/stats/update; public price/quota unavailable | Raw time series VERIFIED from licensed source; trend/stability INFERRED with method/window; otherwise NOT_FOUND | PAID SOURCE REQUIRED |
| Current BSR + BSR category | Demand; P1; Filter/Future Decision | None | SP Catalog `salesRanks` / SP | Current snapshot; applied rate header controls | Market/category/timestamp mandatory; BSR is fact at retrieval, not sales | VERIFIED SOURCE |
| BSR history / rank drops | Demand; P1 | None | KP candidate; own future snapshots / KP | Keepa model supports history; completeness/freshness must be contract-tested | Provider time series VERIFIED as observed; rank-drop count INFERRED from explicit window; fallback NOT_FOUND | PAID SOURCE REQUIRED |
| Estimated monthly/daily sales, velocity, trend, seasonality | Demand; P1/P2; Filter/Future Decision | None | Derived from licensed history; possible provider estimate / derived | Amazon does not expose market-wide sales here; method/accuracy not established | Always INFERRED, with window/method/inputs/confidence; no estimate is safer than invented estimate | DERIVED |
| Offer count / FBA count / FBM count | Competition; P1; Filter/Future Decision | None | SP Pricing offers/competitive summary; KP history candidate / SP current | Offers batch 20 at 0.1 rps; exact total-count coverage per response must be live-validated | Current count VERIFIED only for documented condition/fulfillment scope; history requires licensed source | VERIFIED SOURCE current; PAID SOURCE REQUIRED history |
| Seller identities | Competition; P2 | None | SP offer response where returned; KP offers candidate / conditional | Subject to payload, license and relevance; Keepa warns offers can be stale/incomplete | Do not infer all sellers from top offers; retain last-seen; absent remains NOT_FOUND | BLOCKED pending payload/license validation |
| Competition trend / seller count history | Competition; P2 | None | KP candidate / KP | History can have gaps; offers can be incomplete/outdated per provider model | Time series observation vs derived trend separate; fallback NOT_FOUND | PAID SOURCE REQUIRED |
| Referral fee | Profitability; P0 | User/API input today; no schedule source | SP Product Fees estimate; official public schedules as reference / SP | Seller auth; API cost not publicly verified | Estimate at a stated price and fulfillment; retain response + currency; do not hardcode rates | ACCOUNT-SPECIFIC |
| FBA fulfillment fee | Profitability; P0 | User/API input today | SP Product Fees; seller FBA fee-preview report for own offers / SP | API authorization; FBA report only own active inventory and daily constraints | Fee estimate VERIFIED for the queried seller/price/time, not permanent | ACCOUNT-SPECIFIC |
| Closing / storage / aged-inventory / inbound-placement / prep / other fees | Profitability; P0/P1 | Manual inputs, not source-connected | SP fee estimate + account FBA reports; user configuration / mixed | Storage/aged fees require inventory/account context; prep and inbound placement may be user/account policy | Separate Amazon-observed fee from user cost; unknown must block/flag applicable calculation | ACCOUNT-SPECIFIC / BUSINESS DECISION REQUIRED |
| FBA profit / ROI | Core decision; P0 | Existing deterministic engine | Derived from verified/inferred inputs / derived | No external endpoint | `CALCULATED`; weakest-link provenance; missing critical input → NOT_FOUND | DERIVED |
| FBM profit / ROI | Alternative fulfillment decision; P1 | No dedicated model/source | Seller-entered shipping/handling/returns + marketplace price / business config | Carrier rates and account policy not researched as one source | Requires explicit FBM cost model and seller settings; do not reuse FBA fee | BUSINESS DECISION REQUIRED |
| Amazon item vs package dimensions / package weight | Fees, bulky; P0 | Supplier dimensions only | SP Catalog dimensions (`item`, `package`) / SP | Current catalog data; applied rate header controls | Store Amazon item and package values separately from supplier values; normalize lb/in; record divergence | VERIFIED SOURCE |
| Amazon size tier / oversize/bulky | Risk/fees; P1 | Current Excel bulky flag only | Seller FBA reports for own inventory; derive only after approved rule / SP + derived | `product_size_tier` appears in FBA reports, not catalog-wide; source is account inventory | Size tier is account/product context; bulky policy must not be silently equated to Amazon tier | ACCOUNT-SPECIFIC / BUSINESS DECISION REQUIRED |
| Supplier-declared HazMat | Risk; P1 | Excel boolean | SF / SF | File | Supplier declaration can be VERIFIED as a declaration, not Amazon dangerous-goods approval; severity remains separate provenance | VERIFIED SOURCE |
| Amazon dangerous-goods/HazMat status | FBA eligibility/risk; P1 | None | FBA storage report for seller inventory; inbound eligibility; selected SP payloads / SP | Account/inventory dependent; no verified public catalog-wide endpoint identified | Treat FBA dangerous-goods storage type as account-specific observation. Do not derive a universal HazMat boolean from it. | ACCOUNT-SPECIFIC |
| JUVAl HazMat policy/severity | Risk/Decision; P0 once adopted | Provisional existing mapping only | Business-approved policy / derived | No source can decide JUVAl severity | Presence and severity are separate (`ADR-020`); no default policy expansion | BUSINESS DECISION REQUIRED |
| Seller eligibility to list | Go/no-go; P0 | None | SP Listings Restrictions / SP | Seller authorization + Product Listing role; per-ASIN request; documented defaults and applied header must be recorded per operation | Empty restriction list is a result for the specified context, not a global claim; recheck near listing | ACCOUNT-SPECIFIC |
| FBA inbound / commingling eligibility | Go/no-go; P0/P1 | None | SP FBA Inbound Eligibility / SP | Amazon Fulfillment role; 1 rps; single preview | Record preview type, seller, marketplace, reason codes and retrieval time; no batch documented | ACCOUNT-SPECIFIC |
| Brand/category/ASIN restriction, approval-required | Go/no-go; P0 | None | SP Listings Restrictions / SP | Same as eligibility | Restriction reason/action links are evidence; never infer eligibility from listing existence | ACCOUNT-SPECIFIC |
| Meltable/adult/restricted product | Risk; P1 | None | Account restrictions where returned; product-type/policy review / mixed | No single catalog-wide verified source identified | Preserve individual risk types; source absence is UNKNOWN/NOT_FOUND, not ABSENT | BLOCKED |
| IP complaint / enforcement / trademark risk | Risk; P1/P2 | None | Official trademark registries may support a specific trademark query; no reliable product-level complaint history found / none selected | No documented authorized market-wide complaint signal located | Do not produce an IP score. Brand match is not complaint risk. | NOT FOUND / BUSINESS DECISION REQUIRED |

## 5. ASIN matching: confidence, false-positive control and batch

| Method | Candidate source | Precision / recall position | Batch | Final match status |
| --- | --- | --- | --- | --- |
| Exact UPC/EAN/GTIN/ISBN | SP Catalog identifier search | Highest expected precision, but multi-result/packaging collisions remain possible; recall depends on catalog identifier coverage | 20 identifiers/request | Candidate source VERIFIED; automatic selection requires collision policy. |
| Existing ASIN | SP `getCatalogItem` | Exact identity verification for a syntactically valid supplied ASIN; does not prove supplier item equivalence | Single ASIN; operation-specific rate and applied header control | VERIFIED catalog existence; supplier-to-ASIN equivalence still needs evidence. |
| Seller SKU | SP Catalog SKU + `sellerId` | Only maps an authorized seller's SKU; not a supplier SKU lookup | API constrained/account-specific | ACCOUNT-SPECIFIC. |
| Title + brand + model/MPN | Catalog keyword search plus supplier values | Better recall, material false-positive risk, especially variants/bundles | Keyword pagination; no safe automated matching policy documented | Candidate discovery only; selected match remains INFERRED. |

**Required future matching policy (business/architecture decision):** exact ID with one candidate may be auto-accepted only after package quantity/brand/title guard checks; multiple candidates, mismatch, or keyword-only candidates require review. Store every candidate ASIN, match method, source request ID/reference, normalized comparison fields, score and rejection reason. A numeric confidence is informational; it cannot substitute for `VerificationStatus`.

## 6. Provider comparison

| Provider | Available data / US coverage | Auth model | Public price | Rate/batch | History/freshness | Reliability, terms and lock-in |
| --- | --- | --- | --- | --- | --- | --- |
| Supplier catalog/feed | Supplier SKU, IDs, descriptive facts, COG, shipping, declared dimensions/HazMat; supplier-specific | Supplier file/feed authority | Contract-specific | File batch; no API guarantee | At catalog issuance; no inherent history | Strong for supplier facts, never proof of Amazon facts; supplier format/quality risk. |
| Amazon SP-API | US (and NA/EU/FE documented) catalog, current ranks, current offers/competitive info, fees, restrictions, FBA eligibility | Registered/authorized seller or vendor; required roles | API operational pricing not confirmed publicly; seller plan page public but not an API price model | Per operation, headers authoritative; Catalog supports up to 20 identifier inputs; pricing/fees are operation-specific | Current snapshot; account reports have stated schedules; no market history service | Official/high authority, but account authorization and operation-specific access; vendor lock-in to Amazon. |
| Keepa API candidate | Product identity, parent, historical price/rank and optional offers/stats suggested by official API model; US domain supported by product locale model | Paid API key/entitlement required | **PRICE NOT PUBLIC in verifiable primary source** | Request model says up to 100 product codes in a request; token/refill and actual quota require account validation | Historical payload exists; offer model warns gaps/stale/incomplete offers | Established specialized provider, but proprietary schema/tokens/retention contract create lock-in. |
| SellerAmp SAS | End-user research tool advertises fees, eligibility/IP alerts, historical price/sales charts and Buy Box analysis | Subscription / lookup allocation | Public subscription tiers and 1,000-or-unlimited lookup allocations are published | No documented provider API/batch contract was found | Product feature claims are not a reusable data contract | Useful functional benchmark only; do not integrate, scrape, proxy or treat it as a source. |
| Amazon Creators API | Catalog/search/variations/browse nodes for affiliate product discovery | Associates enrollment, qualifying sales, credentials | Program/contract dependent | API reference must be checked post-onboarding | Not selected for seller account/fees/restrictions | Not appropriate primary source for seller eligibility or FBA economics; affiliate license constraints. |
| Public Amazon webpages / scraping | Apparent product facts | None/unstable | N/A | N/A | Unreliable | **Rejected:** prohibited by project source policy; legal/ToS, blocking and maintenance risk. |

## 7. Public / paid / account-specific matrix

| Classification | Fields |
| --- | --- |
| FREE / official but authorized | SP Catalog current ASIN/IDs/title/brand/category/images/relationships/dimensions/current BSR; access still needs seller/vendor authorization and role. |
| PAID SOURCE REQUIRED | Historical price, Buy Box, BSR, offer/seller-count history; third-party sales estimates; historical competition. Keepa is researched but not selected. |
| ACCOUNT-SPECIFIC | Seller listing eligibility/restrictions, FBA inbound/commingling eligibility, fees, own FBA size/storage/dangerous-goods reports, FOEP, seller SKU mapping. |
| DERIVED | Profit/ROI, price trend/stability, sales velocity/estimates, rank drops, competition trend, any bulky classification after approved policy. |
| UNAVAILABLE / no reliable product-level source found | Market-wide IP complaint/enforcement risk; complete public seller universe/history; a universal account-independent eligibility verdict. |

## 8. Cost and throughput model

### Cost model

No numeric third-party cost is invented. Therefore the 1K/10K/100K rows below are a valid **not calculable** result until vendor quotes/portal pricing and terms are captured.

| Source / operation | 1K one-time | 10K one-time | 100K one-time | Daily / weekly / monthly refresh |
| --- | --- | --- | --- | --- |
| Supplier file | No verified external per-item price; supplier agreement governs | Same | Same | New catalog cadence; no independent refresh assumed. |
| SP-API Catalog / Pricing / Fees / Restrictions | API fee model **PRICE NOT PUBLIC / account required**. Do not allocate a fabricated $/ASIN. | Same | Same | Compute only after authorization/usage plan and account costs are approved. Public seller plan reference is not a JUVAl API unit cost. |
| Keepa candidate | **PRICE NOT PUBLIC / account or sales contact required**; token cost unknown | Same | Same | Cannot price daily/weekly/monthly without verified plan, token consumption and license. |
| JUVAl derived values | No external per-item charge once inputs are available | Same | Same | Storage/compute cost is outside this research; refresh follows source snapshots. |

### Throughput lower bounds (not SLA)

| Operation | Documented default | Effective product ceiling | 1K | 10K | 100K | Limitation |
| --- | --- | --- | --- | --- | --- | --- |
| SP Catalog identifier search | Current reference says 5 rps; historical official notice says 2 rps; 20 IDs/request | 40–100 IDs/s | 10–25 s | 1 m 40 s–4 m 10 s | 16 m 40 s–41 m 40 s | Applied header wins; pagination, retries and collisions reduce throughput. |
| SP Product Fees batch | 0.5 requests/s; up to 20 products/batch | 10 products/s | 1 m 40 s | 16 m 40 s | 2 h 47 m | Estimate is seller/price/context specific and not guaranteed actual fee. |
| SP Item Offers batch | 0.1 requests/s; 20 items/batch | 2 ASIN/s | 8 m 20 s | 83 m 20 s | 13 h 53 m | Current lowest offers, not complete history. |
| SP Competitive Summary | 0.033 requests/s; batch size must be rechecked from current request schema | Unknown | Not calculable honestly | Not calculable honestly | Not calculable honestly | Do not assume items/request from endpoint name. |
| SP Featured Offer Expected Price | 0.033 requests/s; 40 requests/batch | 1.32 SKUs/s | 12 m 38 s | 2 h 6 m | 21 h 3 m | Seller SKU/account-specific and expected, not guaranteed Buy Box. |
| SP Listings Restrictions | 5 requests/s; no batch operation documented | 5 ASIN/s | 3 m 20 s | 33 m 20 s | 5 h 33 m | Per seller/account context. |
| SP FBA eligibility preview | 1 request/s; no batch documented | 1 ASIN/s | 16 m 40 s | 2 h 47 m | 27 h 47 m | Per seller/account context. |
| Keepa candidate | Token/refill/quota not independently public-verified | Unknown | BLOCKED | BLOCKED | BLOCKED | Must validate paid account documentation/sample first. |

### Normative rate-limit and batch policy

Rate limiting is scoped to **provider + operation**, never “Amazon” or a whole run. For every enabled operation, record documented default, observed `x-amzn-RateLimit-Limit` when supplied, batch size, burst, concurrency and retry result. The observed header prevails over a documented default; no adapter may scatter fixed `sleep` calls.

| Outcome | Required handling | Never classify as |
| --- | --- | --- |
| 429 | Throttled; bounded retry/backoff under the operation policy, then operational failure | `NOT_FOUND` |
| 5xx / timeout | Source failure; retry under policy, retain attempt evidence | `NOT_FOUND` |
| LWA/auth failure | Configuration or authorization failure; do not retry blindly | `NOT_FOUND` |
| Malformed provider response | Source/schema failure; preserve sanitized diagnostic evidence | `NOT_FOUND` |

Batching is used only where provider documentation explicitly supports it. Catalog identifier search is up to 20 homogeneous identifiers; Product Fees batch is up to 20 products; no batch is assumed for Listings Restrictions or FBA eligibility. Provider documentation, not an endpoint name, is evidence for batch behavior.

## 9. Freshness, cache and history policy — conceptual only

| Class | Fields | Proposed refresh / storage behavior |
| --- | --- | --- |
| STATIC / slow-changing | Supplier SKU, validated identifiers, brand, Amazon catalog relationships, package dimensions | Keep source snapshots; refresh on new supplier catalog, match conflict, or periodic catalog check. |
| DAILY | BSR, catalog updates, fees at a selected price, restrictions when catalog is screened | Cache a timestamped snapshot; rescreen before irreversible action. |
| INTRADAY | Current price, Buy Box, offer counts, competition | Query close to profitability/decision time; do not reuse a stale observation as “current.” |
| REAL-TIME / account event | Listing eligibility, inbound eligibility, FOEP | Query at the seller action boundary; source only applies to that seller/context/time. |
| HISTORICAL | Price/BSR/Buy Box/offers | Licensed history source or JUVAl-collected snapshots; preserve provider timestamps and gaps. |

No cache implementation is approved here. Retention, refresh windows, storage permission and marketplace scope must be verified for the selected provider before implementation.

## 10. Normalization, provenance and data quality contract

### Normalization

- Preserve `supplier_*` and `amazon_*` facts as separate logical values. Do not overwrite supplier weight/dimensions/title with catalog values.
- Normalize weights to lb and dimensions to in using existing `domain.units`; retain original source/unit in evidence where possible.
- Money always records marketplace/currency, condition, fulfillment channel and the exact price basis (listing, shipping, landed, Buy Box, lowest offer).
- Catalog fields include marketplace, ASIN, included-data set, response/request reference and retrieval time.
- Identifier matching retains raw ID, normalized ID, query type, candidate count and acceptance/rejection evidence.

### Status rules

| Outcome | Required evidence |
| --- | --- |
| VERIFIED | Source response/supplier file is authorized for that fact; value validates; source, method, marketplace/account scope and retrieval time recorded. |
| INFERRED | Explicit rule/model/window/input references and optional confidence. Examples: sales estimate, price trend, rank drops, future bulky policy. |
| NOT_FOUND | A documented source/query was tried and produced no usable value; retain request/response reference and timestamp. |
| INVALID | Source supplied a value that fails format/range/consistency validation; preserve `raw_value` plus reason. |

`RiskFlag` needs two distinct provenance tracks: risk **presence** versus policy **severity** (ADR-020). A source finding `IsHazmat` does not prove the severity JUVAl assigns. `INVALID` must never be collapsed into `NOT_FOUND`.

## 11. Fallback and conflict policy — proposed for approval

| Data family | Primary | Secondary | Derived fallback | No-data behavior / conflict |
| --- | --- | --- | --- | --- |
| Supplier facts/COG/shipping | Supplier file/feed | User correction with provenance | None | Missing COG/shipping blocks profitability; never assume zero. |
| ASIN | SP exact identifier search | Supplier ASIN verified through SP | Title/brand/model candidate ranking | No accepted candidate → NOT_FOUND/ASIN unresolved; never select first keyword hit. |
| Catalog facts | SP Catalog | Licensed provider only after field-level validation | None | Retain both values and mark divergence; source context selects display/use. |
| Current price/competition | SP Pricing | Licensed provider snapshot (not “current” unless timestamp satisfies policy) | None | NOT_FOUND; no demo or last known value as current. |
| History | Licensed provider | JUVAl own collected snapshots | Windowed calculation | NOT_FOUND if no licensed/collected history. |
| Fees/eligibility | Authorized seller SP-API | User-provided configuration only where domain allows | None | Account-specific NOT_FOUND/ERROR blocks relevant decision rather than claiming universal eligibility. |
| Weight/dimensions | Supplier package value for supplier shipping; Amazon package value for Amazon fee context | Other authorized source after validation | Approved conversion only | Retain both; divergence is a data-quality flag, not automatic overwrite. |
| HazMat/bulky | Supplier declaration / account Amazon observation | Authorized product compliance source if approved | Approved policy only | UNKNOWN or NOT_FOUND, not ABSENT. |

**Conflict rule:** retain both source facts, choose only by an explicit context rule, and surface material divergence. Price conflicts are normally timestamps/condition/fulfillment differences; dimension conflicts may change fees; HazMat conflicts must escalate to risk review. No precedence order is approved by this research.

## 12. Legal and technical access constraints (not legal advice)

- SP-API requires registration, authorization and operation roles; use the documented OAuth/authorization model and actual rate headers. See [onboarding](https://developer-docs.amazon.com/sp-api/docs/onboarding-overview).
- Listings restrictions, FBA eligibility, fees, inventory reports and FOEP are seller/account-context observations. They must not be redistributed or represented as universal catalog facts without confirming the applicable agreement.
- Creators API is an affiliate/catalog product API whose documentation requires Associates enrollment, qualifying sales and credentials. It is not selected as a substitute for seller eligibility/fees.
- Keepa license, commercial-use scope, retention, redistribution, token price and data freshness must be reviewed in its current paid agreement before procurement or implementation; this research did not find a primary public pricing/terms page sufficient to approve them.
- Scraping Amazon, Keepa or competitor pages is rejected by `DATA_SOURCES.md`: legal/ToS risk, blocking risk, brittle structure and ongoing maintenance burden.

## 13. Live validation

| Source | Live request | Result |
| --- | --- | --- |
| SP-API | Not attempted: no seller authorization, role grant or secret was used | **AUTH REQUIRED**. Documentation establishes request/response families only. |
| Keepa | Not attempted: no key, plan or purchase | **AUTH / PAID PLAN REQUIRED**. Official model establishes candidate fields, not JUVAl entitlement. |
| Creators API | Not attempted: no Associate credentials | **AUTH REQUIRED**. Not selected for core seller data. |

The sample XLSX in `tests/fixtures/sample_sourcing_TEST_DATA.xlsx` remains technical test data, not evidence of external market facts.

## 14. Unresolved data and required decisions

### Controlled status vocabulary

`IMPLEMENTED`, `VERIFIED SOURCE`, `DOC VERIFIED`, `AUTH BLOCKED`, `LIVE VALIDATION BLOCKED`, `PAID SOURCE REQUIRED`, `ACCOUNT-SPECIFIC`, `DERIVED`, `BUSINESS DECISION REQUIRED`, `NOT FOUND`, and `NOT NEEDED` are the acquisition statuses used by this document. SP-API onboarding may additionally use `UNDER REVIEW`, `NOT CREATED`, `NOT PERFORMED` and `NOT AVAILABLE`; these describe Amazon onboarding state, never field provenance or an operational result. A combined label may retain two facts (for example, `VERIFIED SOURCE current; PAID SOURCE REQUIRED history`); it never hides an operational failure as a data result.

1. **Vendor selection/procurement:** whether a licensed history provider is approved, including Keepa vs alternatives, price, tokens, data rights, retention, coverage and live sample validation.
2. **ASIN collision/match acceptance policy:** especially packs, variations and keyword candidates.
3. **FBA/FBM economic model:** explicit account/user inputs, which fees are queried, and when a missing fee blocks a decision.
4. **Bulky/oversize policy:** distinguish supplier measurements, Amazon tier and JUVAl decision policy; do not equate them.
5. **HazMat policy/severity:** source hierarchy and severity taxonomy require business approval; current provisional mapping is not approval.
6. **IP risk model:** no reliable product-level complaint/enforcement source was verified; do not build a score without an approved business model and lawful source.
7. **Retention/cache policy:** set only after selected vendor terms and data-use constraints are verified.

### Unified unresolved decisions register

| Decision | Why required | Blocks | Current state/default | Owner | Status |
| --- | --- | --- | --- | --- | --- |
| AMBIGUOUS matching model | `VerificationStatus` cannot represent multiple candidates honestly | Exact identifier matcher | Do not select; do not call it NOT_FOUND | Domain/product | PENDING DECISION |
| HazMat severity | Presence and severity are distinct; current mapping is provisional | Automated risk/decision policy | `HAZMAT → HIGH` provisional | Business/domain | BUSINESS DECISION REQUIRED |
| Bulky severity | Same separation and policy issue | Automated risk/decision policy | `BULKY → MEDIUM` provisional | Business/domain | BUSINESS DECISION REQUIRED |
| Historical provider | History needs a licensed source | Price/BSR/Buy Box/competition history | Keepa is candidate, not selected | Product/procurement | PAID SOURCE REQUIRED |
| Queue technology | Enrichment must survive browser/process lifecycle | Scalable enrichment execution | No technology selected | Architecture/backend | PENDING DECISION |
| Enrichment DAG | Prevent needless calls and define partial results | Orchestration/stages | Conceptual only | Architecture/product | TO BE FORMALIZED IN ADR |
| Decision Score | Formula and business thresholds are not approved | Score as decision input | Framework exists; use deferred | Business/domain | BUSINESS DECISION REQUIRED |
| Sales-estimate methodology | Estimates are not source facts | Demand enrichment | Must remain INFERRED | Product/data | BUSINESS DECISION REQUIRED |
| IP-risk model | No reliable lawful product-level source verified | IP risk score/automation | Do not score | Business/legal/product | NOT FOUND |
| Eligibility scope | Eligibility is seller + marketplace + context specific | Can-I-sell claims | Use account-specific result only | Product/domain | BUSINESS DECISION REQUIRED |

## 15. Data-readiness conclusion

| Area | Readiness |
| --- | --- |
| Supplier ingestion and provenance | Ready today; coverage is limited to supplier-provided fields. |
| Official catalog identity/current catalog facts | Verified source exists, but integration/authentication is pending. |
| Current account-specific sourcing feasibility | Verified official source families exist, but require seller authorization/roles and throughput design. |
| Price/BSR/Buy Box/competition history | Paid source required; no provider selected or price/rights validated. |
| Sales estimate/trend | Derived only; method and validation policy pending. |
| IP risk / universal restrictions | Not found as a reliable universal source; business model required. |

**Estimated data-readiness:** supplier-core is usable now; a defensible current-sourcing enrichment vertical slice is blocked on SP-API approval/authorization; historical intelligence is blocked on a licensed-provider procurement and validation decision. No source was selected by intuition.

## 16. Relationship to existing capability matrix

`docs/PRODUCT_CAPABILITY_MATRIX.md` is currently an untracked concurrent-work file. To avoid overwriting work outside this research task, it was inspected but intentionally not edited. Once its owner stages it, reconcile its “External Data Source Roadmap” and this authoritative acquisition matrix in a deliberate documentation-only change.

## 17. SP-API Catalog / ASIN matching POC — 2026-08-17

### Status

| Checkpoint | Status | Evidence |
| --- | --- | --- |
| SP-API Catalog documentation | **DOC VERIFIED** | Catalog Items `searchCatalogItems` accepts UPC/EAN/GTIN identifiers, up to 20 identifiers per request; Catalog Items requires Product Listing role. See A1/A2. |
| Developer registration | **REJECTED_REMEDIATION_REQUIRED** | Amazon decision dated 2026-08-17: **NOT ELIGIBLE FOR SP-API ACCESS**. Reapplication requires an updated Developer Profile and a new case; do not reopen the prior case. JUVAl remains a **PRIVATE DEVELOPER** for internal use by its own organization and own seller account. |
| Production application client | **NOT CREATED** | No production application client exists. Creation remains blocked until remediation, reapplication and Amazon approval. |
| Self-authorization | **NOT PERFORMED** | It cannot occur until Amazon approves a reapplication and a production client exists. |
| Credentials | **NOT AVAILABLE** | No LWA client ID, LWA client secret or refresh token exists for JUVAl. No credential was requested, read or used. |
| Live Catalog call / rate-limit header | **LIVE CALL BLOCKED** | No authenticated call was attempted; `x-amzn-RateLimit-Limit` therefore has not been observed. The blocker is remediation, reapplication and Amazon approval. |
| Adapter, provider port and tests | **NOT STARTED BY DESIGN** | This POC must not create a production adapter or mock authentication before real authorization exists. |

### Access model for the US Catalog POC

- **Application type:** use a **private application** only if JUVAl is initially used solely by its own organization. A private application self-authorizes and does not need an Appstore listing. If JUVAl will authorize independent seller organizations, stop and register a **public application** with the OAuth/Appstore authorization flow instead. This is an ownership/business decision, not a code shortcut.
- **Required role:** `Product Listing` for `searchCatalogItems` and `getCatalogItem` (A2). Pricing, Fees, restrictions and FBA roles are explicitly out of this POC.
- **Authorization:** Catalog Items is not grantless. Use the authorized selling partner's LWA refresh token to exchange for a short-lived LWA access token. `client_credentials` scopes are for grantless operations and are not a substitute for this call.
- **US marketplace:** `ATVPDKIKX0DER`; NA endpoint `https://sellingpartnerapi-na.amazon.com`; region `us-east-1` (A1 and [Marketplace IDs](https://developer-docs.amazon.com/sp-api/lang-zh/docs/marketplace-ids)).
- **AWS signing:** current Amazon documentation states that AWS IAM and SigV4 have not been required since 2023-10-02. Do not create IAM keys or a SigV4 implementation for this POC. LWA remains required ([Amazon announcement](https://developer-docs.amazon.com/sp-api/changelog/sp-api-will-no-longer-require-aws-iam-or-aws-signature-version-4)).
- **Request headers:** obtain an LWA token at runtime and use the documented `host`, `x-amz-access-token`, `x-amz-date` and `user-agent` headers. Never send a token to the browser.

### Onboarding gates — next external actions

1. **GATE 1:** Remediate and evidence the Amazon registration findings, update the Developer Profile truthfully and submit a **new** case. Do not reopen the prior case or treat `REJECTED_REMEDIATION_REQUIRED` as approval. See `compliance/SP_API_REGISTRATION_REMEDIATION.md`.
2. **GATE 1A:** Amazon approves the new developer-registration submission.
3. **GATE 2:** Create the minimum-privilege JUVAl production application client.
4. **GATE 3:** Verify the exact roles required against current official SP-API documentation before selecting them.
5. **GATE 4:** Self-authorize against Juval Logistics' own US Seller account.
6. **GATE 5:** Store `JUVAL_SP_API_LWA_CLIENT_ID`, `JUVAL_SP_API_LWA_CLIENT_SECRET` and `JUVAL_SP_API_REFRESH_TOKEN` only in a backend-only secret store; never use `VITE_*` names and never commit them to Git. Do not transmit their values in chat, source code or frontend configuration.
7. **GATE 6:** Perform one minimal authenticated Catalog Items validation using a public/non-sensitive identifier and record only sanitized metadata: HTTP status, request ID, returned ASIN(s), marketplace, identifier type and `x-amzn-RateLimit-Limit` if supplied.
8. **GATE 7:** Record the actual observed rate-limit metadata and reconcile it with this matrix.

Amazon documents the token exchange at `https://api.amazon.com/auth/o2/token` using the refresh token, client ID and client secret; the returned access token is short-lived. See [Connect to SP-API](https://developer-docs.amazon.com/sp-api/lang-zh_CN/docs/connecting-to-the-selling-partner-api) and [authorization workflow](https://developer-docs.amazon.com/sp-api/lang-zh_CN/docs/onboarding-step-6-set-up-the-authorization-workflow).

### Matching semantics — decision required before implementation

The existing `VerificationStatus` is intentionally exhaustive: `VERIFIED`, `INFERRED`, `NOT_FOUND`, `INVALID`. It represents the verification state of **one field value**, so it cannot truthfully encode “multiple exact candidates exist.”

| Provider result | Safe current interpretation | Required future representation |
| --- | --- | --- |
| 0 exact candidates | `asin = NOT_FOUND`, `source=AMAZON_SP_API`, `method=EXACT_IDENTIFIER_MATCH`, query evidence/timestamp retained | Existing `FieldValue.not_found` is suitable. |
| 1 candidate whose returned identifiers include the queried normalized identifier | ASIN candidate may be `VERIFIED` after the explicit exact-match guard | Existing `FieldValue.verified` is suitable; preserve request/response reference. |
| More than 1 candidate | Do not select or mark an ASIN `NOT_FOUND`; candidates exist and the field has no resolved value | **PENDING DECISION:** add a small match-result outcome such as `AMBIGUOUS` separate from `VerificationStatus`, carrying candidate ASINs/evidence. Do not alter the global provenance enum. |
| Network/auth/HTTP/schema error | Operational/source failure, never `NOT_FOUND` | **PENDING DECISION:** adapter-level typed source error plus `ProcessingIssue`; no FieldValue claim is made. |

This is an ADR candidate only if implementation begins: a match-specific result/outcome preserves ADR-004 rather than deforming it. It is not approved by this document.

### Minimal future port and adapter boundary

When authorization and the ambiguity decision exist, introduce only a catalog-focused port, for example `ProductCatalogSource.search_by_identifiers(marketplace, identifier_type, identifiers)`. It returns source observations/candidates and leaves acceptance to a matching use case. It must not include pricing, fees, history, eligibility or other product intelligence.

The SP-API adapter will batch at most 20 homogeneous identifiers, observe `x-amzn-RateLimit-Limit` when present, and expose an injectable conservative throttle value. Its cache key, if a cache is later approved, is `(marketplace, identifier_type, normalized_identifier)`; TTL remains a slow-changing-policy decision, not an implementation assumption.

Required tests after authorization/decision: exact match, zero match, multiple candidates, malformed response, source failure, provenance, 20-item batch and 21-item split. A credential-gated live integration test must stay outside the normal suite.

## 18. Incremental enrichment and PWA responsibility — architecture requirements

These are requirements for a future enrichment architecture, **not** an implementation or queue selection:

- Enrichment is asynchronous, persistently queued and idempotent by record/stage; a browser closing must not cancel a run.
- Runs must resume after restart, expose partial record/stage results, use bounded retry/backoff and support priority, conditional stages, batches, throughput monitoring and provider-operation cost/usage monitoring.
- JUVAl must account for request count, item count, retries, provider, operation, run and estimated/actual cost.
- The PWA only **observes, controls, prioritizes and displays progress**. It does not execute provider calls, own a queue, enforce provider rate limits or need to remain open.
- The conceptual dependency path is `Supplier → Identity → Catalog → eligibility/restrictions → pricing → fees → history → decision`; it is **CONCEPTUAL / TO BE FORMALIZED IN ADR**. A stage that makes a later stage inapplicable should prevent that request.

No TTL is set here. Freshness classes in §9 express refresh requirements, not a cache implementation.
