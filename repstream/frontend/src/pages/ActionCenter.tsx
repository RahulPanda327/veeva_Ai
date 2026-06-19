import React, { useState } from "react";
import { ActionCenterKPI } from "../components/actioncenter/ActionCenterKPI";
import { AlertCard } from "../components/actioncenter/AlertCard";
import { HCPAwarenessPanel } from "../components/actioncenter/HCPAwarenessPanel";
import { CompetitiveIntelPanel } from "../components/actioncenter/CompetitiveIntelPanel";
import { PayerAccessPanel } from "../components/actioncenter/PayerAccessPanel";
import { useAlerts, useHCPAwareness, useCompetitiveIntel, usePayerAccess } from "../hooks/useActionCenter";

type Tab = "alerts" | "awareness" | "intel" | "payer";

const TABS: { id: Tab; label: string }[] = [
  { id: "alerts", label: "Active Alerts" },
  { id: "awareness", label: "HCP Awareness" },
  { id: "intel", label: "Competitive Intel" },
  { id: "payer", label: "Payer Access" },
];

export const ActionCenter: React.FC = () => {
  const [activeTab, setActiveTab] = useState<Tab>("alerts");

  const alertsQuery = useAlerts();
  const awarenessQuery = useHCPAwareness();
  const intelQuery = useCompetitiveIntel();
  const payerQuery = usePayerAccess();

  const summary = alertsQuery.data?.summary;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Page header */}
      <div className="bg-white border-b border-gray-200 px-6 py-4 sticky top-0 z-10">
        <div className="max-w-5xl mx-auto">
          <div className="flex items-center gap-3 mb-1">
            <h1 className="text-xl font-bold text-gray-900">
              Action Center — Launch & Market Defense
            </h1>
            <span className="bg-indigo-600 text-white text-[10px] font-bold px-2 py-1 rounded uppercase tracking-wider">
              POWERED BY VEEVA AI
            </span>
          </div>
          {summary && (
            <p className="text-xs text-gray-400">
              {summary.period} · Last refresh: {summary.last_refresh}
            </p>
          )}
        </div>
      </div>

      <div className="max-w-5xl mx-auto px-4 py-6">
        {/* Yellow alert banner */}
        {summary?.ai_new_unread_count !== undefined && summary.ai_new_unread_count > 0 && (
          <div className="bg-amber-50 border border-amber-300 rounded-lg px-4 py-3 flex items-center justify-between mb-5 shadow-sm">
            <div className="flex items-center gap-2">
              <span className="text-amber-600 text-lg">⚠</span>
              <span className="text-sm font-medium text-amber-800">
                <strong>{summary.ai_new_unread_count} new alert{summary.ai_new_unread_count > 1 ? "s" : ""} require action</strong>
                {summary.ai_banner_message && ` — ${summary.ai_banner_message}`}
              </span>
            </div>
            <button
              onClick={() => setActiveTab("alerts")}
              className="text-xs font-semibold text-amber-700 border border-amber-400 bg-white px-3 py-1.5 rounded-lg hover:bg-amber-50 transition-colors"
            >
              View Alerts
            </button>
          </div>
        )}

        {/* KPI tiles (loaded from alerts summary) */}
        {summary && <ActionCenterKPI summary={summary} />}

        {/* Tab bar */}
        <div className="flex border-b border-gray-200 mb-5 gap-0">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-5 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab.id
                  ? "border-indigo-600 text-indigo-600"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              {tab.label}
              {tab.id === "alerts" && summary?.ai_new_unread_count ? (
                <span className="ml-1.5 bg-red-500 text-white text-[9px] font-bold px-1.5 py-0.5 rounded-full">
                  {summary.ai_new_unread_count}
                </span>
              ) : null}
            </button>
          ))}
        </div>

        {/* Tab content */}
        {activeTab === "alerts" && (
          <div>
            {alertsQuery.isLoading && <LoadingState />}
            {alertsQuery.isError && <ErrorState message="Failed to load alerts." />}
            {alertsQuery.data && alertsQuery.data.alerts.length === 0 && (
              <EmptyState message="No active alerts for your territory." />
            )}
            {alertsQuery.data?.alerts.map((alert) => (
              <AlertCard key={alert.alert_id} alert={alert} />
            ))}
          </div>
        )}

        {activeTab === "awareness" && (
          <div>
            {awarenessQuery.isLoading && <LoadingState />}
            {awarenessQuery.isError && <ErrorState message="Failed to load HCP awareness data." />}
            {awarenessQuery.data && (
              <HCPAwarenessPanel
                items={awarenessQuery.data.items}
                ai_high_awareness_count={awarenessQuery.data.ai_high_awareness_count}
                ai_medium_awareness_count={awarenessQuery.data.ai_medium_awareness_count}
                ai_low_awareness_count={awarenessQuery.data.ai_low_awareness_count}
              />
            )}
          </div>
        )}

        {activeTab === "intel" && (
          <div>
            {intelQuery.isLoading && <LoadingState />}
            {intelQuery.isError && <ErrorState message="Failed to load competitive intel." />}
            {intelQuery.data && (
              <CompetitiveIntelPanel
                items={intelQuery.data.items}
                ai_high_threat_count={intelQuery.data.ai_high_threat_count}
                ai_medium_threat_count={intelQuery.data.ai_medium_threat_count}
                ai_avg_threat_score={intelQuery.data.ai_avg_threat_score}
              />
            )}
          </div>
        )}

        {activeTab === "payer" && (
          <div>
            {payerQuery.isLoading && <LoadingState />}
            {payerQuery.isError && <ErrorState message="Failed to load payer access data." />}
            {payerQuery.data && (
              <PayerAccessPanel
                items={payerQuery.data.items}
                ai_high_impact_count={payerQuery.data.ai_high_impact_count}
                ai_total_covered_lives_at_risk={payerQuery.data.ai_total_covered_lives_at_risk}
                ai_total_affected_hcps={payerQuery.data.ai_total_affected_hcps}
              />
            )}
          </div>
        )}
      </div>
    </div>
  );
};

const LoadingState: React.FC = () => (
  <div className="flex items-center justify-center py-12 text-gray-400 text-sm">
    Loading…
  </div>
);

const ErrorState: React.FC<{ message: string }> = ({ message }) => (
  <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700">
    {message}
  </div>
);

const EmptyState: React.FC<{ message: string }> = ({ message }) => (
  <div className="text-center py-12 text-gray-400 text-sm">{message}</div>
);
