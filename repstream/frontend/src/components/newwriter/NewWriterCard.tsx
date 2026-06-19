import { useState } from 'react'
import { FileText, Loader2 } from 'lucide-react'
import clsx from 'clsx'
import type { NewWriterCandidate, ApproachBriefResponse } from '../../types/newwriter'
import { useApproachBrief } from '../../hooks/useNewWriters'

interface Props {
  candidate: NewWriterCandidate
}

const AVATAR_COLORS = [
  'bg-blue-800', 'bg-teal-600', 'bg-purple-700', 'bg-rose-600',
  'bg-cyan-700', 'bg-indigo-700', 'bg-amber-600', 'bg-emerald-700',
]
function avatarColor(name: string) {
  let h = 0; for (const c of name) h = c.charCodeAt(0) + ((h << 5) - h)
  return AVATAR_COLORS[Math.abs(h) % AVATAR_COLORS.length]
}
function initials(name: string) {
  const p = name.replace('Dr. ', '').split(' ')
  return p.length >= 2 ? (p[0][0] + p[p.length - 1][0]).toUpperCase() : name.slice(0, 2).toUpperCase()
}

function PeerBar({ pct }: { pct: number }) {
  const color = pct >= 70 ? 'bg-green-500' : pct >= 40 ? 'bg-yellow-400' : 'bg-gray-300'
  return (
    <div className="flex items-center gap-2">
      <div className="w-24 h-1.5 bg-gray-100 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-semibold text-gray-700">{pct.toFixed(0)}%</span>
    </div>
  )
}

function BriefText({ text, highlight }: { text: string; highlight: string | null }) {
  if (!highlight || !text.includes(highlight)) return <span className="text-sm text-gray-700">{text}</span>
  const [before, after] = text.split(highlight)
  return (
    <span className="text-sm text-gray-700">
      {before}<span className="text-green-600 font-medium">{highlight}</span>{after}
    </span>
  )
}

export default function NewWriterCard({ candidate }: Props) {
  const [showBrief, setShowBrief] = useState(false)
  const { mutate: generate, data: brief, isPending } = useApproachBrief()

  const handleGenerate = () => {
    setShowBrief(true)
    if (!brief) generate(candidate.hcp_id)
  }

  return (
    <div className="bg-white border border-gray-200 rounded-lg mb-3 overflow-hidden">
      <div className="flex items-start p-4 gap-4">
        {/* Avatar */}
        <div className={clsx(
          'w-11 h-11 rounded-full flex items-center justify-center shrink-0 text-white font-bold text-sm',
          avatarColor(candidate.name),
        )}>
          {initials(candidate.name)}
        </div>

        <div className="flex-1 min-w-0">
          {/* Header */}
          <div className="flex items-start justify-between gap-4">
            <div>
              <h3 className="font-semibold text-gray-900 text-sm">{candidate.name}</h3>
              <p className="text-xs text-gray-400">{candidate.specialty} · {candidate.city}, {candidate.state}</p>
              <span className="inline-block mt-1.5 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wide border border-teal-400 text-teal-600 bg-teal-50">
                Non-Writer
              </span>
            </div>
            <button onClick={handleGenerate} disabled={isPending} className="shrink-0 flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-indigo-600 text-white rounded hover:bg-indigo-700 transition-colors disabled:opacity-50">
              {isPending ? <Loader2 className="w-3 h-3 animate-spin" /> : <FileText className="w-3 h-3" />}
              Approach Brief
            </button>
          </div>

          {/* Peer match */}
          <div className="mt-3">
            <div className="flex items-center justify-between mb-1">
              <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">
                AI Peer Match{candidate.ai_peer_name ? ` — via ${candidate.ai_peer_name}` : ''}
              </p>
              <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-bold bg-teal-600 text-white uppercase tracking-wider">
                AI Matched
              </span>
            </div>
            <PeerBar pct={candidate.ai_peer_match_score} />
          </div>

          {/* ICD-10 matches */}
          {candidate.ai_icd10_matched_codes.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {candidate.ai_icd10_matched_codes.map((code) => (
                <span key={code} className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-teal-50 text-teal-700 border border-teal-200">
                  {code}
                </span>
              ))}
            </div>
          )}

          {/* Approach brief (expanded) */}
          {showBrief && (
            <div className="mt-3 bg-indigo-50 border border-indigo-100 rounded-lg p-3">
              <div className="flex items-center justify-between mb-1">
                <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">AI-Generated Approach Brief</p>
                <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-bold bg-indigo-600 text-white uppercase tracking-wider">
                  AI Insight
                </span>
              </div>
              {isPending
                ? <p className="text-xs text-indigo-400 italic">Generating via GPT-4o…</p>
                : brief && <BriefText text={brief.ai_approach_brief} highlight={brief.ai_approach_highlight} />}
            </div>
          )}

          {/* Metrics footer */}
          <div className="flex items-center gap-8 mt-3 pt-3 border-t border-gray-100">
            <div><p className="text-[10px] text-gray-400">In-Class Rx Q1</p><p className="text-xs font-semibold text-gray-800">{candidate.in_class_rx_q1.toFixed(0)}</p></div>
            <div><p className="text-[10px] text-gray-400">Brand Rx Q1</p><p className="text-xs font-semibold text-orange-500">{candidate.brand_rx_q1 > 0 ? candidate.brand_rx_q1.toFixed(0) : '—'}</p></div>
            <div><p className="text-[10px] text-gray-400">Competitor ({candidate.competitor_brand ?? '—'})</p><p className="text-xs font-semibold text-gray-800">{candidate.competitor_volume.toFixed(0)} Rx/qtr</p></div>
            <div><p className="text-[10px] text-gray-400">ICD-10 Matches</p><p className="text-xs font-semibold text-teal-700">{candidate.ai_icd10_match_count}</p></div>
            <div><p className="text-[10px] text-gray-400">Segment</p><p className="text-xs font-semibold text-gray-800">{candidate.segment ?? '—'}</p></div>
          </div>
        </div>
      </div>
    </div>
  )
}
