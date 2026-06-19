import React, { useState } from "react";
import type { PayerAccessItem, AccessImpact } from "../../types/actioncenter";

interface Props {
  items: PayerAccessItem[];
  ai_high_impact_count: number;
  ai_total_covered_lives_at_risk: number;
  ai_total_affected_hcps: number;
}

const IMPACT_STYLES: Record<AccessImpact, string> = {
  High: "bg-red-100 text-red-700",
  Medium: "bg-orange-100 text-orange-700",
  Low: "bg-green-100 text-green-700",
};

const TIER_CHANGE_STYLES: Record<string, string> = {
  DOWNGRADE: "text-red-600 font-bold",
  UPGRADE: "text-green-600 font-bold",
  UNCHANGED: "text-gray-500",
};

const TIER_CHANGE_ICON: Record<string, string> = {
  DOWNGRADE: "▼",
  UPGRADE: "▲",
  UNCHANGED: "—",
};

const FORMULARY_LABELS: Record<string, string> = {
  PREFERRED: "Preferred",
  NON_PREFERRED: "Non-Preferred",
  NON_PREFERRED_BRAND: "Non-Preferred",
  EXCLUDED: "Excluded",
  PA_REQUIRED: "PA Required",
};

export const PayerAccessPanel: React.FC<Props> = ({
  items,
  ai_high_impact_count,
  ai_total_covered_lives_at_risk,
  ai_total_affected_hcps,
}) => {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  return (
    <div>
      {/* Summary row */}
      <div className="flex gap-3 mb-4 flex-wrap">
        <span className="bg-red-100 text-red-700 text-xs font-bold px-3 py-1 rounded-full">
          High Impact: {ai_high_impact_count}
        </span>
        <span className="bg-orange-100 text-orange-700 text-xs font-bold px-3 py-1 rounded-full">
          {ai_total_covered_lives_at_risk.toLocaleString()} Covered Lives at Risk
        </span>
        <span className="bg-gray-100 text-gray-600 text-xs font-bold px-3 py-1 rounded-full">
          {ai_total_affected_hcps} Total Affected HCPs
        </span>
      </div>

      <div className="space-y-4">
        {items.map((item) => {
          const isExpanded = expandedId === item.access_id;
          const direction = item.ai_tier_change_direction ?? "UNCHANGED";
          const formularyLabel = FORMULARY_LABELS[item.formulary_status ?? ""] ?? item.formulary_status ?? "—";

          return (
            <div key={item.access_id} className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
              <div className="p-4">
                <div className="flex items-start gap-3 mb-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap mb-1">
                      <span className="font-semibold text-gray-900 text-sm">{item.payer_name}</span>
                      <span className={`text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-wide ${IMPACT_STYLES[item.ai_access_impact]}`}>
                        {item.ai_access_impact} IMPACT
                      </span>
                      <span className="text-[10px] bg-indigo-100 text-indigo-700 font-bold px-2 py-0.5 rounded uppercase tracking-wide">
                        AI FLAGGED
                      </span>
                    </div>
                    <p className="text-xs text-gray-500">{item.formulary_status && `${formularyLabel} · `}{item.period}</p>
                  </div>
                  <div className="flex flex-col items-center flex-shrink-0">
                    <span className="text-lg font-bold text-gray-900">{item.ai_impact_score.toFixed(0)}</span>
                    <span className="text-[10px] text-gray-400 uppercase">AI Score</span>
                  </div>
                </div>

                {/* Tier change */}
                {(item.product_tier_current !== undefined && item.product_tier_previous !== undefined) && (
                  <div className="bg-gray-50 rounded-lg p-3 mb-3">
                    <div className="flex items-center justify-between">
                      <div className="text-center">
                        <div className="text-xs text-gray-500 mb-0.5">Previous Tier</div>
                        <div className="text-2xl font-bold text-gray-600">Tier {item.product_tier_previous}</div>
                      </div>
                      <div className="text-center">
                        <div className={`text-xl ${TIER_CHANGE_STYLES[direction]}`}>
                          {TIER_CHANGE_ICON[direction]}
                        </div>
                        <div className={`text-xs font-bold ${TIER_CHANGE_STYLES[direction]}`}>
                          {direction}
                        </div>
                      </div>
                      <div className="text-center">
                        <div className="text-xs text-gray-500 mb-0.5">Current Tier</div>
                        <div className={`text-2xl font-bold ${direction === "DOWNGRADE" ? "text-red-600" : direction === "UPGRADE" ? "text-green-600" : "text-gray-600"}`}>
                          Tier {item.product_tier_current}
                        </div>
                      </div>
                    </div>
                    {item.tier_change_date && (
                      <div className="text-center mt-1 text-[11px] text-gray-400">
                        Effective: {item.tier_change_date}
                      </div>
                    )}
                  </div>
                )}

                {/* Metrics */}
                <div className="grid grid-cols-2 gap-2 mb-3">
                  <div className="bg-gray-50 rounded p-2 text-center">
                    <div className="text-sm font-bold text-gray-800">{item.covered_lives.toLocaleString()}</div>
                    <div className="text-[10px] text-gray-500 uppercase">Covered Lives</div>
                  </div>
                  <div className="bg-gray-50 rounded p-2 text-center">
                    <div className="text-sm font-bold text-gray-800">{item.affected_hcp_count}</div>
                    <div className="text-[10px] text-gray-500 uppercase">Affected HCPs</div>
                  </div>
                </div>

                {/* Action required */}
                {item.ai_action_required && (
                  <div className="bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 text-xs text-amber-900 mb-3 leading-relaxed">
                    <span className="font-semibold">Action needed: </span>{item.ai_action_required}
                  </div>
                )}

                {/* Patient assistance */}
                {item.patient_assistance_available && item.ai_patient_assistance_note && (
                  <button
                    onClick={() => setExpandedId(isExpanded ? null : item.access_id)}
                    className="text-xs text-indigo-600 font-semibold hover:text-indigo-800 transition-colors"
                  >
                    {isExpanded ? "Hide Patient Support Info ▲" : "View Patient Support Info ▼"}
                  </button>
                )}
              </div>

              {/* Patient assistance detail */}
              {isExpanded && item.ai_patient_assistance_note && (
                <div className="border-t border-gray-100 px-4 py-3 bg-blue-50">
                  <p className="text-sm text-blue-900 leading-relaxed">{item.ai_patient_assistance_note}</p>
                </div>
              )}

              {/* Action buttons */}
              <div className="px-4 py-3 border-t border-gray-100 flex flex-wrap gap-2">
                <button className="px-3 py-1.5 bg-indigo-600 text-white text-xs font-semibold rounded-lg hover:bg-indigo-700 transition-colors">
                  View HCP List
                </button>
                <button className="px-3 py-1.5 bg-white border border-gray-300 text-gray-700 text-xs font-semibold rounded-lg hover:bg-gray-50 transition-colors">
                  Access Resources
                </button>
                <button className="px-3 py-1.5 bg-white border border-gray-200 text-gray-400 text-xs font-medium rounded-lg hover:bg-gray-50 transition-colors">
                  Acknowledge
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
