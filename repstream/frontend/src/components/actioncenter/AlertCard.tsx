import React, { useState } from "react";
import type { AlertItem, AlertSeverity, AlertDetectionMethod } from "../../types/actioncenter";

interface Props {
  alert: AlertItem;
}

// ── Badge styles ─────────────────────────────────────────────────────────────

const SEVERITY_STYLES: Record<AlertSeverity, string> = {
  CRITICAL: "bg-red-600 text-white",
  HIGH:     "bg-orange-500 text-white",
  MEDIUM:   "bg-blue-500 text-white",
  LOW:      "bg-gray-400 text-white",
};

const SEVERITY_LABELS: Record<AlertSeverity, string> = {
  CRITICAL: "CRITICAL",
  HIGH:     "HIGH PRIORITY",
  MEDIUM:   "MEDIUM PRIORITY",
  LOW:      "LOW PRIORITY",
};

const DETECTION_STYLES: Record<AlertDetectionMethod, string> = {
  ANOMALY_DETECTION: "bg-red-100 text-red-700 border border-red-200",
  AUTO_DETECTED:     "bg-orange-100 text-orange-700 border border-orange-200",
  ML_MODEL:          "bg-purple-100 text-purple-700 border border-purple-200",
};

// "ML TREND" matches exactly what the user's KPI data shows for ML_MODEL rows
const DETECTION_LABELS: Record<AlertDetectionMethod, string> = {
  ANOMALY_DETECTION: "ANOMALY DETECTION",
  AUTO_DETECTED:     "AUTO-DETECTED",
  ML_MODEL:          "ML TREND",
};

const RISK_COLOR: Record<string, string> = {
  High:   "text-red-600 font-bold",
  Medium: "text-orange-500 font-bold",
  Low:    "text-green-600 font-bold",
};

// ── Left-border accent by severity ───────────────────────────────────────────
const CARD_BORDER: Record<AlertSeverity, string> = {
  CRITICAL: "border-l-4 border-l-red-500",
  HIGH:     "border-l-4 border-l-orange-400",
  MEDIUM:   "border-l-4 border-l-blue-400",
  LOW:      "border-l-4 border-l-gray-300",
};

// ── Action buttons vary by alert_type ────────────────────────────────────────
interface ActionBtn { label: string; primary?: boolean; }

function getActionButtons(alertType: string, severity: AlertSeverity): ActionBtn[] {
  if (alertType === "PAYER" || alertType === "FORMULARY") {
    return [
      { label: "View HCP List", primary: true },
      { label: "Access Resources" },
      { label: "Acknowledge" },
    ];
  }
  // MEDIUM/LOW severity competitive alerts: monitor rather than deploy
  if (severity === "MEDIUM" || severity === "LOW") {
    return [
      { label: "Monitor", primary: true },
      { label: "View Affected HCPs" },
      { label: "Dismiss" },
    ];
  }
  return [
    { label: "Deploy to Field", primary: true },
    { label: "View Affected HCPs" },
    { label: "Dismiss" },
  ];
}

// ── Impact field labels vary by alert_type ────────────────────────────────────
function getImpactFields(alert: AlertItem) {
  const isPayer = alert.alert_type === "PAYER" || alert.alert_type === "FORMULARY";
  return [
    { label: "Affected HCPs",                value: String(alert.ai_affected_hcp_count) },
    { label: isPayer ? "Covered Lives" : "Territory Reach", value: alert.ai_territory_reach ?? "—" },
    { label: isPayer ? "Access Impact" : "Rx Risk",
      value: alert.ai_rx_risk ?? "—",
      colored: true },
  ];
}

// ── Component ─────────────────────────────────────────────────────────────────

