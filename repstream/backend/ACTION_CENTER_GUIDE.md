# RepStream — Action Center Module Documentation

> Action Center — Launch & Market Defense
> Real-time competitive intelligence and HCP awareness monitoring for ZENPEP sales reps



---

## KPI Summary Tiles (Top of Page)

These 5 tiles appear at the top of the Action Center page regardless of which tab is active.

**Endpoint:** `GET /api/v1/action-center/alerts/summary`

| Key | Description | Example |
|---|---|---|
| `ai_critical_count` | Number of CRITICAL severity alerts | 3 |
| `ai_high_count` | Number of HIGH severity alerts | 3 |
| `ai_medium_count` | Number of MEDIUM severity alerts | 2 |
| `ai_hcp_drift_detected` | Total HCPs showing awareness decline | 12 |
| `ai_early_detection_weeks` | How many weeks ahead AI detected the threat vs traditional reporting | 2.8 weeks |
| `ai_banner_message` | Yellow banner text shown at top of page | "New alerts require action. Competitive script shifts detected in your territory." |

---

## Module 1 — Active Alerts

### Description
Active Alerts is the main intelligence feed of the Action Center. It uses machine learning to automatically detect three types of threats in the sales rep's territory — competitive threats (competitor gaining Rx share), payer access changes (formulary tier downgrades), and HCP awareness decline (doctors losing awareness of ZENPEP). Each alert is enriched by GPT-4o with a description, counter-script, and recommended actions. Alerts are classified as CRITICAL, HIGH, or MEDIUM priority so the rep always knows what to act on first.

### How It Works
1. IsolationForest ML model detects unusual competitor Rx activity → COMPETITIVE alerts
2. Linear Regression ML model detects gradual HCP Rx drift → HCP_DRIFT alerts
3. Reads payer access table directly from DB → PAYER alerts
4. GPT-4o enriches each alert with title, description, counter-script, and supporting materials
5. Groups alerts into 3 sections and numbers them independently

### Input (what the system needs)
| Field | Description | Source |
|---|---|---|
| `territory_id` | The rep's territory ID | Extracted from login token automatically |

### Output (what the UI receives)

**Alert Cards** — `GET /api/v1/action-center/alerts`

**Competitive Alert Card** (13 keys)

| Key | Description | Example |
|---|---|---|
| `alert_id` | Unique alert identifier | ML-ANOM-001 |
| `ai_severity` | Priority level | CRITICAL / HIGH / MEDIUM / LOW |
| `ai_detection_method` | How the alert was detected | ANOMALY_DETECTION / ML_MODEL |
| `detected_at` | When the alert was detected | 2026-04-28 09:15 |
| `title` | GPT-4o generated alert headline | "Competitive script shift in cardiology segment" |
| `description` | GPT-4o generated description | "Competitor X launched new messaging..." |
| `ai_affected_hcp_count` | Number of HCPs impacted | 23 |
| `ai_territory_reach` | How many sub-territories affected | 3/12 |
| `ai_rx_risk` | Risk level to Rx volume | High |
| `ai_icd10_codes_affected` | Diagnosis codes where shift is happening | [{"code": "K86.81", "label": "EPI", "hcp_count": 8}] |
| `ai_prescribing_drift_note` | GPT-4o note on prescribing drift | "4 HCPs showing 15-20% reduction in Rx volume" |
| `ai_counter_script` | MLR-approved response script for the rep | "While onset time is one factor, our clinical data shows..." |
| `ai_supporting_materials` | Materials to use in response | "APEX Trial Summary, Competitive Positioning Guide" |
| `recommended_actions` | List of actions for the rep | ["Deploy to Field", "View Affected HCPs"] |

**Payer Alert Card** (10 keys)

| Key | Description | Example |
|---|---|---|
| `alert_id` | Unique alert identifier | PA-ALERT-001 |
| `ai_severity` | Priority level | HIGH / MEDIUM / LOW |
| `ai_detection_method` | How detected | AUTO_DETECTED |
| `detected_at` | When the change was detected | 2026-04-25 |
| `title` | Alert headline | "Payer formulary update - Tier change" |
| `description` | What changed | "BlueCross Northeast moved our product from Tier 2 to Tier 3..." |
| `ai_affected_hcp_count` | Number of HCPs affected | 47 |
| `ai_territory_reach` | Covered lives (for payer alerts) | 340 |
| `ai_rx_risk` | Access impact level | Medium |
| `recommended_actions` | Actions from DB | ["View HCP List", "Access Resources"] |

