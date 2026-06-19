import { X, Loader2, Sparkles } from 'lucide-react'
import type { ApproachBriefResponse } from '../../types/newwriter'

interface Props {
  hcpName: string
  brief: ApproachBriefResponse | null
  isLoading: boolean
  onClose: () => void
}

export default function ApproachBriefModal({ hcpName, brief, isLoading, onClose }: Props) {
  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg">
        <div className="flex items-center justify-between p-5 border-b border-slate-100">
          <div className="flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-purple-600" />
            <h2 className="font-semibold text-slate-900">Warm Approach Brief</h2>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-5">
          <p className="text-sm text-slate-500 mb-4">Generated for: <strong className="text-slate-800">{hcpName}</strong></p>

          {isLoading && (
            <div className="flex items-center gap-3 text-purple-600 py-8 justify-center">
              <Loader2 className="w-5 h-5 animate-spin" />
              <span className="text-sm">Generating approach brief via GPT-4o…</span>
            </div>
          )}

          {!isLoading && brief && (
            <>
              <div className="bg-purple-50 border border-purple-100 rounded-xl p-4">
                <p className="text-sm text-slate-800 leading-relaxed">{brief.brief_text}</p>
              </div>
              {brief.peer_name && (
                <p className="text-xs text-slate-400 mt-3">
                  Connected via peer: <strong className="text-slate-600">{brief.peer_name}</strong>
                </p>
              )}
              <p className="text-xs text-slate-400 mt-1">
                Generated {new Date(brief.generated_at).toLocaleString()}
                {brief.cached && ' · from cache'}
              </p>
            </>
          )}
        </div>

        <div className="px-5 pb-5">
          <button onClick={onClose} className="btn-ghost w-full justify-center">
            Close
          </button>
        </div>
      </div>
    </div>
  )
}