export const AlertCard: React.FC<Props> = ({ alert }) => {
  // CRITICAL and HIGH alerts show the counter-script open by default
  const [scriptOpen, setScriptOpen] = useState(
    alert.ai_severity === "CRITICAL" || alert.ai_severity === "HIGH"
  );

  const impactFields  = getImpactFields(alert);
  const actionButtons = getActionButtons(alert.alert_type, alert.ai_severity);

  return (
    <div className={`bg-white border border-gray-200 rounded-xl shadow-sm mb-4 overflow-hidden ${CARD_BORDER[alert.ai_severity]}`}>

      {/* ── Header ── */}
      <div className="px-5 pt-4 pb-3 border-b border-gray-100">
        <div className="flex items-center gap-2 flex-wrap mb-2">
          <span className={`text-xs font-bold px-2.5 py-1 rounded uppercase tracking-wide ${SEVERITY_STYLES[alert.ai_severity]}`}>
            {SEVERITY_LABELS[alert.ai_severity]}
          </span>
          <span className={`text-xs font-semibold px-2.5 py-1 rounded uppercase tracking-wide ${DETECTION_STYLES[alert.ai_detection_method]}`}>
            {DETECTION_LABELS[alert.ai_detection_method]}
          </span>
          {!alert.is_acknowledged && (
            <span className="ml-auto text-[10px] bg-indigo-100 text-indigo-700 font-bold px-2 py-0.5 rounded uppercase tracking-wide">
              NEW
            </span>
          )}
        </div>

        <h3 className="text-base font-semibold text-gray-900 mb-1">{alert.title}</h3>
        <p className="text-sm text-gray-600 leading-relaxed">{alert.description}</p>
        <p className="text-xs text-gray-400 mt-1.5">
          Detected: {alert.detected_at}
        </p>
      </div>

      {/* ── Impact Analysis ── */}
      <div className="px-5 py-3 bg-gray-50 border-b border-gray-100">
        <div className="flex items-center gap-2 mb-3">
          <span className="text-xs font-bold text-gray-700 uppercase tracking-wide">Impact Analysis</span>
          <span className="text-[10px] bg-indigo-100 text-indigo-700 font-bold px-2 py-0.5 rounded uppercase tracking-wide">
            AI ANALYSIS
          </span>
        </div>
        <div className="grid grid-cols-3 gap-4">
          {impactFields.map((f) => (
            <div key={f.label}>
              <span className="text-[11px] text-gray-400 uppercase tracking-wide block mb-0.5">{f.label}</span>
              <span className={`text-xl font-bold ${f.colored ? (RISK_COLOR[f.value] ?? "text-gray-800") : "text-gray-900"}`}>
                {f.value}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* ── ICD-10 codes ── */}
      {alert.ai_icd10_codes_affected.length > 0 && (
        <div className="px-5 py-3 border-b border-gray-100">
          <span className="text-xs font-bold text-gray-500 uppercase tracking-wide mb-2 block">
            Target ICD-10 Codes Affected
          </span>
          <div className="flex flex-wrap gap-2">
            {alert.ai_icd10_codes_affected.map((icd) => (
              <span
                key={icd.code}
                className="inline-flex items-center gap-1.5 bg-teal-50 border border-teal-200 text-teal-800 text-xs font-medium px-2.5 py-1 rounded-full"
              >
                <span className="font-bold">{icd.code}</span>
                <span className="text-teal-600">{icd.label}</span>
                <span className="bg-teal-200 text-teal-900 text-[10px] font-bold px-1.5 py-0.5 rounded-full">
                  {icd.hcp_count} HCPs
                </span>
              </span>
            ))}
          </div>
        </div>
      )}

      {/* ── Prescribing drift note ── */}
      {alert.ai_prescribing_drift_note && (
        <div className="px-5 py-3 border-b border-gray-100">
          <p className="text-sm text-gray-600 italic leading-relaxed">
            {alert.ai_prescribing_drift_note}
          </p>
        </div>
      )}

      {/* ── Counter-script ── */}
      {alert.ai_counter_script && (
        <div className="px-5 py-3 border-b border-gray-100">
          {/* Header row */}
          <button
            onClick={() => setScriptOpen(!scriptOpen)}
            className="flex items-center gap-2 w-full text-left mb-0"
          >
            <span className="text-xs font-bold text-gray-700 uppercase tracking-wide">
              Recommended Counter-Script
            </span>
            <span className="text-[10px] bg-green-100 text-green-700 border border-green-200 font-bold px-2 py-0.5 rounded uppercase tracking-wide">
              MLR-APPROVED
            </span>
            <span className="ml-auto text-gray-400 text-xs select-none">
              {scriptOpen ? "▲" : "▼"}
            </span>
          </button>

          {scriptOpen && (
            <div className="mt-2 bg-green-50 border border-green-200 rounded-lg px-4 py-3 text-sm text-green-900 leading-relaxed">
              {alert.ai_counter_script}
            </div>
          )}

          {/* Supporting materials */}
          {alert.ai_supporting_materials.length > 0 && (
            <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1">
              <span className="text-[11px] text-gray-400 font-medium">Supporting materials:</span>
              {alert.ai_supporting_materials.map((m, i) => (
                <span key={i} className="text-xs text-indigo-600 font-medium hover:underline cursor-pointer">
                  {m.title}
                  {m.sku && <span className="text-gray-400 font-normal"> ({m.sku})</span>}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── Action buttons ── */}
      <div className="px-5 py-3 flex flex-wrap gap-2">
        {actionButtons.map((btn) => (
          <button
            key={btn.label}
            className={
              btn.primary
                ? "px-3 py-1.5 bg-indigo-600 text-white text-xs font-semibold rounded-lg hover:bg-indigo-700 transition-colors"
                : btn.label === "Dismiss" || btn.label === "Acknowledge"
                  ? "px-3 py-1.5 bg-white border border-gray-200 text-gray-400 text-xs font-medium rounded-lg hover:bg-gray-50 transition-colors"
                  : "px-3 py-1.5 bg-white border border-gray-300 text-gray-700 text-xs font-semibold rounded-lg hover:bg-gray-50 transition-colors"
            }
          >
            {btn.label}
          </button>
        ))}
      </div>
    </div>
  );
};