**HCP Awareness Alert Card** (6 keys)

| Key | Description | Example |
|---|---|---|
| `alert_id` | Unique alert identifier | ML-DRFT-001 |
| `ai_severity` | Priority level | MEDIUM |
| `ai_detection_method` | How detected | ML_MODEL |
| `detected_at` | When detected | 2026-04-27 13:15 |
| `title` | Alert headline | "HCP awareness score decline in endocrinology" |
| `description` | What was detected | "3 HCPs showing decreased awareness of key product benefits..." |
| `recommended_actions` | Actions for the rep | ["Schedule Calls", "Review Letter"] |




### API Endpoints

| Purpose | Method | Endpoint |
|---|---|---|
| KPI tiles (5 summary numbers at top) | GET | `/api/v1/action-center/alerts/summary` |
| All alert cards (3 sections) | GET | `/api/v1/action-center/alerts` |
| Re-run ML pipeline for territory | POST | `/api/v1/action-center/detect` |
| Re-enrich one alert with GPT-4o | POST | `/api/v1/action-center/alerts/{alert_id}/enrich` |

---

## Module 2 — HCP Awareness

### Description
HCP Awareness Monitoring tracks how aware each doctor in the territory is of ZENPEP's key product benefits over time. It measures awareness scores across 4 weekly periods and uses linear regression to predict whether scores will continue declining. Each HCP with a declining score is listed with an AI-generated recommended action (schedule a call, send clinical data, etc.) so the rep knows exactly who needs re-engagement and why. The bar chart on the page shows the average awareness score trend across all territory HCPs.

### How It Works
1. Reads 4 weekly awareness scores per HCP from the database (Jan, Feb, Mar, Apr)
2. Runs Linear Regression to calculate the trend slope and predict the next period score
3. Computes an AI Risk Score (0-100) combining score gap, slope severity, and engagement priority
4. NLP classifies the root cause (competitor threat, rep engagement gap, clinical evidence gap, payer access)
5. GPT-4o generates a digital activity description and recommended action for each HCP
6. Sorts HCPs by risk score descending (highest risk first)

### Input (what the system needs)
| Field | Description | Source |
|---|---|---|
| `territory_id` | The rep's territory ID | Extracted from login token automatically |

### Output (what the UI receives)

**Trend Chart Data + HCP Cards** — `GET /api/v1/action-center/hcp-awareness`

**Summary (trend chart)**

| Key | Description | Example |
|---|---|---|
| `awareness_trend` | Average score per period for bar chart | [{"period": "Jan 29", "avg_score": 78.2}, ...] |
| `ai_declining_period` | Date range label shown above HCP list | "Mar 25 - Apr 22, 2026" |

**Each HCP Card**

| Key | Description | Example |
|---|---|---|
| `hcp_full_name` | Doctor's full name | Dr. Thomas Harrison |
| `specialty` | Medical specialty | Cardiology |
| `institution` | Hospital or clinic | Valley Medical Center |
| `ai_awareness_score` | Latest awareness score (%) | 62.0% |
| `ai_awareness_level` | Level label | High / Medium / Low |
| `ai_trend_direction` | Which way the score is moving | Declining / Stable / Improving |
| `ai_score_change_pct` | Total % change over the period | -20.5% |
| `ai_aim_xr_activity` | GPT-4o: what the HCP has been reading/doing | "Reading competitor articles on heart failure outcomes 3x last month" |
| `analysis_badges` | AI techniques applied | NLP_ANALYSIS, AI_SCORING, PREDICTIVE_ANALYTICS |

### API Endpoints

| Purpose | Method | Endpoint |
|---|---|---|
| Trend chart + HCP awareness cards | GET | `/api/v1/action-center/hcp-awareness` |

---

## Module 3 — Competitive Intel

