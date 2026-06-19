import React from "react";
import type { ActionCenterSummary } from "../../types/actioncenter";

interface Props {
  summary: ActionCenterSummary;
}

interface KPITileProps {
  value: string | number;
  label: string;
  badge?: string;
  badgeColor?: string;
  subtext?: string;
  valueColor?: string;
}

const KPITile: React.FC<KPITileProps> = ({
  value,
  label,
  badge,
  badgeColor = "bg-indigo-100 text-indigo-700",
  subtext,
  valueColor = "text-gray-900",
}) => (
  <div className="bg-white border border-gray-200 rounded-lg p-4 flex flex-col gap-1 shadow-sm">
    <div className="flex items-center justify-between">
      <span className={`text-2xl font-bold ${valueColor}`}>{value}</span>
      {badge && (
        <span className={`text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-wide ${badgeColor}`}>
          {badge}
        </span>
      )}
    </div>
    <span className="text-xs text-gray-500 font-medium uppercase tracking-wide leading-tight">{label}</span>
    {subtext && <span className="text-[11px] text-gray-400">{subtext}</span>}
  </div>
);

export const ActionCenterKPI: React.FC<Props> = ({ summary }) => (
  <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3 mb-6">
    <KPITile
      value={summary.ai_critical_count}
      label="Critical Alerts"
      badge="AI DETECTED"
      badgeColor="bg-red-100 text-red-700"
      valueColor="text-red-600"
    />
    <KPITile
      value={summary.ai_high_priority_count}
      label="High Priority"
      badge="AI DETECTED"
      badgeColor="bg-orange-100 text-orange-700"
      valueColor="text-orange-600"
    />
    <KPITile
      value={summary.ai_medium_priority_count}
      label="Medium Priority"
      subtext="No change"
      valueColor="text-blue-600"
    />
    <KPITile
      value={summary.ai_hcp_drift_detected_count}
      label="HCP Drift Detected"
      badge="ML MODEL"
      badgeColor="bg-purple-100 text-purple-700"
      valueColor="text-purple-600"
    />
    <KPITile
      value={`${summary.ai_early_detection_weeks}wk`}
      label="Early Detection"
      badge="AI DETECTED"
      badgeColor="bg-green-100 text-green-700"
      subtext="vs 6-8 wk traditional"
      valueColor="text-green-600"
    />
  </div>
);
