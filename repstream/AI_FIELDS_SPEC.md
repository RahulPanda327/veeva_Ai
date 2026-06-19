# RepStream — AI Fields Specification

Complete contract of every `ai_*` key produced by each module,
where it is computed, and how the UI renders it.

---

## Module 1 — Territory Prioritization

### Computation pipeline

```
DB tables                  Service layer               API response key
─────────────────────────────────────────────────────────────────────────
vw_tfact_prescribersales   feature_engineering.py
  total_rx (Q1, Q4)    ──► rx_trend_pct              → rx_trend_pct
                        ──► ai_trx_growth_norm         → ai_trx_growth_norm   (normalised 0-100)

vw_tfact_callactivity      data_ingestion.py
  call_date, outcome   ──► days_since_last_call        → days_since_last_call
  call_count 90d       ──► call_count_90d              → call_count_90d
  call_outcome         ──► last_call_outcome           → last_call_outcome

                           ai_score.py
  (above inputs)       ──► ai_interaction_impact       → ai_interaction_impact (0-100)
                           (50% recency + 30% frequency + 20% outcome)

vw_tdim_hcp
  decile_rank          ──► ai_decile_score_norm        → ai_decile_score_norm  (0-100)

                           ai_score.py
  trx_norm × 0.60
  interaction × 0.30
  decile × 0.10        ──► ai_priority_score           → ai_priority_score    (0-100 composite)
                       ──► ai_priority_tier            → ai_priority_tier     (HIGH/MEDIUM/LOW)
                              ≥65 → HIGH
                              35-64 → MEDIUM
                              <35  → LOW

                           llm_insight.py (GPT-4o)
  rx_trend, competitor
  score, last call     ──► ai_generated_insight        → ai_generated_insight (≤25-word sentence)
                       ──► ai_insight_highlight        → ai_insight_highlight (3-8 word phrase → green UI)
```

### Formula reference

| Component | Weight | Input | Normalisation |
|---|---|---|---|
| TRx Growth | **60%** | `rx_trend_pct` | `(growth + 50) / 200 × 100`, capped [-50%, +150%] → [0, 100] |
| Interaction Impact | **30%** | days since call, 90d call count, last outcome | `50% recency + 30% freq + 20% outcome` |
| Decile Score | **10%** | `decile_rank` (1=best, 10=worst) | `(10 - rank) / 9 × 100` |
| **AI Priority Score** | — | Above three | Weighted sum → 0-100 |

### UI rendering

| API key | UI element |
|---|---|
| `ai_priority_tier` | Card badge: orange **HIGH PRIORITY** / blue **MEDIUM PRIORITY** / gray **LOW PRIORITY** |
| `ai_generated_insight` | "AI-Generated Insight" text block |
| `ai_insight_highlight` | Same block, key phrase rendered in **green** |
| `ai_priority_score` | Footer metric "AI Score: 78/100" |
| `ai_interaction_impact` | Footer metric (future: score bar) |
| `ai_is_ranked` | Purple **AI RANKED** badge on KPI tiles |

---

## Module 2 — New Writer Identification

### Computation pipeline

```
DB tables                  Service layer               API response key
─────────────────────────────────────────────────────────────────────────
vw_tfact_prescribersales
  is_brand = 0         ──► in_class_rx_q1             → in_class_rx_q1
  is_brand = 1 (Q1)    ──► brand_rx_q1 = 0 (filter)  → brand_rx_q1
  is_brand = 1 (Q4)    ──► brand_rx_q4 = 0 (filter)  → brand_rx_q4
                       ──► ai_non_writer_flag = True  → ai_non_writer_flag

insight360_peer_match
  match_score          ──► ai_peer_match_score        → ai_peer_match_score (0-100)
  peer_hcp_name        ──► ai_peer_name               → ai_peer_name
  match_rationale      ──► ai_peer_rationale          → ai_peer_rationale

vw_tdim_hcp
  icd10_codes          ──► icd10_matching.py
  TARGET_ICD10_CODES   ──► ai_icd10_matched_codes     → ai_icd10_matched_codes (list)
                       ──► ai_icd10_match_count       → ai_icd10_match_count

                           approach_brief.py (GPT-4o, on demand)
  name, peer, ICD-10   ──► ai_approach_brief          → ai_approach_brief (2 sentences)
  competitor info      ──► ai_approach_highlight      → ai_approach_highlight (green phrase)
```

