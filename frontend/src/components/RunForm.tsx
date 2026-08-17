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

// Every field the Core requires explicitly (Thresholds/FeeInputs have no
// default -- ADR-007) starts empty here on purpose: the operator must
// type a real value, never a silently pre-filled business number.
// Only the two FeeInputs fields that already have a domain-level default
// (fulfillment_fee/other_selling_fees = 0, see domain/costs.py) mirror
// that same default here -- that is not a new invented value.
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
  const [formError, setFormError] = useState<string | null>(null)

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (!file) {
      setFormError("Selecciona un archivo .xlsx.")
      return
    }
    if (!targetProfit || !targetRoi || !minMonthlySales || !maxRiskSeverity || !referralFee || !referralFeeRate) {
      setFormError("Todos los campos marcados como obligatorios deben completarse -- no existe un valor comercial por defecto.")
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
      persist: false,
    })
  }

  return (
    <form onSubmit={handleSubmit} className="run-form">
      <fieldset disabled={disabled}>
        <legend>Archivo</legend>
        <label>
          Catalog (.xlsx; .csv pending) *
          <input
            type="file"
            accept=".xlsx,.csv"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
        </label>

        <legend>Thresholds (obligatorios -- sin default comercial, ADR-007)</legend>
        <label>
          Target profit *
          <input value={targetProfit} onChange={(e) => setTargetProfit(e.target.value)} placeholder="ej. 5" />
        </label>
        <label>
          Target ROI *
          <input value={targetRoi} onChange={(e) => setTargetRoi(e.target.value)} placeholder="ej. 0.3" />
        </label>
        <label>
          Ventas mensuales estimadas mínimas *
          <input
            type="number"
            value={minMonthlySales}
            onChange={(e) => setMinMonthlySales(e.target.value)}
            placeholder="ej. 0"
          />
        </label>
        <label>
          Severidad de riesgo máxima aceptada *
          <select value={maxRiskSeverity} onChange={(e) => setMaxRiskSeverity(e.target.value as Severity)}>
            <option value="">-- seleccionar --</option>
            {SEVERITIES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
        <label className="checkbox">
          <input type="checkbox" checked={allowRestricted} onChange={(e) => setAllowRestricted(e.target.checked)} />
          Permitir RESTRICTED
        </label>
        <label className="checkbox">
          <input
            type="checkbox"
            checked={allowApprovalRequired}
            onChange={(e) => setAllowApprovalRequired(e.target.checked)}
          />
          Permitir APPROVAL_REQUIRED
        </label>
        <label className="checkbox">
          <input
            type="checkbox"
            checked={allowUnknownRisk}
            onChange={(e) => setAllowUnknownRisk(e.target.checked)}
          />
          Permitir riesgo desconocido
        </label>

        <legend>Fees (obligatorios los dos primeros)</legend>
        <label>
          Referral fee *
          <input value={referralFee} onChange={(e) => setReferralFee(e.target.value)} placeholder="ej. 3" />
        </label>
        <label>
          Referral fee rate *
          <input value={referralFeeRate} onChange={(e) => setReferralFeeRate(e.target.value)} placeholder="ej. 0.15" />
        </label>
        <label>
          Fulfillment fee
          <input value={fulfillmentFee} onChange={(e) => setFulfillmentFee(e.target.value)} />
        </label>
        <label>
          Other selling fees
          <input value={otherSellingFees} onChange={(e) => setOtherSellingFees(e.target.value)} />
        </label>

        {formError && (
          <p role="alert" className="form-error">
            {formError}
          </p>
        )}

        <button type="submit">Procesar</button>
      </fieldset>
    </form>
  )
}