### Description
Competitive Intelligence Feeds provides real-time monitoring of competitor activity in the rep's territory. It automatically detects when a competitor (like Creon or Pancreaze) is increasing rep visits, gaining market share, or running messaging campaigns targeting ZENPEP's HCPs. Each signal is scored by threat level and enriched by GPT-4o with an executive summary, business impact statement, and 3 recommended actions the rep should take immediately. Signals are color-coded: red = Critical/High threat, orange = Medium, blue = Low.

### How It Works
1. Reads competitive intelligence signals from the database
2. AI Threat Score combines market share change, competitor call frequency change, and signal type
3. Linear Regression projects how much additional market share could be lost in 4 weeks
4. NLP classifies the signal type (messaging claim, market share threat, rep activity, formulary)
5. GPT-4o generates headline, executive summary, business impact, and 3 talking points
6. Sorts by threat level: Critical → High → Medium → Low

### Input (what the system needs)
| Field | Description | Source |
|---|---|---|
| `territory_id` | The rep's territory ID | Extracted from login token automatically |
| `featured` | Optional: return only top 3 (one per threat tier) | Query param `?featured=true` |

### Output (what the UI receives)

**Competitive Signal Feed** — `GET /api/v1/action-center/competitive-intel`

| Key | Description | Example |
|---|---|---|
| `signal_id` | Unique signal identifier | SIG-001 |
| `signal_type` | How it was detected | AI DETECTED / ML TREND / ANOMALY |
| `signal_date` | When it was detected | 2026-04-28 |
| `competitor_brand` | Which competitor | CREON / PANCREAZE |
| `territory_name` | Territory where detected | BAY RIDGE, NY |
| `rx_change_percent` | Rx volume change for ZENPEP | -4.2% |
| `activity_change_percent` | Competitor rep visit increase | +68% |
| `risk_level` | Threat level | HIGH / MEDIUM / LOW |
| `urgency_level` | How fast rep should respond | IMMEDIATE / STANDARD / ROUTINE |
| `headline` | GPT-4o one-line headline | "Competitor X New Efficacy Claims" |
| `executive_summary` | GPT-4o 2-3 sentence summary | "Detected messaging around 'superior efficacy' in 5 HCP interactions..." |
| `business_impact` | GPT-4o revenue risk statement | "1.2% market share gain in cardiology segment Apr 13-27..." |
| `recommended_actions` | GPT-4o 3 action steps | ["Schedule urgent calls with top prescribers", ...] |
| `field_force_talking_points` | GPT-4o 3 talking points for HCP conversations | ["ZENPEP's APEX trial demonstrates...", ...] |
| `counter_strategy` | DB-stored counter messaging | "Deploy APEX trial head-to-head data..." |
| `analysis_badges` | AI techniques applied | AI_DETECTED / ML_TREND / ANOMALY |

### API Endpoints

| Purpose | Method | Endpoint |
|---|---|---|
| All competitive signals (full list) | GET | `/api/v1/action-center/competitive-intel` |
| Top 1 per threat tier (max 3) | GET | `/api/v1/action-center/competitive-intel?featured=true` |

---

## Module 7 — Payer Access

### Description
Payer Access Monitoring tracks the formulary status of ZENPEP across all major insurance payers (BlueCross, Aetna, UnitedHealthcare, etc.) in the rep's territory. It automatically detects when a payer downgrades ZENPEP to a worse tier (making it harder for patients to get), estimates how many patients might abandon their prescription, and generates a prior authorization bridge note for the rep to use. Payers flagged with AI_ALERT (tier change detected) are shown first, stable payers are shown after.

### How It Works
1. Reads all payer records from the `payer_access` database table
2. AI Impact Score combines tier change direction, covered lives, PA requirement, and channel type
3. ML model predicts patient abandonment % and count based on the new tier (e.g., Tier 3 = 18% abandonment risk)
4. NLP classifies the recommended action type (formulary change, PA required, access win, monitoring)
5. GPT-4o generates impact summary, 3-step action plan, and PA bridge note (for payers requiring prior auth)
6. Sorts: AI_ALERT payers first, then by impact score descending

