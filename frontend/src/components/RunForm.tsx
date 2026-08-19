import { useState, type FormEvent } from "react"
import type { FeesIn, Severity, ThresholdsIn } from "../types"

export interface RunFormValues {
  file: File
  thresholds: ThresholdsIn
  fees: FeesIn
  persist: boolean
}

interface Props {
  disabled: boolean
  onSubmit: (values: RunFormValues) => void
}

const SEVERITIES: Severity[] = ["NONE", "LOW", "MEDIUM", "HIGH", "CRITICAL"]

export function RunForm({ disabled, onSubmit }: Props) {
  const [file, setFile] = useState<File | null>(null)
  const [targetProfit, setTargetProfit] = useState("")
  const [targetRoi, setTargetRoi] = useState("")
  const [minMonthlySales, setMinMonthlySales] = useState("")
  const [maxRiskSeverity, setMaxRiskSeverity] = useState<Severity | "">("")
  const [allowRestricted, setAllowRestricted] = useState(false)
  const [allowApprovalRequired, setAllowApprovalRequired] = useState(false)
  const [allowUnknownRisk, setAllowUnknownRisk] = useState(false)
  const [referralFee, setReferralFee] = useState("")
  const [referralFeeRate, setReferralFeeRate] = useState("")
  const [fulfillmentFee, setFulfillmentFee] = useState("0")
  const [otherSellingFees, setOtherSellingFees] = useState("0")
  const [persist, setPersist] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)

  function selectFile(candidate: File | null) {
    if (candidate && !candidate.name.toLowerCase().endsWith(".xlsx")) {
      setFile(null)
      setFormError("JUVAl currently processes Excel workbooks (.xlsx) only. Choose an .xlsx file.")
      return
    }
    setFile(candidate)
    setFormError(null)
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (!file) {
      setFormError("Choose the Excel workbook to submit.")
      return
    }
    if (!targetProfit || !targetRoi || !minMonthlySales || !maxRiskSeverity || !referralFee || !referralFeeRate) {
      setFormError("Complete every required threshold and fee. JUVAl does not invent commercial defaults.")
      return
    }
    setFormError(null)
    onSubmit({
      file,
      thresholds: {
        target_profit: targetProfit,
        target_roi: targetRoi,
        minimum_estimated_monthly_sales: Number(minMonthlySales),
        maximum_risk_severity: maxRiskSeverity,
        allow_restricted: allowRestricted,
        allow_approval_required: allowApprovalRequired,
        allow_unknown_risk: allowUnknownRisk,
      },
      fees: {
        referral_fee: referralFee,
        referral_fee_rate: referralFeeRate,
        fulfillment_fee: fulfillmentFee,
        other_selling_fees: otherSellingFees,
      },
      persist,
    })
  }

  return (
    <form onSubmit={handleSubmit} className="run-form" aria-busy={disabled}>
      <fieldset disabled={disabled}>
        <legend>1. Select workbook</legend>
        <p className="form-help">One upload creates one processing run. The API accepts Excel workbooks (`.xlsx`) only.</p>
        <label className="file-field">
          Catalog workbook <span aria-hidden="true">*</span>
          <input type="file" accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" onChange={(event) => selectFile(event.target.files?.[0] ?? null)} aria-describedby="file-selection" />
        </label>
        <p id="file-selection" className={`file-selection${file ? " selected" : ""}`}>
          {file ? <>Selected: <strong>{file.name}</strong> · {(file.size / 1024).toFixed(0)} KB</> : "No workbook selected."}
        </p>
      </fieldset>

      <fieldset disabled={disabled}>
        <legend>2. Decision configuration</legend>
        <p className="form-help">These values are submitted to the deterministic pipeline; they are not saved as browser defaults.</p>
        <label>Target profit <span aria-hidden="true">*</span><input value={targetProfit} onChange={(event) => setTargetProfit(event.target.value)} inputMode="decimal" placeholder="e.g. 5" /></label>
        <label>Target ROI <span aria-hidden="true">*</span><input value={targetRoi} onChange={(event) => setTargetRoi(event.target.value)} inputMode="decimal" placeholder="e.g. 0.3" /></label>
        <label>Minimum estimated monthly sales <span aria-hidden="true">*</span><input type="number" min="0" value={minMonthlySales} onChange={(event) => setMinMonthlySales(event.target.value)} placeholder="e.g. 0" /></label>
        <label>Maximum accepted risk severity <span aria-hidden="true">*</span><select value={maxRiskSeverity} onChange={(event) => setMaxRiskSeverity(event.target.value as Severity)}><option value="">Select severity</option>{SEVERITIES.map((severity) => <option key={severity} value={severity}>{severity}</option>)}</select></label>
        <label className="checkbox"><input type="checkbox" checked={allowRestricted} onChange={(event) => setAllowRestricted(event.target.checked)} />Allow RESTRICTED</label>
        <label className="checkbox"><input type="checkbox" checked={allowApprovalRequired} onChange={(event) => setAllowApprovalRequired(event.target.checked)} />Allow APPROVAL_REQUIRED</label>
        <label className="checkbox"><input type="checkbox" checked={allowUnknownRisk} onChange={(event) => setAllowUnknownRisk(event.target.checked)} />Allow unknown risk</label>
      </fieldset>

      <fieldset disabled={disabled}>
        <legend>3. Fees and review availability</legend>
        <p className="form-help">Referral fees are required. Persisting stores the immutable run snapshot so it can be reviewed later.</p>
        <label>Referral fee <span aria-hidden="true">*</span><input aria-label="Referral fee" value={referralFee} onChange={(event) => setReferralFee(event.target.value)} inputMode="decimal" placeholder="e.g. 3" /></label>
        <label>Referral fee rate <span aria-hidden="true">*</span><input aria-label="Referral fee rate" value={referralFeeRate} onChange={(event) => setReferralFeeRate(event.target.value)} inputMode="decimal" placeholder="e.g. 0.15" /></label>
        <label>Fulfillment fee<input value={fulfillmentFee} onChange={(event) => setFulfillmentFee(event.target.value)} inputMode="decimal" /></label>
        <label>Other selling fees<input value={otherSellingFees} onChange={(event) => setOtherSellingFees(event.target.value)} inputMode="decimal" /></label>
        <label className="checkbox persist-option"><input type="checkbox" checked={persist} onChange={(event) => setPersist(event.target.checked)} />Persist this run for Runs and later review</label>
      </fieldset>

      {formError && <p role="alert" className="form-error">{formError}</p>}
      <button type="submit" disabled={disabled}>{disabled ? "Processing catalog…" : "Process catalog"}</button>
    </form>
  )
}
