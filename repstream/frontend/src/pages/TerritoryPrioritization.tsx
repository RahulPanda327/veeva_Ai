import { useState } from 'react'
import { Loader2 } from 'lucide-react'
import clsx from 'clsx'
import KPITiles from '../components/territory/KPITiles'
import HCPCard from '../components/territory/HCPCard'
import { useHCPList, useTerritorySummary } from '../hooks/useTerritoryData'
import type { HCPRankedItem } from '../types/hcp'

type Filter = 'ALL' | 'HIGH' | 'MEDIUM' | 'LOW'

const filters: { label: string; value: Filter }[] = [
  { label: 'All', value: 'ALL' },
  { label: 'High Priority', value: 'HIGH' },
  { label: 'Medium Priority', value: 'MEDIUM' },
  { label: 'Low Priority', value: 'LOW' },
]

export default function TerritoryPrioritization() {
  const [filter, setFilter] = useState<Filter>('ALL')
  const { data: summary, isLoading: summaryLoading } = useTerritorySummary()
  const { data: hcps, isLoading: hcpLoading } = useHCPList()

  const filtered: HCPRankedItem[] = (hcps ?? []).filter(
    (h) => filter === 'ALL' || h.ai_priority_tier === filter,
  )

  if (summaryLoading || hcpLoading) {
    return (
      <div className="flex items-center justify-center py-24 text-gray-400 gap-3">
        <Loader2 className="w-5 h-5 animate-spin" />
        <span className="text-sm">Loading territory data…</span>
      </div>
    )
  }

  return (
    <div>
      {summary && <KPITiles summary={summary} />}

      {/* Section header */}
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold text-gray-800">This week's priority targets</h2>
        <p className="text-[11px] text-gray-400">Powered by DATAstream™ Rx + Veeva AI</p>
      </div>

      {/* Filter chips */}
      <div className="flex gap-2 mb-4">
        {filters.map((f) => (
          <button
            key={f.value}
            onClick={() => setFilter(f.value)}
            className={clsx(
              'px-3 py-1 rounded-full text-xs font-medium transition-colors',
              filter === f.value
                ? 'bg-gray-900 text-white'
                : 'bg-white border border-gray-200 text-gray-600 hover:bg-gray-50',
            )}
          >
            {f.label}
          </button>
        ))}
        <span className="ml-auto text-xs text-gray-400 self-center">{filtered.length} HCPs</span>
      </div>

      {/* HCP list */}
      {filtered.length === 0 ? (
        <div className="text-center py-16 text-gray-400 text-sm">No HCPs match this filter.</div>
      ) : (
        filtered.map((hcp) => <HCPCard key={hcp.hcp_id} hcp={hcp} />)
      )}
    </div>
  )
}