### Input (what the system needs)
| Field | Description | Source |
|---|---|---|
| `territory_id` | The rep's territory ID | Extracted from login token automatically |
| `featured` | Optional: return only top 3 (one per status tier) | Query param `?featured=true` |

### Output (what the UI receives)

**Payer Cards** — `GET /api/v1/action-center/payer-access`

**Each Payer Card**

| Key | Description | Example |
|---|---|---|
| `plan_id` | Unique payer plan ID | PA-001 |
| `payer_name` | Insurance company name | BlueCross Northeast |
| `mco_org_name` | Parent MCO organization | BlueCross BlueShield |
| `channel_name` | Insurance channel | Commercial / Medicare / Medicaid |
| `tier_current` | Current formulary tier | Tier 3 |
| `tier_previous` | Previous formulary tier | Tier 2 |
| `tier_label_current` | Human-readable tier label | Preferred / Standard / Non-preferred |
| `change_date` | When the tier change happened | 2026-04-25 |
| `pa_required` | Is prior authorization required | Yes / No |
| `covered_lives` | Number of patients covered by this plan | 340,000 |
| `affected_hcp_count` | Number of HCPs affected in territory | 47 |
| `status_badge` | Alert status | AI_ALERT / STABLE |
| `change_badge` | Whether a change was detected | CHANGE_DETECTED / null |
| `ai_tier_change_direction` | Direction of tier change | DOWNGRADE / UPGRADE / UNCHANGED |
| `ai_impact_level` | Impact severity | High / Medium / Low |
| `ai_abandonment_risk_pct` | % of patients likely to abandon Rx | 18.0% |
| `ai_projected_patient_impact` | Estimated number of patients at risk | 51 |
| `ai_impact_summary` | GPT-4o one-sentence business impact | "BlueCross tier downgrade affects 340,000 covered lives..." |
| `ai_action_plan` | GPT-4o 3-step action plan | ["Alert field reps...", "Provide PA bridge scripts...", "Enroll patients..."] |
| `ai_pa_bridge_note` | GPT-4o prior auth clinical rationale | "For BlueCross: emphasize clinical necessity of Zenpep..." |
| `recommended_action` | Original DB recommended action text | "Alert field reps — immediate PA bridge script needed..." |
| `analysis_badges` | AI techniques applied | AI_SCORING, AI_ALERT, PREDICTIVE_ANALYTICS, NLP_ANALYSIS |
| `ai_is_flagged` | Whether this payer triggered an AI alert | true / false |

**Response Summary Counts**

| Key | Description |
|---|---|
| `ai_alert_count` | Number of payers with active AI alerts |
| `ai_stable_count` | Number of payers with no change |
| `ai_tier_downgrade_count` | Number of payers that downgraded |
| `ai_high_impact_count` | Number of high-impact payer changes |
| `ai_total_covered_lives_at_risk` | Total covered lives across alerted payers |
| `ai_total_affected_hcps` | Total HCPs affected across alerted payers |

### API Endpoints

| Purpose | Method | Endpoint |
|---|---|---|
| All payer cards (full list) | GET | `/api/v1/action-center/payer-access` |
| Top 3 payers (one per status tier) | GET | `/api/v1/action-center/payer-access?featured=true` |

---

## All Action Center Endpoints — Quick Reference

| Module | Method | Endpoint |
|---|---|---|
| Summary KPI tiles | GET | `/api/v1/action-center/alerts/summary` |
| Active Alerts (3 sections) | GET | `/api/v1/action-center/alerts` |
| HCP Awareness | GET | `/api/v1/action-center/hcp-awareness` |
| Competitive Intel | GET | `/api/v1/action-center/competitive-intel` |
| Payer Access | GET | `/api/v1/action-center/payer-access` |

---

## DB Tables Used (Action Center)

| Module | DB Table | Purpose |
|---|---|---|
| Active Alerts | `insight360_active_alerts` | Pre-computed alert rows |
| Active Alerts | `payer_access` | Payer change data for payer alerts |
| HCP Awareness | `insight360_hcp_awareness` | Weekly awareness scores per HCP |
| Competitive Intel | `insight360_competitive_intel` | Competitor signal data |
| Payer Access | `payer_access` | Full payer formulary status |
