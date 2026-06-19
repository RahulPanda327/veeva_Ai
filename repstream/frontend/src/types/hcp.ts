export type PriorityTier = 'HIGH' | 'MEDIUM' | 'LOW'

export interface TerritorySummary {
  total_hcps: number
  high_priority_count: number
  medium_priority_count: number
  low_priority_count: number
  weekly_target: number
  period: string               // e.g. "Q1 2026 (Jan - Mar)"
  last_refresh: string         // e.g. "Apr 28, 2026 8:15 AM"
  territory_id: string
  territory_name: string | null
}

export interface HCPRankedItem {
  // Identity
  hcp_id: string
  name: string
  specialty: string | null
  affiliated_hospital: string | null
  territory_id: string
  segment: string | null
  city: string | null
  state: string | null
  decile_rank: number | null

  // Rx metrics
  rx_q1: number
  rx_q4: number
  rx_trend_pct: number
  competitor_brand: string | null
  competitor_brand_share: number

  // Call interaction
  last_call_date: string | null
  days_since_last_call: number | null
  call_count_90d: number
  last_call_outcome: string | null

  // AI output keys
  ai_priority_score: number           // 0-100 composite (60/30/10)
  ai_priority_tier: PriorityTier
  ai_trx_growth_norm: number          // TRx component 0-100
  ai_interaction_impact: number       // Interaction component 0-100
  ai_decile_score_norm: number        // Decile component 0-100
  ai_generated_insight: string | null
  ai_insight_highlight: string | null // rendered in green
  ai_is_ranked: boolean
}

export interface HCPInsightResponse {
  hcp_id: string
  ai_generated_insight: string
  ai_insight_highlight: string | null
  generated_at: string
  cached: boolean
}
