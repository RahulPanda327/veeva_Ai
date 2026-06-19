import React from "react";
import type { HCPAwarenessItem, AwarenessLevel } from "../../types/actioncenter";

interface Props {
  items: HCPAwarenessItem[];
  ai_high_awareness_count: number;
  ai_medium_awareness_count: number;
  ai_low_awareness_count: number;
}

const LEVEL_COLORS: Record<AwarenessLevel, string> = {
  High: "bg-green-100 text-green-700",
  Medium: "bg-blue-100 text-blue-700",
  Low: "bg-red-100 text-red-700",
};

const SCORE_BAR_COLOR: Record<AwarenessLevel, string> = {
  High: "bg-green-500",
  Medium: "bg-blue-500",
  Low: "bg-red-400",
};

const AVATAR_COLORS = [
  "bg-indigo-500", "bg-teal-500", "bg-orange-500",
  "bg-purple-500", "bg-pink-500", "bg-green-600",
];

const avatarColor = (name: string) =>
  AVATAR_COLORS[name.charCodeAt(0) % AVATAR_COLORS.length];

const initials = (name: string) =>
  name.split(" ").slice(0, 2).map((p) => p[0]).join("").toUpperCase();

const ScoreBar: React.FC<{ value: number; level: AwarenessLevel }> = ({ value, level }) => (
  <div className="flex items-center gap-2">
    <div className="flex-1 bg-gray-100 rounded-full h-2">
      <div
        className={`h-2 rounded-full ${SCORE_BAR_COLOR[level]}`}
        style={{ width: `${Math.min(100, Math.max(0, value))}%` }}
      />
    </div>
    <span className="text-xs font-bold text-gray-700 w-10 text-right">{value.toFixed(0)}/100</span>
  </div>
);

export const HCPAwarenessPanel: React.FC<Props> = ({
  items,
  ai_high_awareness_count,
  ai_medium_awareness_count,
  ai_low_awareness_count,
}) => (
  <div>
    {/* Summary row */}
    <div className="flex gap-3 mb-4">
      <span className="bg-green-100 text-green-700 text-xs font-bold px-3 py-1 rounded-full">
        High: {ai_high_awareness_count}
      </span>
      <span className="bg-blue-100 text-blue-700 text-xs font-bold px-3 py-1 rounded-full">
        Medium: {ai_medium_awareness_count}
      </span>
      <span className="bg-red-100 text-red-700 text-xs font-bold px-3 py-1 rounded-full">
        Low: {ai_low_awareness_count}
      </span>
    </div>

    <div className="space-y-4">
      {items.map((item) => (
        <div key={item.awareness_id} className="bg-white border border-gray-200 rounded-xl shadow-sm p-4">
          <div className="flex items-start gap-3 mb-3">
            <div className={`w-10 h-10 rounded-full flex items-center justify-center text-white text-sm font-bold flex-shrink-0 ${avatarColor(item.hcp_full_name)}`}>
              {initials(item.hcp_full_name)}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-semibold text-gray-900 text-sm">{item.hcp_full_name}</span>
                <span className={`text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-wide ${LEVEL_COLORS[item.ai_awareness_level]}`}>
                  {item.ai_awareness_level}
                </span>
                <span className="text-[10px] bg-indigo-100 text-indigo-700 font-bold px-2 py-0.5 rounded uppercase tracking-wide">
                  AI ASSESSED
                </span>
              </div>
              <span className="text-xs text-gray-500">{item.specialty ?? "—"}</span>
            </div>
          </div>

          {/* AI Awareness Score */}
          <div className="mb-3">
            <div className="flex items-center gap-1 mb-1">
              <span className="text-xs text-gray-600 font-medium">AI Awareness Score</span>
            </div>
            <ScoreBar value={item.ai_awareness_score} level={item.ai_awareness_level} />
          </div>

          {/* Score breakdown */}
          <div className="grid grid-cols-3 gap-2 mb-3">
            <div className="bg-gray-50 rounded p-2 text-center">
              <div className="text-sm font-bold text-gray-800">{item.product_awareness_score.toFixed(0)}</div>
              <div className="text-[10px] text-gray-500 uppercase">Product</div>
            </div>
            <div className="bg-gray-50 rounded p-2 text-center">
              <div className="text-sm font-bold text-gray-800">{item.competitor_awareness_score.toFixed(0)}</div>
              <div className="text-[10px] text-gray-500 uppercase">Competitor</div>
            </div>
            <div className="bg-gray-50 rounded p-2 text-center">
              <div className="text-sm font-bold text-gray-800">{item.clinical_evidence_score.toFixed(0)}</div>
              <div className="text-[10px] text-gray-500 uppercase">Clinical</div>
            </div>
          </div>

          {/* Messages delivered */}
          {item.ai_key_messages_delivered.length > 0 && (
            <div className="mb-2">
              <span className="text-[11px] text-gray-500 uppercase tracking-wide font-medium block mb-1">Messages Delivered</span>
              <div className="flex flex-wrap gap-1">
                {item.ai_key_messages_delivered.map((msg, i) => (
                  <span key={i} className="text-xs bg-green-50 border border-green-200 text-green-800 px-2 py-0.5 rounded-full">
                    {msg}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Knowledge gaps */}
          {item.ai_knowledge_gaps.length > 0 && (
            <div className="mb-2">
              <span className="text-[11px] text-gray-500 uppercase tracking-wide font-medium block mb-1">Knowledge Gaps</span>
              <div className="flex flex-wrap gap-1">
                {item.ai_knowledge_gaps.map((gap, i) => (
                  <span key={i} className="text-xs bg-amber-50 border border-amber-200 text-amber-800 px-2 py-0.5 rounded-full">
                    {gap}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Recommended action */}
          {item.ai_recommended_action && (
            <div className="mt-2 bg-indigo-50 border border-indigo-100 rounded-lg px-3 py-2 text-xs text-indigo-900">
              <span className="font-semibold">Recommended: </span>{item.ai_recommended_action}
            </div>
          )}

          <div className="flex items-center gap-3 mt-2 text-xs text-gray-400">
            <span>{item.total_interactions} interactions</span>
            {item.last_interaction_date && <span>Last: {item.last_interaction_date}</span>}
          </div>
        </div>
      ))}
    </div>
  </div>
);
