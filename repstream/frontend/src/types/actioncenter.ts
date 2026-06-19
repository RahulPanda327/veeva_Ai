export interface ICD10Affected {
  code: string;
  label: string;
  hcp_count: number;
}

export interface SupportingMaterial {
  title: string;
  sku?: string | null;
}

// ─── Active Alerts ───────────────────────────────────────────────────────────

export type AlertSeverity = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
export type AlertDetectionMethod = "ANOMALY_DETECTION" | "AUTO_DETECTED" | "ML_MODEL";

export interface AlertItem {
  alert_id: string;
  alert_type: string;
  title: string;
  description: string;
  detected_at: string;
  period?: string;

  // AI detection metadata
  ai_severity: AlertSeverity;
  ai_detection_method: AlertDetectionMethod;

  // AI impact analysis
  ai_affected_hcp_count: number;
  ai_territory_reach?: string;
  ai_rx_risk?: string;
  ai_icd10_codes_affected: ICD10Affected[];
  ai_prescribing_drift_note?: string;
  ai_detection_lead_weeks?: number;

  // AI counter-script
  ai_counter_script?: string;
  ai_supporting_materials: SupportingMaterial[];

  is_acknowledged: boolean;
  is_dismissed: boolean;
  is_deployed: boolean;
  ai_is_detected: boolean;
}

export interface ActionCenterSummary {
  territory_id: string;
  period: string;
  last_refresh: string;
  ai_critical_count: number;
  ai_high_priority_count: number;
  ai_medium_priority_count: number;
  ai_hcp_drift_detected_count: number;
  ai_early_detection_weeks: number;
  ai_new_unread_count: number;
  ai_banner_message?: string;
}

export interface AlertListResponse {
  summary: ActionCenterSummary;
  alerts: AlertItem[];
  total: number;
}

// ─── HCP Awareness ───────────────────────────────────────────────────────────

export type AwarenessLevel = "High" | "Medium" | "Low";

export interface HCPAwarenessItem {
  awareness_id: string;
  hcp_id: string;
  hcp_full_name: string;
  specialty?: string;
  territory_id: string;
  period?: string;
  product_awareness_score: number;
  competitor_awareness_score: number;
  clinical_evidence_score: number;
  total_interactions: number;
  last_interaction_date?: string;
  ai_awareness_score: number;
  ai_awareness_level: AwarenessLevel;
  ai_key_messages_delivered: string[];
  ai_knowledge_gaps: string[];
  ai_recommended_action?: string;
  ai_is_assessed: boolean;
}

export interface HCPAwarenessResponse {
  items: HCPAwarenessItem[];
  total: number;
  ai_high_awareness_count: number;
  ai_medium_awareness_count: number;
  ai_low_awareness_count: number;
}

// ─── Competitive Intel ───────────────────────────────────────────────────────

export type ThreatLevel = "High" | "Medium" | "Low";

export interface CompetitiveIntelItem {
  intel_id: string;
  competitor_name: string;
  territory_id: string;
  period?: string;
  message_theme?: string;
  detection_date?: string;
  affected_hcp_count: number;
  market_share_change_pct: number;
  icd10_focus: ICD10Affected[];
  source_channel?: string;
  ai_threat_score: number;
  ai_threat_level: ThreatLevel;
  ai_counter_strategy?: string;
  ai_supporting_evidence?: string;
  ai_detection_method?: string;
  ai_is_analyzed: boolean;
}

export interface CompetitiveIntelResponse {
  items: CompetitiveIntelItem[];
  total: number;
  ai_high_threat_count: number;
  ai_medium_threat_count: number;
  ai_avg_threat_score: number;
}

// ─── Payer Access ─────────────────────────────────────────────────────────────

export type AccessImpact = "High" | "Medium" | "Low";

export interface PayerAccessItem {
  access_id: string;
  payer_name: string;
  territory_id: string;
  period?: string;
  product_tier_current?: number;
  product_tier_previous?: number;
  tier_change_date?: string;
  formulary_status?: string;
  covered_lives: number;
  affected_hcp_count: number;
  patient_assistance_available: boolean;
  ai_impact_score: number;
  ai_access_impact: AccessImpact;
  ai_action_required?: string;
  ai_patient_assistance_note?: string;
  ai_tier_change_direction?: string;
  ai_is_flagged: boolean;
}

export interface PayerAccessResponse {
  items: PayerAccessItem[];
  total: number;
  ai_high_impact_count: number;
  ai_total_covered_lives_at_risk: number;
  ai_total_affected_hcps: number;
}
