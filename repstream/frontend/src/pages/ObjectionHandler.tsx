import { useState } from 'react'
import { Loader2 } from 'lucide-react'
import ObjectionCard from '../components/objection/ObjectionCard'
import MLRResponseBlock from '../components/objection/MLRResponseBlock'
import { useObjectionResponse, useObjections } from '../hooks/useObjections'

export default function ObjectionHandler() {
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const { data: objections, isLoading } = useObjections()
  const { data: response, isLoading: responseLoading } = useObjectionResponse(selectedId ?? '')

  const highCount = objections?.filter((o) => o.ai_frequency_label === 'HIGH').length ?? 0
  const avgRate = objections && objections.length > 0
    ? (objections.reduce((s, o) => s + o.ai_success_rate, 0) / objections.length * 100).toFixed(0)
    : '—'

  return (
    <div>
      {/* KPI row */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <p className="text-xs text-gray-400 mb-1">Total Objections</p>
          <p className="text-3xl font-bold text-gray-900">{objections?.length ?? '—'}</p>
        </div>
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <p className="text-xs text-gray-400 mb-1">High Frequency</p>
          <p className="text-3xl font-bold text-orange-500">{highCount}</p>
          <span className="inline-flex items-center mt-1 px-1.5 py-0.5 rounded text-[9px] font-bold bg-indigo-600 text-white uppercase tracking-wider">
            AI Ranked
          </span>
        </div>
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <p className="text-xs text-gray-400 mb-1">Avg Rx Conversion</p>
          <p className="text-3xl font-bold text-green-600">{avgRate}%</p>
        </div>
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <p className="text-xs text-gray-400 mb-1">MLR Scripts Available</p>
          <p className="text-3xl font-bold text-indigo-700">{objections?.length ?? '—'}</p>
        </div>
      </div>

      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold text-gray-800">Objections from call transcripts</h2>
        <p className="text-[11px] text-gray-400">Powered by DATAstream™ Rx + Veeva AI</p>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-24 text-gray-400 gap-3">
          <Loader2 className="w-5 h-5 animate-spin" />
          <span className="text-sm">Loading objections…</span>
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-6">
          {/* Left: objection list */}
          <div>
            {objections?.map((obj) => (
              <ObjectionCard
                key={obj.objection_id}
                objection={obj}
                onSelect={setSelectedId}
                isSelected={selectedId === obj.objection_id}
              />
            ))}
          </div>

          {/* Right: MLR response */}
          <div>
            {!selectedId && (
              <div className="bg-white border border-gray-200 rounded-lg flex items-center justify-center py-16 text-gray-400 text-sm">
                Select an objection to view the MLR response
              </div>
            )}
            {selectedId && responseLoading && (
              <div className="bg-white border border-gray-200 rounded-lg flex items-center justify-center py-16 gap-3 text-gray-400">
                <Loader2 className="w-5 h-5 animate-spin" />
                <span className="text-sm">Loading response…</span>
              </div>
            )}
            {selectedId && !responseLoading && response && (
              <MLRResponseBlock response={response} />
            )}
          </div>
        </div>
      )}
    </div>
  )
}
