import { useState } from 'react'
import { RefreshCw } from 'lucide-react'
import clsx from 'clsx'
import type { HCPRankedItem } from '../../types/hcp'
import { useRegenerateInsight } from '../../hooks/useTerritoryData'

interface Props {
  hcp: HCPRankedItem
}

// Cycle through a palette of avatar colours (not tied to priority)
const AVATAR_COLORS = [
  'bg-orange-500', 'bg-blue-800', 'bg-teal-600', 'bg-purple-600',
  'bg-rose-500', 'bg-amber-600', 'bg-cyan-700', 'bg-indigo-600',
]

function getAvatarColor(name: string): string {
  let hash = 0
  for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash)
  return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length]
}

function getInitials(name: string): string {
  const parts = name.replace('Dr. ', '').split(' ')
  return parts.length >= 2
    ? (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
    : name.slice(0, 2).toUpperCase()
}

/** Render insight text — wraps the highlight phrase in green. */
function InsightText({ text, highlight }: { text: string; highlight: string | null }) {
  if (!highlight || !text.includes(highlight)) {
    return <span className="text-sm text-gray-700">{text}</span>
  }
  const [before, after] = text.split(highlight)
  return (
    <span className="text-sm text-gray-700">
      {before}
      <span className="text-green-600 font-medium">{highlight}</span>
      {after}
    </span>
  )
}

const PRIORITY_BADGE: Record<string, string> = {
  HIGH: 'border border-orange-400 text-orange-600 bg-orange-50',
  MEDIUM: 'border border-blue-400 text-blue-600 bg-blue-50',
  LOW: 'border border-gray-300 text-gray-500 bg-gray-50',
}

export default function HCPCard({ hcp }: Props) {
  const { mutate: regenerate, isPending } = useRegenerateInsight()

  return (
    <div className="bg-white border border-gray-200 rounded-lg mb-3 overflow-hidden">
      <div className="flex items-start p-4 gap-4">
        {/* Avatar */}
        <div className={clsx(
          'w-11 h-11 rounded-full flex items-center justify-center shrink-0 text-white font-bold text-sm',
          getAvatarColor(hcp.name),
        )}>
          {getInitials(hcp.name)}
        </div>

        {/* Main content */}
        <div className="flex-1 min-w-0">
          {/* Name + specialty row */}
          <div className="flex items-start justify-between gap-4">
            <div>
              <h3 className="font-semibold text-gray-900 text-sm">{hcp.name}</h3>
              <p className="text-xs text-gray-400">
                {[hcp.specialty, hcp.affiliated_hospital].filter(Boolean).join(' • ')}
              </p>
              {/* Priority badge */}
              <span className={clsx(
                'inline-block mt-1.5 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wide',
                PRIORITY_BADGE[hcp.ai_priority_tier],
              )}>
                {hcp.ai_priority_tier} Priority
              </span>
            </div>
            <button className="shrink-0 px-3 py-1.5 text-xs font-medium border border-gray-700 text-gray-700 rounded hover:bg-gray-50 transition-colors">
              View Profile
            </button>
          </div>

          {/* AI Insight block */}
          <div className="mt-3">
            <div className="flex items-center justify-between mb-1">
              <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">AI-Generated Insight</p>
              <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-bold bg-indigo-600 text-white uppercase tracking-wider">
                AI Insight
              </span>
            </div>
            {hcp.ai_generated_insight ? (
              <InsightText text={hcp.ai_generated_insight} highlight={hcp.ai_insight_highlight} />
            ) : (
              <span className="text-xs text-gray-400 italic">Insight not yet generated</span>
            )}
          </div>

          {/* Metrics footer */}
          <div className="flex items-center gap-10 mt-3 pt-3 border-t border-gray-100">
            <div>
              <p className="text-[10px] text-gray-400">Last Rx</p>
              <p className="text-xs font-semibold text-gray-800">{hcp.last_call_date ?? '—'}</p>
            </div>
            <div>
              <p className="text-[10px] text-gray-400">Total Rx Q1</p>
              <p className="text-xs font-semibold text-gray-800">{hcp.rx_q1.toFixed(0)}</p>
            </div>
            <div>
              <p className="text-[10px] text-gray-400">Total Rx Q4</p>
              <p className={clsx(
                'text-xs font-semibold',
                hcp.rx_q4 === 0 ? 'text-gray-400' : 'text-orange-500',
              )}>
                {hcp.rx_q4 > 0 ? hcp.rx_q4.toFixed(0) : '—'}
              </p>
            </div>
            <div>
              <p className="text-[10px] text-gray-400">Segment</p>
              <p className="text-xs font-semibold text-gray-800">{hcp.segment ?? '—'}</p>
            </div>
            <div>
              <p className="text-[10px] text-gray-400">AI Score</p>
              <p className="text-xs font-semibold text-indigo-700">{hcp.ai_priority_score.toFixed(0)}/100</p>
            </div>

            {/* Regenerate button far right */}
            <div className="ml-auto">
              <button
                onClick={() => regenerate(hcp.hcp_id)}
                disabled={isPending}
                className="flex items-center gap-1 text-[10px] text-indigo-500 hover:text-indigo-700 disabled:opacity-40"
              >
                <RefreshCw className={clsx('w-3 h-3', isPending && 'animate-spin')} />
                Regenerate
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
