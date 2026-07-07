# RepStream — Module Documentation

> AI-powered intelligence platform for pharmaceutical sales representatives (ZENPEP)

---

## Changelog — Key Changes in This Revision

**Module 1 — Territory Prioritization**
- `hcp-list` response trimmed: removed `affiliated_hospital`, `ai_priority_score`, `last_call_date`, `ai_rx_trend_direction`, `ai_predicted_next_q_rx`, `ai_engagement_category`, `ai_engagement_urgency`, `analysis_badges`
- Added `view_profile` (nested HCP contact/profile object) and `last_rx_date` (replaces `last_call_date`)
- New endpoint: `GET /territory/hcp/{hcp_id}/profile` (optional — same data is already in `view_profile`)
- `ai_generated_insight` is now genuinely AI-generated per HCP in the background (real GPT-4o call, not a template), filling in progressively after each page load

**Module 2 — New Writer ID**
- Candidate list now sourced from the peer-match model, enriched with live Rx history
- `last_nrx_date`, `total_in_class_rx`, `top_5_in_class_rx` are now live values (previously always empty); the latter two use a trailing 4-quarter window
- `affiliated_hospital` and `ai_icd10_matched_codes` return `""` when no source data exists (previously `null`/`[]`)
- New `approach_brief` object embedded in every card — a full AI-drafted outreach email (subject, body, HCP's real email address) and talking points, generated automatically in the background

**Module 3 — Objection Handler**
- `ai_supporting_materials` is now the real `ai_mlr_response` text combined with its `ai_sku`, both from the database — no longer a generic hardcoded material name

---

## Module 1 — Territory Prioritization

### Description
Territory Prioritization uses AI and machine learning to automatically rank every HCP (doctor) in a sales rep's territory based on how likely they are to prescribe ZENPEP. The system analyzes prescription history, competitor activity, call frequency, and HCP decile rank to generate a priority score for each doctor. Each HCP is classified as High, Medium, or Low priority so the rep always knows who to visit first. A GPT-4o generated insight is provided for each HCP to help the rep prepare for the visit.

### How It Works
1. Pulls HCP identity, Rx totals (current + prior quarter), and awareness/segment data from the database in one query
2. Runs AI composite scoring (TRx growth + call interaction + decile) to assign a priority tier
3. Sorts all HCPs by priority tier (HIGH → MEDIUM → LOW)
4. Returns the ranked list instantly; a GPT-4o insight is generated for each HCP in the background and appears within a few minutes (first load shows a placeholder line until ready)

### Input (what the system needs)
| Field | Description | Source |
|---|---|---|
| `territory_id` | The rep's territory ID | Extracted from login token automatically |

### Output (what the UI receives)

**KPI Summary Tiles** — `GET /api/v1/territory/summary`

| Key | Description | Example |
|---|---|---|
| `total_hcps` | Total number of HCPs in territory | 127 |
| `high_priority_count` | Number of HIGH priority HCPs | 34 |
| `medium_priority_count` | Number of MEDIUM priority HCPs | 58 |
| `low_priority_count` | Number of LOW priority HCPs | 35 |
| `weekly_target` | Recommended visits this week | 22 |
| `last_refresh` | When data was last calculated | Apr 28, 2026 8:15 AM |
| `period` | Current quarter | Q1 2026 (Jan - Mar) |

**HCP Cards List** — `GET /api/v1/territory/hcp-list`

> **Updated:** this response is now trimmed to the fields below only. `affiliated_hospital`, `ai_priority_score`, `last_call_date`, `ai_rx_trend_direction`, `ai_predicted_next_q_rx`, `ai_engagement_category`, `ai_engagement_urgency`, and `analysis_badges` are no longer returned. A new `view_profile` object (full HCP contact/profile detail) is now embedded in every card instead.

| Key | Description | Example |
|---|---|---|
| `hcp_id` | Unique HCP identifier | 3368938 |
| `name` | Doctor's full name | Arthur Magun |
| `specialty` | Medical specialty | Gastroenterology |
| `segment` | HCP segment (target-plan segment; may be blank if no plan record exists for this HCP) | High |
| `view_profile` | Full HCP profile object — see table below | see below |
| `rx_q1` | ZENPEP Rx written in current quarter | 1200 |
| `rx_q4` | ZENPEP Rx written in prior quarter | 300 |
| `last_rx_date` | Most recent date this HCP had any ZENPEP Rx activity | Apr 30, 2026 |
| `ai_priority_tier` | AI-assigned priority level | HIGH / MEDIUM / LOW |
| `ai_generated_insight` | GPT-4o written insight for the visit, generated in the background from this HCP's own real Rx numbers; shows an instant placeholder line until the AI version is ready | "Your ZENPEP prescriptions have increased by 300% this quarter to 1200, with no competitor brand share..." |

**`view_profile` object** (nested inside every HCP card)

| Key | Description | Example |
|---|---|---|
| `formatted_name` | HCP name | Arthur Magun |
| `specialist_description` | Specialty | Gastroenterology |
| `is_ama_do_not_contact` | AMA do-not-contact flag | N |
| `email` | HCP's email address | magunmd@earthlink.net |
| `hcp_status` | Active/Inactive status | Active |
| `hcp_type` | HCP type | Prescriber |
| `medical_degree` | Medical degree | MD |
| `npi` | NPI number | 1790865012 |
| `pdrp_output` | PDRP opt-out flag | N |
| `website` | HCP's practice website | https://www.nyp.org/physician/ammagun |
| `target` | Target flag | N |
| `city` | City | New York |
| `address` | Street address | 180 Fort Washington Ave Ste 254 |
| `state` | State | NY |

### API Endpoints

| Purpose | Method | Endpoint |
|---|---|---|
| KPI Tiles (5 summary numbers at top) | GET | `/api/v1/territory/summary` |
| HCP Cards List (main ranked list) | GET | `/api/v1/territory/hcp-list` |
| Regenerate insight for one HCP | GET | `/api/v1/territory/hcp/{hcp_id}/insight` |
| View Profile for one HCP *(optional — same data already embedded as `view_profile` in the list above)* | GET | `/api/v1/territory/hcp/{hcp_id}/profile` |

---

## Module 2 — New Writer ID

### Description
New Writer Identification uses machine learning to automatically find doctors in the territory who are already prescribing ZENPEP's competitor drugs (like CREON) but have never written a single ZENPEP prescription. These are high-value conversion targets. The system matches each non-writer HCP to an existing ZENPEP writer (peer) who has a similar profile, giving the rep a warm introduction angle. It also matches the doctor's diagnosis codes (ICD-10) to ZENPEP's target conditions to confirm clinical relevance.

### How It Works
1. Uses the peer-match model as the candidate list — HCPs identified upstream as having a warm peer connection to an existing ZENPEP writer — enriched live with HCP profile, territory, and Rx history
2. Peer match score and warm approach text are read directly from the peer-match data where available
3. Matches the HCP's diagnosis codes against ZENPEP's target ICD-10 codes (returns an empty value when no diagnosis data exists for that HCP)
4. Generates a full AI outreach email (subject, body, and talking points) per HCP in the background, addressed to the HCP's real email address
5. Sorts by peer match score (highest first)

### Input (what the system needs)
| Field | Description | Source |
|---|---|---|
| `territory_id` | The rep's territory ID | Extracted from login token automatically |

### Output (what the UI receives)

**New Writer Candidate Cards** — `GET /api/v1/new-writers/candidates`

> **Updated:** `last_nrx_date`, `total_in_class_rx`, and `top_5_in_class_rx` are now live database values (previously placeholders). `total_in_class_rx` and `top_5_in_class_rx` reflect a trailing 4-quarter window, not the current quarter only, so the brand table stays populated even in a quiet quarter. `affiliated_hospital` and `ai_icd10_matched_codes` are returned as an empty string `""` when no data exists — no source column for hospital affiliation or ICD-10 codes currently exists in the database for this HCP view. A new `approach_brief` object (full AI-drafted outreach email) is now embedded in every card.

| Key | Description | Example |
|---|---|---|
| `hcp_id` | Unique HCP identifier | 3364060 |
| `name` | Doctor's full name | Jessica Fligge |
| `specialty` | Medical specialty | Family Medicine |
| `affiliated_hospital` | Hospital or clinic name — no source data available, always `""` | "" |
| `city` / `state` | HCP's location | Graceville / MN |
| `segment` | HCP segment | Low |
| `last_nrx_date` | Last date doctor wrote any new in-class Rx | Jan 30, 2026 |
| `total_in_class_rx` | Total competitor Rx written (trailing 4 quarters) | 3 |
| `top_5_in_class_rx` | Top competitor brands this HCP prescribes with volumes (trailing 4 quarters) | [{"brand": "CREON", "rx": 23}] |
| `competitor_brand` | HCP's highest-volume competitor brand | CREON |
| `ai_warm_approach_text` | Opening line for the rep — real peer-match text when available in the database, otherwise a GPT-4o line generated from this HCP's own Rx numbers | "Dr. Robert Taylor at Dallas Medical has seen strong results with Zenpep for EPI patients..." |
| `ai_peer_match_score` | How similar this HCP is to an existing ZENPEP writer (%) | 87.9 |
| `ai_peer_name` | Name of the matched existing ZENPEP writer | Dr. Robert Taylor |
| `ai_icd10_matched_codes` | ICD-10 diagnosis codes that match ZENPEP targets — `""` when no diagnosis data exists | "" |
| `ai_icd10_match_count` | Number of matching ICD-10 codes | 0 |
| `approach_brief` | Full AI-generated outreach email and talking points, ready to send — see table below | see below |
| `analysis_badges` | AI badges applied | ML_PATTERN_MATCHING, AI_GENERATED |

**`approach_brief` object** (nested inside every candidate card — generated automatically in the background, no button click required)

| Key | Description | Example |
|---|---|---|
| `email.to` | HCP's real email address | eperdomo72@hotmail.com |
| `email.to_name` | HCP's name, cleaned for display | Elizabeth Perdomo |
| `email.subject` | AI-generated email subject line | "Exploring Flexible Dosing Options with ZENPEP for Your Patients" |
| `email.email_body` | Full AI-generated email body, personalized to this HCP's Rx history and peer connection | "Dear Dr. Perdomo, I hope this message finds you well..." |
| `key_discussion_points` | 3 AI-generated talking points for the rep's visit | ["Flexible dosing with 5 strengths...", "Non-enteric-coated microsphere formulation", "ZenConnect co-pay program..."] |

**Approach Brief (on-demand, button click)** — `POST /api/v1/new-writers/{hcp_id}/approach-brief`

*Unchanged — generates a short 2-3 sentence brief on demand, separate from the auto-generated `approach_brief` email above.*

| Key | Description |
|---|---|
| `ai_approach_brief` | Full GPT-4o written warm approach brief (2-3 sentences) |
| `ai_approach_highlight` | Key phrase highlighted from the brief |
| `ai_peer_name` | Peer doctor's name used in the brief |
| `generated_at` | Timestamp when the brief was generated |

### API Endpoints

| Purpose | Method | Endpoint |
|---|---|---|
| New Writer candidate cards (main list) | GET | `/api/v1/new-writers/candidates` |
| Generate full approach brief (on button click) | POST | `/api/v1/new-writers/{hcp_id}/approach-brief` |

---

## Module 3 — Objection Handler

### Description
Objection Handler uses Natural Language Processing (NLP) to automatically scan call transcripts and identify the most common objections HCPs raise about ZENPEP. It then surfaces the best MLR-approved (legally reviewed) response for each objection, along with the historical success rate for that response. Objections are ranked by how frequently they appear (HIGH → MEDIUM → LOW), so the rep can prepare for the most likely pushbacks before visiting a doctor. The rep can also save any objection to their next call prep for quick access before a visit.

### How It Works
1. Reads all objections recorded in call transcripts from the database
2. Calculates frequency (how many calls it appeared in) and success rate for each objection
3. Fetches the best MLR-approved response for each objection from the database
4. Classifies each objection as HIGH (>10 calls), MEDIUM (5-9 calls), or LOW (<5 calls)
5. Sorts all objections: HIGH first, then MEDIUM, then LOW

### Input (what the system needs)
| Field | Description | Source |
|---|---|---|
| `territory_id` | The rep's territory ID | Extracted from login token automatically |
| `period` | Optional date range filter | Query parameter (e.g. "Mar 1 - Apr 26, 2026") |

### Output (what the UI receives)

**Objection Cards List** — `GET /api/v1/objections/list`

| Key | Description | Example |
|---|---|---|
| `objection_id` | Unique objection identifier | OBJ001 |
| `objection_type` | Category of the objection | Side Effect Profile |
| `objection_text` | Exact objection phrase the doctor said | "I'm concerned about the side effect profile" |
| `period` | Date range when objection was recorded | Mar 1 - Apr 26, 2026 |
| `ai_frequency_label` | How often this objection comes up | HIGH / MEDIUM / LOW |
| `ai_call_count` | Number of calls this objection appeared in | 12 |
| `ai_date_range` | First and last date this objection was heard | Mar 15 - Apr 22 |
| `ai_conversion_score` | Success rate of the recommended response (0-100) | 67 |
| `ai_mlr_response` | The MLR-approved response text the rep should use | "I understand that's an important consideration..." |
| `ai_sku` | SKU code for supporting material | SP-2024-01 |
| `ai_supporting_materials` | **Updated:** now the real `ai_mlr_response` text combined with its `ai_sku`, straight from the database — no longer a generic hardcoded material name | "We have a patient-friendly dosing guide that can be co-branded with your practice... (SKU: ZNP-MLR-2024-052)" |
| `analysis_badges` | AI badges applied | DETECTED_BY_AI, NLP_ANALYSIS, AI_OPTIMIZED |

### API Endpoints

| Purpose | Method | Endpoint |
|---|---|---|
| All objection cards sorted by frequency | GET | `/api/v1/objections/list` |
| Full response detail for one objection | GET | `/api/v1/objections/{objection_id}/response` |
| Add objection to next call prep | POST | `/api/v1/objections/{objection_id}/add-to-call-prep` |

---

## Authentication

All endpoints require a JWT Bearer token in the request header:

```
Authorization: Bearer <your_token>
```

The `territory_id` is automatically extracted from the token — no need to pass it manually.

---

## Base URL

```
http://localhost:8000/api/v1
```

Interactive API documentation (Swagger):
```
http://localhost:8000/api/docs
```
