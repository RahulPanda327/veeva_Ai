import { Loader2 } from 'lucide-react'
import NewWriterCard from '../components/newwriter/NewWriterCard'
import { useNewWriterCandidates } from '../hooks/useNewWriters'

export default function NewWriterID() {
  const { data: candidates, isLoading, error } = useNewWriterCandidates()

  return (
    <div>
      {/* KPI row */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <p className="text-xs text-gray-400 mb-1">Non-Writer Candidates</p>
          <p className="text-3xl font-bold text-teal-600">{candidates?.length ?? '—'}</p>
          <span className="inline-flex items-center mt-1 px-1.5 py-0.5 rounded text-[9px] font-bold bg-indigo-600 text-white uppercase tracking-wider">
            AI Detected
          </span>
        </div>
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <p className="text-xs text-gray-400 mb-1">Avg Peer Match Score</p>
          <p className="text-3xl font-bold text-indigo-600">
            {candidates && candidates.length > 0
              ? (candidates.reduce((s, c) => s + c.ai_peer_match_score, 0) / candidates.length).toFixed(0)
              : '—'}%
          </p>
          <span className="inline-flex items-center mt-1 px-1.5 py-0.5 rounded text-[9px] font-bold bg-teal-600 text-white uppercase tracking-wider">
            AI Matched
          </span>
        </div>
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <p className="text-xs text-gray-400 mb-1">ICD-10 Match Rate</p>
          <p className="text-3xl font-bold text-gray-900">
            {candidates && candidates.length > 0
              ? `${candidates.filter((c) => c.ai_icd10_match_count > 0).length}/${candidates.length}`
              : '—'}
          </p>
        </div>
      </div>

      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold text-gray-800">Non-writer candidates for conversion</h2>
        <p className="text-[11px] text-gray-400">Powered by DATAstream™ Rx + Veeva AI</p>
      </div>

      {isLoading && (
        <div className="flex items-center justify-center py-24 text-gray-400 gap-3">
          <Loader2 className="w-5 h-5 animate-spin" />
          <span className="text-sm">Loading candidates…</span>
        </div>
      )}

      {error && <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-600 text-sm">Failed to load candidates.</div>}

      {!isLoading && candidates?.map((c) => <NewWriterCard key={c.hcp_id} candidate={c} />)}

      {!isLoading && candidates?.length === 0 && (
        <div className="text-center py-16 text-gray-400 text-sm">No new-writer candidates found this period.</div>
      )}
    </div>
  )
}
