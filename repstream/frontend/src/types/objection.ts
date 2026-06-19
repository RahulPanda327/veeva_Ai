export type FrequencyLabel = 'HIGH' | 'MEDIUM' | 'LOW'

export interface ObjectionItem {
  objection_id: string
  objection_type: string
  objection_text: string
  period: string
  territory_id: string

  // AI output keys
  ai_frequency_label: FrequencyLabel
  ai_call_count: number
  ai_success_rate: number
  ai_conversion_score: number
}

export interface ObjectionResponse {
  objection_id: string
  objection_type: string
  objection_text: string
  hcp_segment: string | null

  // AI output keys
  ai_mlr_response: string
  ai_response_source: string | null
  ai_sku: string | null
  ai_success_rate: number
  ai_conversion_score: number
  ai_response_highlight: string | null
}

export interface AddToCallPrepResponse {
  success: boolean
  message: string
  objection_id: string
  rep_id: string
}
