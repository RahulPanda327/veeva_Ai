import type { TerritorySummary } from '../../types/hcp'

interface Props {
  summary: TerritorySummary
}

export default function KPITiles({ summary }: Props) {
  return (
    <div className="grid grid-cols-5 gap-4 mb-6">
      {/* Total HCPs */}
      <div className="bg-white border border-gray-200 rounded-lg p-4">
        <p className="text-xs text-gray-400 mb-1">Total HCPs</p>
        <p className="text-3xl font-bold text-gray-900">{summary.total_hcps}</p>
      </div>

      {/* High priority */}
      <div className="bg-white border border-gray-200 rounded-lg p-4">
        <p className="text-xs text-gray-400 mb-1">High priority</p>
        <p className="text-3xl font-bold text-orange-500">{summary.high_priority_count}</p>
        <span className="inline-flex items-center mt-1 px-1.5 py-0.5 rounded text-[9px] font-bold bg-indigo-600 text-white uppercase tracking-wider">
          AI Ranked
        </span>
      </div>

      {/* Medium priority */}
      <div className="bg-white border border-gray-200 rounded-lg p-4">
        <p className="text-xs text-gray-400 mb-1">Medium priority</p>
        <p className="text-3xl font-bold text-blue-500">{summary.medium_priority_count}</p>
        <span className="inline-flex items-center mt-1 px-1.5 py-0.5 rounded text-[9px] font-bold bg-indigo-600 text-white uppercase tracking-wider">
          AI Ranked
        </span>
      </div>

      {/* Last refresh */}
      <div className="bg-white border border-gray-200 rounded-lg p-4">
        <p className="text-xs text-gray-400 mb-1">Last refresh</p>
        <p className="text-base font-semibold text-gray-800 leading-snug">{summary.last_refresh}</p>
      </div>

      {/* This week target */}
      <div className="bg-white border border-gray-200 rounded-lg p-4">
        <p className="text-xs text-gray-400 mb-1">This week target</p>
        <p className="text-3xl font-bold text-gray-900">{summary.weekly_target}</p>
      </div>
    </div>
  )
}
