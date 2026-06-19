import clsx from 'clsx'
import type { ObjectionItem } from '../../types/objection'

interface Props {
  objection: ObjectionItem
  onSelect: (id: string) => void
  isSelected: boolean
}

const FREQ_STYLE: Record<string, string> = {
  HIGH: 'border border-orange-400 text-orange-600 bg-orange-50',
  MEDIUM: 'border border-blue-400 text-blue-600 bg-blue-50',
  LOW: 'border border-gray-300 text-gray-500 bg-gray-50',
}

export default function ObjectionCard({ objection, onSelect, isSelected }: Props) {
  return (
    <button
      onClick={() => onSelect(objection.objection_id)}
      className={clsx(
        'w-full text-left bg-white border rounded-lg p-4 mb-2 transition-all hover:shadow-sm',
        isSelected ? 'border-indigo-400 ring-1 ring-indigo-400' : 'border-gray-200',
      )}
    >
      <div className="flex items-start justify-between gap-2 mb-2">
        <span className="text-sm font-semibold text-gray-900">{objection.objection_type}</span>
        <div className="flex items-center gap-2 shrink-0">
          <span className={clsx('px-2 py-0.5 rounded text-[10px] font-bold uppercase', FREQ_STYLE[objection.ai_frequency_label])}>
            {objection.ai_frequency_label}
          </span>
          <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-bold bg-indigo-600 text-white uppercase tracking-wider">
            AI Ranked
          </span>
        </div>
      </div>

      <p className="text-xs text-gray-600 line-clamp-2 mb-3">{objection.objection_text}</p>

      <div className="flex items-center gap-4 text-[11px] text-gray-400">
        <span>{objection.ai_call_count} calls</span>
        <span>·</span>
        <span>{objection.period}</span>
        <span>·</span>
        <span className={clsx('font-medium', objection.ai_success_rate >= 0.5 ? 'text-green-600' : 'text-gray-500')}>
          {(objection.ai_success_rate * 100).toFixed(0)}% Rx conversion
        </span>
        <span>·</span>
        <span className="text-indigo-600 font-medium">Score: {objection.ai_conversion_score.toFixed(0)}</span>
      </div>
    </button>
  )
}
