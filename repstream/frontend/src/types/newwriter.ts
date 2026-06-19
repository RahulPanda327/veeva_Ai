export interface NewWriterCandidate {
  hcp_id: string
  name: string
  specialty: string | null
  city: string | null
  state: string | null
  territory_id: string
  segment: string | null
  in_class_rx_q1: number
  brand_rx_q1: number
  brand_rx_q4: number
  competitor_brand: string | null
  competitor_volume: number

  // AI output keys
  ai_peer_match_score: number          // 0-100
  ai_peer_name: string | null
  ai_peer_hcp_id: string | null
  ai_peer_rationale: string | null
  ai_icd10_matched_codes: string[]
  ai_icd10_match_count: number
  ai_non_writer_flag: boolean
  ai_approach_brief: string | null
  ai_approach_highlight: string | null
}

export interface ApproachBriefResponse {
  hcp_id: string
  ai_approach_brief: string
  ai_approach_highlight: string | null
  ai_peer_name: string | null
  generated_at: string
  cached: boolean
}
