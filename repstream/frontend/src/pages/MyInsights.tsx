import { useState } from 'react'
import clsx from 'clsx'

// My Insights modules
import TerritoryPrioritization from './TerritoryPrioritization'
import NewWriterID from './NewWriterID'
import ObjectionHandler from './ObjectionHandler'

// Action Center modules
import { ActionCenterKPI } from '../components/actioncenter/ActionCenterKPI'
import { AlertCard } from '../components/actioncenter/AlertCard'
import { HCPAwarenessPanel } from '../components/actioncenter/HCPAwarenessPanel'
import { CompetitiveIntelPanel } from '../components/actioncenter/CompetitiveIntelPanel'
import { PayerAccessPanel } from '../components/actioncenter/PayerAccessPanel'

// Hooks
import { useTerritorySummary } from '../hooks/useTerritoryData'
import { useAlerts, useHCPAwareness, useCompetitiveIntel, usePayerAccess } from '../hooks/useActionCenter'

type Tab = 'territory' | 'newwriter' | 'objection' | 'alerts' | 'awareness' | 'intel' | 'payer'

const TABS: { id: Tab; label: string }[] = [
  { id: 'territory', label: 'Territory Prioritization' },
  { id: 'newwriter', label: 'New Writer ID' },
  { id: 'objection', label: 'Objection Handler' },
  { id: 'alerts',    label: 'Active Alerts' },
  { id: 'awareness', label: 'HCP Awareness' },
  { id: 'intel',     label: 'Competitive Intel' },
  { id: 'payer',     label: 'Payer Access' },
]

const Loading = () => (
  <div className="flex items-center justify-center py-16 text-gray-400 text-sm">Loading…</div>
)
const Err = ({ msg }: { msg: string }) => (
  <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700">{msg}</div>
)

export default function MyInsights() {
  const [activeTab, setActiveTab] = useState<Tab>('alerts')

  const { data: territorySummary } = useTerritorySummary()
  const alertsQuery    = useAlerts()
  const awarenessQuery = useHCPAwareness()
  const intelQuery     = useCompetitiveIntel()
  const payerQuery     = usePayerAccess()

  const acSummary = alertsQuery.data?.summary
  const unread    = acSummary?.ai_new_unread_count ?? 0

  const ACTION_TABS = new Set<Tab>(['alerts', 'awareness', 'intel', 'payer'])
  const isActionTab = ACTION_TABS.has(activeTab)

  const refPeriod  = isActionTab ? (acSummary?.period       ?? 'Q1 2026 (Jan - Mar)') : (territorySummary?.period       ?? 'Q1 2026 (Jan - Mar)')
  const refUpdated = isActionTab ? (acSummary?.last_refresh  ?? '—')                  : (territorySummary?.last_refresh  ?? '—')

  return (
    <div className="min-h-screen bg-gray-50 font-sans">

      {/* ── Header ── */}
      <div className="bg-white border-b border-gray-200 px-6 pt-5 pb-0 sticky top-0 z-20">
        <div className="max-w-7xl mx-auto">

          {/* Title row */}
          <div className="flex items-start justify-between mb-4">
            <div>
              <div className="flex items-center gap-3">
                <h1 className="text-xl font-bold text-gray-900">MyInsights — RepStream</h1>
                <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold bg-indigo-600 text-white uppercase tracking-wider">
                  Powered by Veeva AI
                </span>
              </div>
              <p className="text-xs text-gray-400 mt-0.5">AI-powered intelligence for your territory</p>
            </div>
            <div className="border border-gray-200 rounded-md px-3 py-2 text-right min-w-[180px]">
              <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-0.5">Data Reference</p>
              <p className="text-sm font-semibold text-gray-800">{refPeriod}</p>
              <p className="text-[11px] text-gray-400">Last updated: {refUpdated}</p>
            </div>
          </div>

          {/* 7-tab bar */}
          <div className="flex overflow-x-auto hide-scrollbar">
            {TABS.map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={clsx(
                  'relative px-4 py-2.5 text-sm font-medium border-b-2 transition-colors whitespace-nowrap',
                  activeTab === tab.id
                    ? 'border-indigo-600 text-indigo-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700',
                )}
              >
                {tab.label}
                {tab.id === 'alerts' && unread > 0 && (
                  <span className="absolute -top-0.5 right-1 bg-red-500 text-white text-[9px] font-bold w-4 h-4 rounded-full flex items-center justify-center">
                    {unread > 9 ? '9+' : unread}
                  </span>
                )}
              </button>
            ))}
          </div>

        </div>
      </div>

      {/* ── Alert banner (action tabs only) ── */}
      {isActionTab && unread > 0 && acSummary?.ai_banner_message && (
        <div className="bg-amber-50 border-b border-amber-300 px-6 py-3">
          <div className="max-w-7xl mx-auto flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-amber-600">⚠</span>
              <span className="text-sm font-medium text-amber-800">
                <strong>{unread} new alert{unread > 1 ? 's' : ''} require action</strong>
                {' '}— {acSummary.ai_banner_message}
              </span>
            </div>
            <button
              onClick={() => setActiveTab('alerts')}
              className="text-xs font-semibold text-amber-700 border border-amber-400 bg-white px-3 py-1.5 rounded-lg hover:bg-amber-50 transition-colors"
            >
              View Alerts
            </button>
          </div>
        </div>
      )}

      {/* ── Tab content ── */}
      <div className="max-w-7xl mx-auto px-6 py-6">

        {activeTab === 'territory' && <TerritoryPrioritization />}
        {activeTab === 'newwriter'  && <NewWriterID />}
        {activeTab === 'objection'  && <ObjectionHandler />}

        {activeTab === 'alerts' && (
          <div>
            {alertsQuery.isLoading && <Loading />}
            {alertsQuery.isError   && <Err msg="Failed to load alerts." />}
            {alertsQuery.data && (
              <>
                <ActionCenterKPI summary={alertsQuery.data.summary} />
                {alertsQuery.data.alerts.length === 0
                  ? <p className="text-center text-gray-400 text-sm py-12">No active alerts for your territory.</p>
                  : alertsQuery.data.alerts.map(a => <AlertCard key={a.alert_id} alert={a} />)
                }
              </>
            )}
          </div>
        )}

        {activeTab === 'awareness' && (
          <div>
            {awarenessQuery.isLoading && <Loading />}
            {awarenessQuery.isError   && <Err msg="Failed to load HCP awareness data." />}
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

        {activeTab === 'intel' && (
          <div>
            {intelQuery.isLoading && <Loading />}
            {intelQuery.isError   && <Err msg="Failed to load competitive intelligence." />}
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

        {activeTab === 'payer' && (
          <div>
            {payerQuery.isLoading && <Loading />}
            {payerQuery.isError   && <Err msg="Failed to load payer access data." />}
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
  )
}
