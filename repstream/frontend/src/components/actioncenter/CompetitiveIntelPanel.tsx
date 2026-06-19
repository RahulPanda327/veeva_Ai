import React, { useState } from "react";
import type { CompetitiveIntelItem, ThreatLevel } from "../../types/actioncenter";

interface Props {
  items: CompetitiveIntelItem[];
  ai_high_threat_count: number;
  ai_medium_threat_count: number;
  ai_avg_threat_score: number;
}

const THREAT_STYLES: Record<ThreatLevel, string> = {
  High: "bg-red-100 text-red-700 border border-red-200",
  Medium: "bg-orange-100 text-orange-700 border border-orange-200",
  Low: "bg-gray-100 text-gray-600 border border-gray-200",
};

const THREAT_BAR: Record<ThreatLevel, string> = {
  High: "bg-red-500",
  Medium: "bg-orange-400",
  Low: "bg-gray-300",
};

export const CompetitiveIntelPanel: React.FC<Props> = ({
  items,
  ai_high_threat_count,
  ai_medium_threat_count,
  ai_avg_threat_score,
}) => {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  return (
    <div>
      {/* Summary row */}
      <div className="flex gap-3 mb-4 flex-wrap">
        <span className="bg-red-100 text-red-700 text-xs font-bold px-3 py-1 rounded-full">
          High Threat: {ai_high_threat_count}
        </span>
        <span className="bg-orange-100 text-orange-700 text-xs font-bold px-3 py-1 rounded-full">
          Medium Threat: {ai_medium_threat_count}
        </span>
        <span className="bg-gray-100 text-gray-600 text-xs font-bold px-3 py-1 rounded-full">
          Avg AI Threat Score: {ai_avg_threat_score.toFixed(0)}/100
        </span>
      </div>

      <div className="space-y-4">
        {items.map((item) => {
          const isExpanded = expandedId === item.intel_id;
          return (
            <div key={item.intel_id} className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
              <div className="p-4">
                <div className="flex items-start gap-3 mb-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap mb-1">
                      <span className="font-semibold text-gray-900 text-sm">{item.competitor_name}</span>
                      <span className={`text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-wide ${THREAT_STYLES[item.ai_threat_level]}`}>
                        {item.ai_threat_level} THREAT
                      </span>
                      {item.ai_detection_method && (
                        <span className="text-[10px] bg-purple-100 text-purple-700 font-bold px-2 py-0.5 rounded uppercase tracking-wide">
                          {item.ai_detection_method.replace("_", " ")}
                        </span>
                      )}
                    </div>
                    {item.message_theme && (
                      <p className="text-sm text-gray-600">{item.message_theme}</p>
                    )}
                  </div>
                  {/* Threat score */}
                  <div className="flex flex-col items-center flex-shrink-0">
                    <span className="text-lg font-bold text-gray-900">{item.ai_threat_score.toFixed(0)}</span>
                    <span className="text-[10px] text-gray-400 uppercase">AI Score</span>
                  </div>
                </div>

                {/* Threat score bar */}
                <div className="flex items-center gap-2 mb-3">
                  <div className="flex-1 bg-gray-100 rounded-full h-1.5">
                    <div
                      className={`h-1.5 rounded-full ${THREAT_BAR[item.ai_threat_level]}`}
                      style={{ width: `${Math.min(100, item.ai_threat_score)}%` }}
                    />
                  </div>
                </div>

                {/* Quick metrics */}
                <div className="grid grid-cols-3 gap-2 mb-3">
                  <div className="bg-gray-50 rounded p-2 text-center">
                    <div className="text-sm font-bold text-gray-800">{item.affected_hcp_count}</div>
                    <div className="text-[10px] text-gray-500 uppercase">Affected HCPs</div>
                  </div>
                  <div className="bg-gray-50 rounded p-2 text-center">
                    <div className={`text-sm font-bold ${item.market_share_change_pct < 0 ? "text-red-600" : "text-green-600"}`}>
                      {item.market_share_change_pct >= 0 ? "+" : ""}{item.market_share_change_pct.toFixed(1)}%
                    </div>
                    <div className="text-[10px] text-gray-500 uppercase">Mkt Share Δ</div>
                  </div>
                  <div className="bg-gray-50 rounded p-2 text-center">
                    <div className="text-xs font-medium text-gray-700 truncate">{item.source_channel ?? "—"}</div>
                    <div className="text-[10px] text-gray-500 uppercase">Source</div>
                  </div>
                </div>

                {/* ICD-10 Focus */}
                {item.icd10_focus.length > 0 && (
                  <div className="flex flex-wrap gap-1 mb-3">
                    {item.icd10_focus.map((icd) => (
                      <span key={icd.code} className="text-xs bg-teal-50 border border-teal-200 text-teal-800 px-2 py-0.5 rounded-full">
                        {icd.code} · {icd.hcp_count} HCPs
                      </span>
                    ))}
                  </div>
                )}

                {/* Expand button */}
                {item.ai_counter_strategy && (
                  <button
                    onClick={() => setExpandedId(isExpanded ? null : item.intel_id)}
                    className="text-xs text-indigo-600 font-semibold hover:text-indigo-800 transition-colors"
                  >
                    {isExpanded ? "Hide Counter-Strategy ▲" : "View AI Counter-Strategy ▼"}
                  </button>
                )}
              </div>

              {/* Counter-strategy */}
              {isExpanded && item.ai_counter_strategy && (
                <div className="border-t border-gray-100 px-4 py-3 bg-indigo-50">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-xs font-bold text-indigo-700 uppercase tracking-wide">AI Counter-Strategy</span>
                    <span className="text-[10px] bg-indigo-200 text-indigo-800 font-bold px-2 py-0.5 rounded uppercase">
                      AI GENERATED
                    </span>
                  </div>
                  <p className="text-sm text-indigo-900 leading-relaxed">{item.ai_counter_strategy}</p>
                  {item.ai_supporting_evidence && (
                    <p className="text-xs text-indigo-600 mt-2 font-medium">{item.ai_supporting_evidence}</p>
                  )}
                  <div className="flex gap-2 mt-3">
                    <button className="px-3 py-1.5 bg-indigo-600 text-white text-xs font-semibold rounded-lg hover:bg-indigo-700 transition-colors">
                      Deploy Counter-Messaging
                    </button>
                    <button className="px-3 py-1.5 bg-white border border-indigo-200 text-indigo-600 text-xs font-semibold rounded-lg hover:bg-indigo-50 transition-colors">
                      Alert District Manager
                    </button>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