### UI rendering

| API key | UI element |
|---|---|
| `ai_non_writer_flag` | Teal **NON-WRITER** badge |
| `ai_peer_match_score` | Peer affinity progress bar (0-100%) |
| `ai_peer_name` | "AI Peer Match — via Dr. X" label |
| `ai_icd10_matched_codes` | Teal ICD-10 code pills |
| `ai_icd10_match_count` | Footer metric |
| `ai_approach_brief` | "AI-Generated Approach Brief" block (on demand) |
| `ai_approach_highlight` | Same block, key phrase in green |

---

## Module 3 — Objection Handler

### Computation pipeline

```
DB tables                  Service layer               API response key
─────────────────────────────────────────────────────────────────────────
insight360_objection_handler
  call_count           ──► objection_classifier.py
                       ──► ai_frequency_label         → ai_frequency_label (HIGH/MEDIUM/LOW)
                              >8   → HIGH
                              3-8  → MEDIUM
                              <3   → LOW

  success_rate         ──► ai_success_rate            → ai_success_rate (0-1)
                       ──► ai_conversion_score        → ai_conversion_score (× 100 → 0-100)

  recommended_response ──► ai_mlr_response            → ai_mlr_response
  response_source      ──► ai_response_source         → ai_response_source
  sku                  ──► ai_sku                     → ai_sku
                           _extract_response_highlight
                       ──► ai_response_highlight      → ai_response_highlight (green phrase)
```

### UI rendering

| API key | UI element |
|---|---|
| `ai_frequency_label` | Orange **HIGH** / blue **MEDIUM** / gray **LOW** badge |
| `ai_call_count` | "{N} calls" in card footer |
| `ai_success_rate` | "{N}% Rx conversion" in card footer |
| `ai_conversion_score` | "Score: {N}" in response panel |
| `ai_mlr_response` | Green "MLR-Approved Response" block |
| `ai_response_source` | Document reference (e.g. "MLR-v3.1") |
| `ai_sku` | Product SKU metric tile |
| `ai_response_highlight` | Key phrase in green within response text |

---

## Summary — all `ai_*` keys by module

| Key | Module | Type | Source |
|---|---|---|---|
| `ai_priority_score` | M1 | float 0-100 | Computed (60/30/10) |
| `ai_priority_tier` | M1 | HIGH/MED/LOW | Threshold on score |
| `ai_trx_growth_norm` | M1 | float 0-100 | Normalised Rx trend |
| `ai_interaction_impact` | M1 | float 0-100 | Call stats |
| `ai_decile_score_norm` | M1 | float 0-100 | Normalised decile rank |
| `ai_generated_insight` | M1 | string | GPT-4o (cached 24h) |
| `ai_insight_highlight` | M1 | string\|null | Extracted from GPT-4o JSON |
| `ai_is_ranked` | M1 | bool | Always true |
| `ai_non_writer_flag` | M2 | bool | Rx filter logic |
| `ai_peer_match_score` | M2 | float 0-100 | insight360_peer_match |
| `ai_peer_name` | M2 | string\|null | insight360_peer_match |
| `ai_peer_rationale` | M2 | string\|null | insight360_peer_match |
| `ai_icd10_matched_codes` | M2 | string[] | ICD-10 filter |
| `ai_icd10_match_count` | M2 | int | Count of above |
| `ai_approach_brief` | M2 | string\|null | GPT-4o on demand (cached 1h) |
| `ai_approach_highlight` | M2 | string\|null | Extracted from brief |
| `ai_frequency_label` | M3 | HIGH/MED/LOW | Call count threshold |
| `ai_call_count` | M3 | int | insight360_objection_handler |
| `ai_success_rate` | M3 | float 0-1 | insight360_objection_handler |
| `ai_conversion_score` | M3 | float 0-100 | success_rate × 100 |
| `ai_mlr_response` | M3 | string | insight360_objection_handler |
| `ai_response_source` | M3 | string\|null | MLR document reference |
| `ai_sku` | M3 | string\|null | insight360_objection_handler |
| `ai_response_highlight` | M3 | string\|null | Extracted from response |
