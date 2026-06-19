import { ShieldCheck } from 'lucide-react'
import type { ObjectionResponse } from '../../types/objection'
import AddToCallPrepButton from './AddToCallPrepButton'

interface Props {
  response: ObjectionResponse
}

function ResponseText({ text, highlight }: { text: string; highlight: string | null }) {
  if (!highlight || !text.includes(highlight)) return <span className="text-sm text-gray-700">{text}</span>
  const [before, after] = text.split(highlight)
  return (
    <span className="text-sm text-gray-700">
      {before}<span className="text-green-600 font-medium">{highlight}</span>{after}
    </span>
  )
}

export default function MLRResponseBlock({ response }: Props) {
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-5 sticky top-4">
      {/* Header */}
      <div className="flex items-center gap-2 mb-4">
        <ShieldCheck className="w-4 h-4 text-green-600" />
        <h3 className="font-semibold text-gray-900 text-sm">MLR-Approved Response</h3>
        {response.ai_response_source && (
          <span className="ml-auto text-[11px] text-gray-400">{response.ai_response_source}</span>
        )}
      </div>

      {/* AI Insight label */}
      <div className="flex items-center justify-between mb-2">
        <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">AI-Generated Script</p>
        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-bold bg-indigo-600 text-white uppercase tracking-wider">
          AI Insight
        </span>
      </div>

      {/* Response text */}
      <div className="bg-green-50 border border-green-100 rounded-lg p-4 mb-4">
        <ResponseText text={response.ai_mlr_response} highlight={response.ai_response_highlight} />
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-3 gap-3 mb-4">
        {response.ai_sku && (
          <div className="bg-gray-50 rounded-lg p-2 text-center">
            <p className="text-[10px] text-gray-400">SKU</p>
            <p className="text-xs font-semibold text-gray-900">{response.ai_sku}</p>
          </div>
        )}
        <div className="bg-gray-50 rounded-lg p-2 text-center">
          <p className="text-[10px] text-gray-400">Rx Conversion</p>
          <p className="text-sm font-bold text-green-700">{(response.ai_success_rate * 100).toFixed(0)}%</p>
        </div>
        <div className="bg-indigo-50 rounded-lg p-2 text-center">
          <p className="text-[10px] text-gray-400">AI Score</p>
          <p className="text-sm font-bold text-indigo-700">{response.ai_conversion_score.toFixed(0)}/100</p>
        </div>
      </div>

      <AddToCallPrepButton objectionId={response.objection_id} />
    </div>
  )
}
