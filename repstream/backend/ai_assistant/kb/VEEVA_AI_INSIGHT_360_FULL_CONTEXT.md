# Veeva AI Insight 360 — Platform Context Document

**All 7 modules, consolidated.** Knowledge context, assistant instructions,
and data-quality register for every module across both applications on the
platform.

**Applications covered:**
- **My Insights — RepStream** (3 modules): Territory Prioritization, New
  Writer ID, Objection Handler
- **Action Center — Launch & Market Defense** (4 modules): Active Alerts,
  HCP Awareness, Competitive Intel, Payer Access

**Source documents:** this file is a structural merge of the seven
standalone module documents, each independently built from that module's
own screen captures and backend payloads. No content was rewritten in the
merge — headings were renumbered one level deeper (module sections are now
`##` instead of `#`) so all seven fit under one table of contents; wording,
findings, and figures are unchanged from the source documents.

---

## How to use this document

- **Part order follows the platform's own module numbering** (1–7), grouped
  by application. Each Part is a complete, standalone module document —
  jump directly to the Part for the tab a question concerns.
- **Every Part follows the same 10-section shape:** Module → Module Details
  → Frontend → Backend → Frontend↔Backend Mapping → Graphical Flow →
  Assistant Behaviour Rules → Data Quality Register → Open Items →
  Vocabulary. Section numbers are consistent across Parts (e.g. "§7" is
  always Assistant Behaviour Rules), so a rule referenced as "Part 4 §7.3"
  is unambiguous.
- **Cross-references between modules use plain Part names** (e.g. "route to
  Active Alerts §2.2") — every module document was written with the other
  six in mind, so sibling-routing tables throughout already point to the
  right Part.
- **Shared platform conventions are documented once per module, not once
  globally.** The application shell, the five KPI tiles, the yellow banner,
  brand-governance rules, and the data-precedence framework are identical
  across all four Action Center modules (Parts 4–7) and are each
  independently self-contained in every Part, by design — each Part can be
  lifted out and used standalone (e.g. as a single retrieval chunk) without
  losing its own operating rules. This produces some repetition across
  Parts 4–7 in particular; that repetition is intentional, not an error to
  clean up.
- **§8 in every Part (Data Quality Register) is an internal section.** Every
  Part repeats this instruction, and it is repeated here because it is the
  single most important operational rule in this document: if any part of
  this document is used as machine-readable context for an assistant, strip
  every Part's §8 before doing so. §8 exists for engineering, QA, and
  compliance review — it names concrete, sometimes wrong, values precisely
  so they can be found and fixed, and an assistant repeating those values as
  fact would reproduce the defect it documents. The master index directly
  below this note is drawn entirely from every Part's §8 and carries the
  same restriction.

---

## Master data-quality index — all 65 findings across 7 modules, by severity

**This index is part of §8-equivalent content across the whole document —
exclude it from machine-readable context for the same reason each Part's own
§8 is excluded (see above).** It exists so an engineering or compliance
reviewer can triage the full backlog without opening all seven Parts.

| Severity | Count |
|---|---|
| CRITICAL | 4 |
| HIGH | 19 |
| MEDIUM | 27 |
| LOW | 15 |
| **Total** | **65** |

### CRITICAL (4) — fix before any of these five modules ship or reship

| Part | § | Finding |
|---|---|---|
| 1 — Territory Prioritization | 8.1 | PDRP-restricted prescribers have Rx data exposed |
| 1 — Territory Prioritization | 8.2 | Generated content recommending off-label discussion |
| 2 — New Writer ID | 8.1 | Approach text recommending off-label discussion |
| 2 — New Writer ID | 8.2 | Approach text proposes an unrelated indication |

All four are regulatory/compliance-class defects (PDRP exposure, off-label
promotion) rather than data-accuracy bugs — see each Part's own §8 for full
evidence and remediation, and each Part's §8.13/8.10-equivalent Compliance
Register for the broader pattern each belongs to.

### HIGH (19)

| Part | § | Finding |
|---|---|---|
| 1 — Territory Prioritization | 8.3 | `low_priority_count` computed from a hard-coded base |
| 1 — Territory Prioritization | 8.4 | Narrative template contradicts its own row |
| 2 — New Writer ID | 8.3 | TARGET ICD-10 MATCH renders empty with a match badge |
| 2 — New Writer ID | 8.4 | Warm approach text is template mail-merge, labelled AI-GENERATED |
| 2 — New Writer ID | 8.5 | Same peer, two different institutions |
| 3 — Objection Handler | 8.1 | Duplicate records across two source object types |
| 3 — Objection Handler | 8.2 | The response body renders twice |
| 3 — Objection Handler | 8.3 | MLR-APPROVED and AI OPTIMIZED on the same panel |
| 4 — Active Alerts | 8.1 | KPI tiles do not reconcile with the alert list beneath them |
| 4 — Active Alerts | 8.2 | `recommended_actions` is repurposed on payer alerts and no longer drives the buttons |
| 4 — Active Alerts | 8.12 | An HCP-awareness alert's own description names cities outside its stated territory |
| 5 — HCP Awareness | 8.1 | The card panel titled "PRESCRIBING PATTERNS" never shows prescribing data |
| 5 — HCP Awareness | 8.3 | The "HCPs with declining awareness" heading does not filter to declining HCPs |
| 6 — Competitive Intel | 8.1 | `counter_strategy` is fully stable; `headline` and `executive_summary` are not, on the same records |
| 6 — Competitive Intel | 8.2 | Generated text sometimes drops, and sometimes preserves, the specific figures in the underlying signal |
| 6 — Competitive Intel | 8.3 | Three fields of generated content, plus explicit risk/urgency text, are computed but not rendered anywhere in the captured feed |
| 6 — Competitive Intel | 8.4 | A LOW-risk, ROUTINE-urgency signal is narrated with urgent language, in both the payload and the screen |
| 7 — Payer Access | 8.1 | "PA required" renders incorrectly for 4 of 5 stable/hybrid payer cards |
| 7 — Payer Access | 8.2 | Generated action-plan text names the wrong parent organisation for one payer |

### MEDIUM (27)

| Part | § | Finding |
|---|---|---|
| 1 — Territory Prioritization | 8.5 | Narrative addresses the wrong reader |
| 1 — Territory Prioritization | 8.6 | Internal contradictions within single narratives |
| 1 — Territory Prioritization | 8.7 | Competitor share values have no structured source |
| 1 — Territory Prioritization | 8.8 | Warm-introduction referrals ignore geography |
| 1 — Territory Prioritization | 8.9 | Documented contract does not match the implementation |
| 2 — New Writer ID | 8.6 | Candidate qualifies with zero in-class volume |
| 2 — New Writer ID | 8.7 | Three approach fields, two of them null |
| 2 — New Writer ID | 8.8 | Name field is comma-delimited |
| 2 — New Writer ID | 8.9 | Duplicate narrative fields |
| 3 — Objection Handler | 8.4 | Call counts are not territory-scoped |
| 3 — Objection Handler | 8.5 | Segmentation claimed but not delivered |
| 3 — Objection Handler | 8.6 | `ai_date_range` duplicates `period` |
| 3 — Objection Handler | 8.7 | Section header range understates the window |
| 4 — Active Alerts | 8.3 | Payer alert `resources` are identical across every payer alert |
| 4 — Active Alerts | 8.4 | The "HCP drift detected" tile has no structured field behind it |
| 4 — Active Alerts | 8.5 | Generated title/description/counter-script text is not stable, except for payer alerts |
| 4 — Active Alerts | 8.6 | `alert_id` is never surfaced in the UI |
| 4 — Active Alerts | 8.7 | `ai_rx_risk` casing is inconsistent between streams |
| 5 — HCP Awareness | 8.2 | The "How it works" copy describes capabilities this tab's data does not contain |
| 5 — HCP Awareness | 8.5 | One record's card styling and its own narrative disagree with its structured trend field |
| 5 — HCP Awareness | 8.6 | Generated activity-narrative text is not stable across captures, for most but not all records |
| 6 — Competitive Intel | 8.5 | The "Real-time monitoring" panel claims capabilities this module's data does not support |
| 6 — Competitive Intel | 8.6 | Sort order is not strictly date-descending within a risk tier |
| 6 — Competitive Intel | 8.7 | `analysis_badges` is documented but absent; `signal_type` appears to absorb its role |
| 7 — Payer Access | 8.3 | Generated action-plan text references a payer channel inconsistent with the record's own `channel_name` |
| 7 — Payer Access | 8.4 | `ai_action_plan` and `view_action_plan` diverge for alert-tier payers, but are identical for stable payers |
| 7 — Payer Access | 8.5 | The one STABLE+changed record's top badge shows `change_badge`, not its own `status_badge` |

### LOW (15)

| Part | § | Finding |
|---|---|---|
| 1 — Territory Prioritization | 8.10 | Score quantisation |
| 1 — Territory Prioritization | 8.11 | Records that should probably be filtered out |
| 1 — Territory Prioritization | 8.15 | Field naming defects in the published schema |
| 2 — New Writer ID | 8.10 | Missing values render with their label |
| 2 — New Writer ID | 8.11 | Field naming defects in the KPI block |
| 2 — New Writer ID | 8.12 | Empty strings where null is meant |
| 3 — Objection Handler | 8.8 | Field naming inconsistency in the KPI block |
| 3 — Objection Handler | 8.9 | Date ranges lack a year |
| 4 — Active Alerts | 8.8 | KPI tile treatment is inconsistent within the same row |
| 4 — Active Alerts | 8.10 | Null SKU is rendered to the user as the literal word "null" |
| 5 — HCP Awareness | 8.4 | "Schedule Call" is offered unconditionally, including for improving HCPs |
| 5 — HCP Awareness | 8.7 | Only the Declining segment of the list is internally ordered by severity |
| 6 — Competitive Intel | 8.8 | Inconsistent trailing punctuation in generated headlines, present in the payload itself |
| 7 — Payer Access | 8.6 | "Impact: Medium –" renders with a trailing separator and no value |
| 7 — Payer Access | 8.7 | `analysis_badges` undercounts the techniques actually applied to a record |

### Two patterns that recur across most or all of the seven modules

Reading the 65 findings together surfaces two systemic issues that no
single Part's own register calls out as cross-module, because each Part was
built independently from its own captures:

1. **Generated free-text fields (headlines, summaries, counter-scripts,
   narratives, action plans) are frequently regenerated on each read and are
   not stable between two views of what should be the same record.** This is
   documented independently in Part 1 §8.12 (resolved in that specific case),
   Part 4 §8.5, Part 5 §8.6, Part 6 §8.1/§8.2, and Part 7 §8.4. Where it has
   been checked closely enough to compare (Part 6), one field
   (`counter_strategy`) was completely stable while two others were not on
   every record — suggesting some generated fields are cached and others are
   not, inconsistently, within the same payload. Any assistant answering
   from this platform should never treat quoted generated text as a fixed
   identifier for a record across turns — see the "Data precedence" section
   in every Part's §7.1.
2. **Generated free-text content is not reliably grounded in its own
   record's structured fields** — it has been observed naming the wrong
   payer entity (Part 7 §8.2), the wrong patient population/channel (Part 7
   §8.3), a geography outside the alert's own stated territory (Part 4
   §8.12), and an urgency tone contradicting the record's own risk/urgency
   classification (Part 6 §8.4). This is the same underlying failure mode
   recurring across four different modules and four different kinds of
   entity (payer, channel, place, tone) — worth treating as one systemic
   generation-quality issue for prioritisation purposes, not four unrelated
   bugs.

---

## Master Part index

| Part | Module | Application | Platform module # |
|---|---|---|---|
| 1 | Territory Prioritization | My Insights — RepStream | 1 of 7 |
| 2 | New Writer ID | My Insights — RepStream | 2 of 7 |
| 3 | Objection Handler | My Insights — RepStream | 3 of 7 |
| 4 | Active Alerts | Action Center — Launch & Market Defense | 4 of 7 |
| 5 | HCP Awareness | Action Center — Launch & Market Defense | 5 of 7 |
| 6 | Competitive Intel | Action Center — Launch & Market Defense | 6 of 7 |
| 7 | Payer Access | Action Center — Launch & Market Defense | 7 of 7 |

---

# PART 1 — TERRITORY PRIORITIZATION

**Application:** My Insights — RepStream · **Platform module:** Module 1 of 7

## 1. MODULE

| | |
|---|---|
| **Module name** | Territory Prioritization |
| **Parent application** | My Insights — RepStream |
| **Parent platform** | Veeva AI Insight 360 (UI shows "Insights 360™ V2") |
| **Position** | Tab 1 of 3 in RepStream; Module 1 of 7 on the platform |
| **Primary user** | Field sales representative |
| **Secondary user** | Sales manager (consolidated multi-territory view) |
| **Therapy context** | Pancreatic enzyme replacement therapy (PERT / EPI) |
| **Access model** | Role-based, derived from the authenticated session |
| **Write capability** | None. Read-only, not a system of record |
| **Refresh cadence** | Batch recalculation; surfaced as `last_refresh` |

**The question this module answers:** *where should my time go this week?*

It reviews every HCP assigned to a territory and ranks them by current
commercial opportunity and risk — prescribing trend, engagement recency,
relative opportunity — rather than presenting a flat unordered list. Each
ranked HCP carries a generated explanation of why they appear where they do,
with the supporting figures alongside, so the ranking can be understood and
challenged rather than accepted blindly.

**The platform informs the decision; the representative makes it.** Generated
content is decision support for review by a qualified user — never an
autonomous decision, never a clinical recommendation.

---

## 2. MODULE DETAILS

### 2.1 Position in the platform

```
Veeva AI Insight 360 — 7 modules
│
├── My Insights (RepStream)
│   ├── Territory Prioritization   ← THIS MODULE
│   ├── New Writer ID
│   └── Objection Handler
│
└── Action Center — launch and market defence
    ├── Active Alerts            threat feed, three streams
    ├── HCP Awareness            per-HCP awareness scores and trend
    ├── Competitive Intel        competitor signals and counter-strategy
    └── Payer Access             formulary tiers and access risk
```

Value chain the platform implements:

```
Data → Intelligence → Insight → Recommendation → Action
```

This module contributes the **Insight** and **Recommendation** stages for HCP
prioritization specifically.

### 2.2 Sibling modules — routing reference

| Destination | Location | Holds | Route when user asks |
|---|---|---|---|
| **New Writer ID** | tab | HCPs prescribing in-class but not this product; peer-match score, warm-introduction path, drafted outreach email, matched ICD-10 codes | who should I start, non-writers, warm intro, draft an email, conversion targets |
| **Objection Handler** | tab | Objections identified in call transcripts, ranked by frequency, each with an MLR-approved response and SKU reference | what do I say when, they told me, pushback, objection |
| **Active Alerts** | Action Center | Machine-detected threats in three streams — competitive script shifts, payer formulary changes, HCP awareness decline — each with severity, counter-script and recommended actions | alerts, what changed, what needs my attention, counter script, deploy to field, affected HCPs |
| **HCP Awareness** | Action Center | Per-HCP awareness score tracked across four weekly periods, with trend direction, risk score and a recommended re-engagement action | awareness, is this HCP going cold, declining engagement, awareness trend, who needs a call |
| **Competitive Intel** | Action Center | Competitor signals — rep-visit surges, share gains, messaging campaigns — scored by threat level with executive summary, business impact and talking points | competitor activity, what is the competition doing, threat level, talking points, counter strategy |
| **Payer Access** | Action Center | Formulary tier status per payer, with tier-change detection, abandonment risk, covered lives and a prior-authorisation bridge note | formulary, tier change, payer, prior auth, PA, coverage, covered lives, abandonment |

### 2.3 How the ranking is produced

Four techniques combine to produce the tier and score:

| Technique | Contribution |
|---|---|
| Composite scoring | Combines weighted signals into a single score |
| Linear regression | Establishes prescribing trend direction |
| NLP classification | Categorises engagement |
| Generative narrative | Writes the visit-preparation insight |

**Inputs:** HCP list, twelve months of prescribing history, call activity,
decile rank.

**Scores tie heavily.** Many HCPs share an identical score, so a score-ordered
list contains large blocks at the same value and ordering within a block is
arbitrary. Never describe one HCP as ranked above another when their scores are
equal, and never infer rank position from list position alone.

**Tier is a band, not a rank.** Two HCPs in the same tier are not ordered
relative to each other by the tier.

### 2.4 Access scope

Visibility follows the organisational hierarchy. Users see only what their
authenticated identity and organisational position permit.

```
Manager  →  User (representative)  →  Territory  →  HCP
```

| Level | What the user sees |
|---|---|
| Manager | Consolidated view across their teams and territories, able to focus on any one |
| User | The territories assigned to that representative |
| Territory | All insights relating to a selected territory |
| HCP | The detailed position for one professional |

**Territory scope derives from the authenticated session, not free choice.**
Every figure on the page corresponds to the filter currently in force. When the
filter changes, the values change with it — a figure is only ever true of the
selection on screen.

### 2.5 Three classifications that are routinely confused

| Field | Source | Values | Nature |
|---|---|---|---|
| **Segment** | CRM, set by commercial ops | High, Medium, Low, Non-Target, CF HCP | Planning classification |
| **AI Priority** | Ranking model | HIGH, MEDIUM, LOW | Current opportunity band |
| **Target** | Call plan | Y / N flag | On the official plan or not |

Segment and AI Priority diverge routinely **and by design** — a High-segment
HCP can rank MEDIUM priority, and a Non-Target HCP can rank HIGH. Neither is an
error: the model measures current opportunity, the CRM records a planning
classification.

---

## 3. FRONTEND — OVERVIEW AND KEYS

### 3.1 Application shell

```
┌────────────────────────────────────────────────────────────────────────────┐
│ ☰   ▮▮ Insights 360™  [V2]   ⚡SLIPSTREAM              ⊞  </>              │
├──────────────────┬─────────────────────────────────────────────────────────┤
│ ▫ Insights 360 V1│  My Insights - RepStream  [POWERED BY DATAstream AI]     │
│ ▪ My Insights    │  AI-powered intelligence for your territory              │
│ ▫ Action Center  │                                                          │
│                  │  [Territory Prioritization] [New Writer ID] [Objection…] │
│ ⏻ Logout         │                                                          │
└──────────────────┴─────────────────────────────────────────────────────────┘
```

| Element | Detail |
|---|---|
| Platform mark | Insights 360™ with a **V2** version badge |
| Partner mark | SLIPSTREAM |
| Attribution badge | POWERED BY DATAstream AI |
| Tagline | AI-powered intelligence for your territory |
| Left nav | Insights 360 V1, My Insights (active), Action Center, Logout |
| Top-right icons | App/grid launcher, code/developer view toggle |
| Hamburger | Collapses left navigation |
| Assistant launcher | Circular chat button, fixed bottom-right of the viewport. Opens the in-product assistant governed by §7 |

### 3.2 Filter bar

| Control | Behaviour | Default |
|---|---|---|
| **USERS** | Dropdown of representatives the viewer may see | All |
| **TERRITORY NAME** | Dropdown of territories in scope | All |
| **Apply** | Triggers refetch. Selecting a filter changes nothing until pressed | — |

### 3.3 Data reference panel (upper right, display only)

| Line | Source |
|---|---|
| `Q3 2026 (Jul - Sep)` | `period` |
| `Last updated: Aug 18, 2026` | `last_refresh` |

### 3.4 KPI summary cards — five, left to right

| # | Card label | Badge | Displays |
|---|---|---|---|
| 1 | Total HCPs | — | Integer |
| 2 | High Priority | AI RANKED | Integer |
| 3 | Medium Priority | AI RANKED | Integer |
| 4 | Last Refresh | — | `Mon DD, YYYY` |
| 5 | This Week Target | — | Integer |

**AI RANKED badge** appears on High and Medium only. It marks the tier as model
output rather than a CRM segment.

**There is no Low Priority card.** `low_priority_count` exists in the payload
but is never rendered — see §7.3.

### 3.5 Ranked HCP list

Heading: **"DATAstream AI-ranked HCP priority list"**
Attribution (right): **"Powered by DATAstream™ Rx + DATAstream AI"**
Order: priority tier HIGH → MEDIUM → LOW, then by score within tier.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ ┃ (XY)  <hcp name>                                      [View Profile]   │
│ ┃       <specialty>                                                      │
│ ┃       [HIGH PRIORITY]                          Score: <nn.nn%>         │
│ ┃  ┌────────────────────────────────────────────────────────┐            │
│ ┃  │  <generated narrative paragraph>           [AI INSIGHT] │            │
│ ┃  └────────────────────────────────────────────────────────┘            │
│ ┃  LAST RX      RX Q1     RX Q4     SEGMENT      LAST CALL               │
│ ┃  <date>       <count>   <count>   <label>      <n> days ago            │
└──────────────────────────────────────────────────────────────────────────┘
  ↑ coloured left stripe + avatar, keyed to tier
```

#### Card elements

| Element | Position | Notes |
|---|---|---|
| Avatar | Left, circular, initials | Colour keyed to tier |
| Left stripe | Card border | Colour keyed to tier |
| Name | Header, bold link style | Trailing whitespace stripped |
| Specialty | Under name, muted | |
| Priority chip | Under specialty | Style varies by tier |
| Score | Right, under View Profile | Percentage, bold |
| View Profile | Top right, outlined button | Opens detail record |
| AI INSIGHT panel | Tinted box, badge top-right | Generated prose |
| Metric row | Card footer, 5 columns | LAST RX, RX Q1, RX Q4, SEGMENT, LAST CALL |

#### Tier visual coding

| Tier | Avatar | Stripe | Chip |
|---|---|---|---|
| HIGH PRIORITY | Orange | Orange | Filled orange |
| MEDIUM PRIORITY | Blue | Blue | Outlined blue |
| LOW PRIORITY | Green | Green | Plain text, no fill |

---

## 4. BACKEND — KEY DETAILS

### 4.1 Data delivery

**KPI counts and the ranked HCP list arrive as two separate responses** when
the tab loads. The KPI response also carries counts for the sibling tabs — see
§4.2.1.

**Registry detail behind View Profile is fetched per HCP**, on click. It is not
present in the list response.

**Territory scope is derived from the authenticated session**, not chosen
freely. Every figure corresponds to the filter currently in force; when the
filter changes, the values change with it.

### 4.2 Summary payload — field inventory

| Field | Type | Rendered | Notes |
|---|---|---|---|
| `total_hcps` | integer | Yes | HCPs in current filter scope |
| `high_priority_count` | integer | Yes | Reconciles with list |
| `medium_priority_count` | integer | Yes | Reconciles with list |
| `low_priority_count` | integer | **No** | Unreliable — §7.3 |
| `weekly_target` | integer | Yes | Recommended visits |
| `period` | string | Yes | e.g. `"Q3 2026 (Jul - Sep)"` |
| `last_refresh` | string | Yes | `Mon DD, YYYY` |
| `territory_id` | string | No | Delimiter-joined composite |
| `territory_name` | string | No | **Identical to `territory_id`** — no names |
| `filters` | object | Yes | Drives both dropdowns |
| `new_writer_id` | object | No¹ | Cross-module KPI block — §4.2.1 |
| `objection_handler` | object | No¹ | Cross-module KPI block — §4.2.1 |

¹ Not rendered on the Territory Prioritization tab. The KPI response serves
all three RepStream tabs from one call; these blocks feed the sibling tabs.

#### 4.2.1 Cross-module KPI blocks

The KPI response carries headline counts for the other two tabs so the
application can populate them without a second round trip.

```
new_writer_id
    Non_writers_in_Territory   integer
    Prescribing_in_class       integer
    Diagnosis_match            integer
    Warm_condidates            integer    ← spelling exactly as returned

objection_handler
    calls_analysed             integer
    objections_detected        integer
    recurring_patterns         integer
    High_frequency             integer
```

**Do not answer from these on this tab.** They belong to New Writer ID and
Objection Handler respectively. Route the user to the owning tab (§2.2) rather
than reading the count aloud — the tab holds the detail the count summarises.

### 4.3 Filter hierarchy — three levels

```
filters.manager_id[]
    ├── manager_id / manager_name
    └── employee_id[]                    ← USERS dropdown
            ├── employee_id / employee_name
            └── territory_id[]           ← TERRITORY NAME dropdown
                    └── territory_id / territory_name
```

Built live from sales-force org data; updates automatically as managers,
employees, or territories change. Every node carries a paired identifier and
label — `*_id` is what the UI sends back, `*_name` is what it displays.

**Two behaviours to know.**

1. **Top-level territory fields are unusable for display.** `territory_id` and
   `territory_name` are byte-identical delimiter-joined strings of the form
   `Prefix|ID,Prefix|ID`. The `_name` field contains no names. Real display
   names exist only inside the hierarchy above.
2. **`filters.manager_id` can arrive empty.** When it does, no representative
   or territory names exist anywhere in the payload and both dropdowns have
   nothing to populate. In that state do not name a territory or a rep.

### 4.4 HCP list payload — field inventory

| Field | Type | On card | Notes |
|---|---|---|---|
| `hcp_id` | string | No | Join key |
| `name` | string | Yes | Trailing whitespace present in source |
| `specialty` | string | Yes | |
| `segment` | string | Yes | CRM classification |
| `view_profile` | object | On click | 14 nested keys — §4.5 |
| `rx_q1` | integer | Yes | Current-quarter volume |
| `rx_q4` | integer | Yes | Prior-quarter volume |
| `last_rx_date` | string | Yes | `Mon DD, YYYY` |
| `last_call_date` | string | Yes | Rendered as elapsed days |
| `ai_priority_tier` | string | Yes | HIGH / MEDIUM / LOW |
| `ai_score` | string | Yes | Percentage string, e.g. `"nn.nn%"` |
| `ai_score_reason` | string | **No** | Names the ranking drivers — best source for "why". May be an empty string |
| `ai_generated_insight` | string | Yes | Generated prose — not a source of fact |

**`ai_score_reason` is the most useful field for "why is this HCP here".** It
is in the payload but not on the card, and names the drivers directly: Rx
growth, decile rank, engagement recency. Prefer it over the narrative.

### 4.5 `view_profile` object — 14 keys

| Key | Purpose |
|---|---|
| `formatted_name` | Duplicate of `name` |
| `specialist_description` | Duplicate of `specialty` |
| `email` | Contact address |
| `website` | Provider directory URL |
| `npi` | National Provider Identifier |
| `medical_degree` | MD, DO, NP, PA, APRN |
| `address` / `city` / `state` | Practice location |
| `hcp_status` | Active / Inactive |
| `hcp_type` | Prescriber / Non-Prescribing Health Care Professional |
| `target` | Y / N — on the official call plan |
| `pdrp_output` | Y / N — AMA Prescriber Data Restriction Program |
| `is_ama_do_not_contact` | Y / N — contact restriction |

**Four of these gate what may be said about the HCP.**

| Field | Constrains |
|---|---|
| `pdrp_output = "Y"` | Prescriber opted out of Rx data disclosure to sales. **Never report their Rx figures.** |
| `hcp_type` non-prescribing | Do not report prescription counts even if values present |
| `hcp_status = Inactive` | Record may not belong in an active call plan |
| `is_ama_do_not_contact` | Contact restriction |

---

## 5. FRONTEND ↔ BACKEND MAPPING

### 5.1 KPI cards

| UI card | Payload field | Source | Transform |
|---|---|---|---|
| Total HCPs | `total_hcps` | KPI response | Direct |
| High Priority | `high_priority_count` | KPI response | Direct |
| Medium Priority | `medium_priority_count` | KPI response | Direct |
| Last Refresh | `last_refresh` | KPI response | Direct |
| This Week Target | `weekly_target` | KPI response | Direct |
| *(no card)* | `low_priority_count` | KPI response | **Not rendered** |

### 5.2 Header and filter bar

| UI element | Payload path | Transform |
|---|---|---|
| DATA REFERENCE line 1 | `period` | Direct |
| DATA REFERENCE line 2 | `last_refresh` | Prefixed "Last updated: " |
| USERS dropdown | `filters.manager_id[].employee_id[].employee_name` | Flattened to option list |
| USERS value sent | `…employee_id` | |
| TERRITORY dropdown | `filters.…territory_id[].territory_name` | Flattened to option list |
| TERRITORY value sent | `…territory_id` | |
| *(not used)* | top-level `territory_name` | **Not a display name** |

### 5.3 HCP card

| UI element | Payload field | Transform |
|---|---|---|
| Avatar initials | `name` | First letter of first two words |
| Avatar / stripe colour | `ai_priority_tier` | HIGH→orange, MEDIUM→blue, LOW→green |
| Name | `name` | `.strip()` |
| Specialty | `specialty` | Direct |
| Priority chip text | `ai_priority_tier` | + " PRIORITY" |
| Score | `ai_score` | Direct, already a percentage string |
| AI INSIGHT body | `ai_generated_insight` | Direct |
| LAST RX | `last_rx_date` | Direct |
| RX Q1 | `rx_q1` | Direct |
| RX Q4 | `rx_q4` | Direct |
| SEGMENT | `segment` | Direct |
| LAST CALL | `last_call_date` | **Converted to "N days ago"** |
| View Profile button | `view_profile` | Opens detail |
| *(not rendered)* | `ai_score_reason` | Available but unused on card |
| *(not rendered)* | `hcp_id` | Internal |

### 5.4 Mapping notes and traps

**`ai_score` needs no division.** It arrives pre-formatted as a percentage string. Do not treat it as a 0–1 float or a 0–100 number.

**`last_call_date` is the only computed display field.** The payload carries an
absolute date; the card shows elapsed days. These have been observed to
disagree — quote the payload date, not the elapsed figure.

**Two fields are duplicates.** `view_profile.formatted_name` equals `name` and
`view_profile.specialist_description` equals `specialty` in every record.

**Documented fields that do not exist in the payload.** The module guide
describes six fields the API does not return: `affiliated_hospital`,
`ai_rx_trend_direction`, `ai_predicted_next_q_rx`, `ai_engagement_category`,
`ai_engagement_urgency`, `analysis_badges`. Never build against a documented
field name — build against the payload.

**The KPI response is multi-tab.** It carries `new_writer_id` and
`objection_handler` blocks that this tab does not render. Do not map them
to anything here; do not answer from them. Route to the owning tab.

**Score field name and type differ from the documented contract.**

```
documented:  ai_priority_score   numeric 0-100        e.g. <nn.n>
actual:      ai_score            percentage string    e.g. "<nn.nn>%"
```

Build against the payload, never against the documented field name.

---

## 6. GRAPHICAL FLOW

### 6.1 Page lifecycle

```
   Rep opens Territory Prioritization
                │
                ▼
   Territory scope resolved from the authenticated session
                │
       ┌────────┴────────┐
       ▼                 ▼
  KPI response      Ranked HCP list
       │                 │
       ▼                 ▼
  ┌─────────────┐   ┌──────────────────────────┐
  │ 5 KPI cards │   │ HCP card list            │
  │ + data ref  │   │ sorted tier, then score  │
  │ + filters   │   │                          │
  └─────────────┘   └──────────────────────────┘
                            │
                            ▼
                  [View Profile] clicked
                            │
                            ▼
                  registry detail fetched per HCP
       │
       ▼
   Rep changes USERS or TERRITORY NAME
                │
                ▼
   Presses Apply ──► both responses refetch with the new scope
                     (nothing changes until Apply is pressed)
```

### 6.2 Data pipeline behind the ranking

```
   SOURCE
   ├── HCP master list
   ├── 12 months prescribing history
   ├── Call activity log
   └── Decile rank
                │
                ▼
   ┌────────────────────────────────────────────┐
   │  PROCESSING                                │
   │                                            │
   │  Composite scoring    → ai_score           │
   │  Linear regression    → trend direction    │
   │  NLP classification   → engagement band    │
   │  Generative narrative → ai_generated_insight│
   │                       → ai_score_reason    │
   └────────────────────────────────────────────┘
                │
                ▼
   Banding: score → ai_priority_tier (HIGH / MEDIUM / LOW)
                │
                ├──────────► aggregate → summary counts → KPI cards
                └──────────► per-HCP    → hcp-list      → ranked cards
```

### 6.3 Filter resolution

```
   filters.manager_id[]
        │
        ├── manager_name ────────────► (not displayed as a control)
        │
        └── employee_id[]
                ├── employee_name ───► USERS dropdown label
                ├── employee_id ─────► USERS dropdown value
                │
                └── territory_id[]
                        ├── territory_name ──► TERRITORY dropdown label
                        └── territory_id ────► TERRITORY dropdown value

   Top-level territory_id / territory_name  ──► NOT USED for display
                                                (delimiter-joined composite)
```

### 6.4 Ambiguity resolution — "show me my high priority HCPs"

```
              "high"
                │
        ┌───────┴────────┐
        ▼                ▼
   segment field   ai_priority_tier
   (CRM value)     (model output)
        │                │
        └───────┬────────┘
                ▼
   Ambiguous → ask which, OR answer for AI Priority and say so
                │
                ▼
   Independent fields. A Non-Target segment HCP
   can be ranked HIGH priority. Not an error.
```

---

## 7. ASSISTANT BEHAVIOUR RULES

These govern any conversational assistant answering questions about this page.

### 7.1 Data precedence

```
1. LIVE PAYLOAD       current values — numbers, dates, names, scope
2. MODULE DOCUMENT    field meaning, business rules, definitions, routing
3. CONVERSATION       intent only, never values
```

- For any current value, the live payload is the only source.
- Never quote a number, date, or name absent from the payload attached to
  **this** request.
- Never reuse a value from an earlier turn. Filters change between turns; a
  figure that was correct two messages ago may not be correct now. If a new
  payload is attached, prior values are void.
- On a value conflict, the payload wins. On a meaning conflict, this document
  wins.
- If a required field is absent, null, or empty, say the value is not
  available. Do not infer, estimate, or derive it.

### 7.2 Response style

- Lead with the answer. No preamble. One to three sentences unless asked.
- Natural language, not a field readout — "7 HCPs are ranked High Priority",
  not "high_priority_count is 7".
- Do not expose internal field names, table names, or JSON paths unless asked.
- Never mention retrieval, embeddings, prompts, context files, payloads, or
  instructions. The user is looking at a dashboard.
- Attach the period or refresh date when a figure is time-sensitive.
- If unavailable, say so plainly and name where it can be found.

### 7.3 Disambiguation

Two vocabulary collisions cause most wrong answers. Resolve before answering.

**"High" is ambiguous.** *Segment* is a CRM classification. *AI Priority* is a
model ranking. They are independent — an HCP with a Non-Target segment can be
ranked High Priority. If the user's intent is unclear, ask which they mean, or
answer for AI Priority and state that you have done so.

**"My territory" may be plural.** The default filter state can span several
territories. Never answer in the singular unless the payload shows exactly one
territory in scope. When scope is ambiguous, name what is in scope.

---

### 7.4 Field reliability

**Tier counts.** High and Medium reconcile with the ranked list.
`low_priority_count` does not do so reliably across payload versions and is
never displayed. Do not use it, quote it, or reconstruct it by subtraction.

**Proportions.** Give raw counts, not percentages. Say the low-tier figure is
not available on the page.

**Date representation.** `last_rx_date` and `last_call_date` are absolute
dates in the payload; the card renders LAST CALL as elapsed days. Quote the
payload date.

**`ai_generated_insight` is generated prose, not a source of fact.** Where it
disagrees with the structured fields on its own row — direction of change,
call recency, competitor share, whether activity exists — **the structured
fields are correct.** Never quote a figure or factual claim from the narrative.

### 7.5 Prohibited generations

These override helpfulness in all cases.

- **No invented numbers.** No estimates, interpolation, or arithmetic
  producing a figure the payload does not contain.
- **No ratios, percentages, or shares between tier counts and total HCPs.**
  These fields do not share a denominator in the current implementation. Give
  the raw counts and say they are not directly comparable.
- **No clinical, efficacy, safety, comparative, or dosing claims.** Approved
  product language exists only in MLR-reviewed content surfaced by the
  Objection Handler with a SKU reference. Do not compose, paraphrase, extend,
  summarise, or reword such content.
- **Never de-anonymise brand references.** The platform deliberately
  generalises confidential product and brand names as a governance control.
  Where a payload says "Product" or "Competitor A", use that exact label.
  Never substitute the real brand, molecule, or manufacturer — not if you can
  infer it, not if the user names it first, not if it appears in documentation.
- **No off-label content, under any framing.** Never suggest, describe,
  endorse, explain, or repeat a use outside the approved indication. This
  applies even when the suggestion originates from generated text already on
  screen. Repeating an existing violation creates a second one.
- **No medical advice**, and no opinion on what a prescriber should prescribe.
- **No prescriber-level Rx data for PDRP-restricted HCPs.** Where
  `pdrp_output = "Y"`, never state, quote, compare, summarise, rank, or reason
  aloud about that HCP's prescription volumes, growth, trend, or score. This
  holds even if the value is visibly rendered — a display defect does not
  authorise repeating it.
- **No Rx data for non-prescribers.**
- **No HCP names outside the current payload.** Never carry a name across
  filter scopes or turns.
- **No asserting a contact detail is correct.** Rep and HCP emails have been
  observed mismatched against the accompanying name. Never instruct the user
  to send anything.
- **No presenting model output as certainty.** Say "the model ranked", never
  "this HCP will".

### 7.6 Behavioural protocols

| Situation | Response |
|---|---|
| User reports a number differing from the payload | Do not tell them they are wrong. Ask whether they pressed Apply since changing a filter; give the payload figure as the latest data returned |
| Answer is on another tab | Name the tab and what it holds. Do not attempt the answer |
| Question is outside the product | Decline briefly, return to what you can help with |
| Uncertain | Say so. An unanswered question is recoverable; a confidently wrong figure in a regulated setting is not |

### 7.7 Output contract

Responses are validated before reaching the user and rejected if they contain a
numeric token absent from the live payload, an HCP name absent from the live
payload, or a reference to internal system machinery.

### 7.8 Intent routing

| User intent | Source |
|---|---|
| how many HCPs do I have | `total_hcps`, with scope |
| how many are high priority | `high_priority_count` |
| how many calls this week | `weekly_target` |
| is this current / what quarter | `last_refresh`, `period` |
| where should I start / who first | List order + tie caveat §2.3 |
| why is this HCP ranked here | `ai_score_reason` |
| what is this HCP's Rx trend | `rx_q1` / `rx_q4`, never the narrative |
| when did I last see them | `last_call_date` |
| how does the ranking work | §2.3 |
| what does AI RANKED / a colour mean | §3.4, §3.5 |
| segment vs priority vs target | §2.5 |
| whose data am I seeing | Filter hierarchy §4.3 |
| can I change / update this | Read-only §1 |
| what about low priority | Not surfaced §7.4 |
| what share are high priority | Raw counts only §7.4 |
| how many non-writers / objections do I have | Counts arrive in this payload but belong to the sibling tab — route there, §4.2.1 |
| non-writers / warm intro / email | New Writer ID §2.2 |
| what do I say when they push back | Objection Handler §2.2 |
| alerts / what changed | Active Alerts — Action Center §2.2 |
| is this HCP going cold | HCP Awareness — Action Center §2.2 |
| what is the competitor doing | Competitive Intel — Action Center §2.2 |
| formulary / tier / prior auth | Payer Access — Action Center §2.2 |

### 7.9 What this module can and cannot answer

**Available:** any KPI value and its meaning; period and refresh date; for any
listed HCP — name, specialty, tier, score, both quarterly Rx figures, segment,
last Rx date, last call date, score reason (subject to §4.5 gating); reps and
territories in scope when the hierarchy is populated; what any control, badge,
chip, or colour means; how the ranking is produced.

**Not available:** registry detail behind View Profile until opened; content
belonging to sibling modules — including the `new_writer_id` and
`objection_handler` counts that arrive in this tab's own summary payload; trend beyond the two quarters on the row;
predicted future prescribing; any low-tier figure; rankings between HCPs with
identical scores; anything requiring a record change — the platform is
read-only.

---

## 8. DATA QUALITY REGISTER

> **Internal section.** Contains named records and concrete figures. The
> constraints these defects impose are stated qualitatively in §7.4 and §7.5.
> If any part of this document is used as machine-readable context, exclude
> sections 8 and 9 — they contain exactly the values §7.5 forbids repeating.

Ordered by severity. Items 1 and 2 block release.

### 8.1 CRITICAL — PDRP-restricted prescribers have Rx data exposed

Two records carry `view_profile.pdrp_output = "Y"` and also carry populated
`rx_q1` / `rx_q4`, which the card renders.

```
Nadeem Ansari    pdrp_output = Y    rx_q1 = 300    rx_q4 = 200
Jemini Ignacio   pdrp_output = Y    rx_q1 = 100    rx_q4 = 100
```

PDRP is the AMA Prescriber Data Restriction Program. An enrolled prescriber has
opted out of having prescribing data disclosed to pharmaceutical sales
representatives. Rendering their Rx volumes to a rep is the precise disclosure
the programme exists to prevent. Both records also receive an `ai_score`, an
`ai_priority_tier`, and a narrative restating the counts in prose — so the
restricted figure appears three times per row.

**Actions**
- Suppress `rx_q1`, `rx_q4`, `last_rx_date`, `ai_score` and the narrative for
  any record where `pdrp_output = "Y"` — at the API layer, not the frontend.
- Audit whether PDRP is honoured anywhere in the pipeline today.
- Raise with compliance before the next release. This is not a display bug.

### 8.2 CRITICAL — generated content recommending off-label discussion

A New Writer ID narrative recommends discussing "potential off-label uses"
during an HCP visit. Promotion of unapproved uses is a regulatory violation
regardless of intent, and this reached a rendered screen.

**Actions**
- Add an off-label term filter to the generation post-check that blocks the
  output rather than flagging it.
- Review the generation prompt for anything inviting discussion of uses outside
  the approved indication.
- Report the instance through the MLR process.

### 8.3 HIGH — `low_priority_count` computed from a hard-coded base

```
                      KPI payload      actual list
total_hcps                    68               68   match
high_priority_count            7                7   match
medium_priority_count         11               11   match
low_priority_count           982               50   MISMATCH
```

`1000 - 7 - 11 = 982`. The low tier is derived as `1000 - high - medium` rather
than counted. An earlier capture fits the same formula: `1000 - 0 - 0 = 1000`
against `total_hcps` of 50.

**High and medium reconcile exactly.** Only the low tier is wrong.

**This contradicts the module spec.** The guide gives a worked example of 127
total against 34 high, 58 medium, 35 low — which sums to 127. Tiers are
specified to partition the territory.

**A second code path already behaves correctly.** A later single-territory
payload returns `2 + 9 + 4 = 15` against `total_hcps` 15, which reconciles and
does not fit the 1000-base formula. Two implementations coexist.

**Actions**
- Replace the constant with `total_hcps - high - medium`, or count directly.
- Identify which service produces which payload shape and consolidate.
- Add a pipeline assertion `high + medium + low = total_hcps` failing the build.
- Consider surfacing a Low Priority card so the defect is visible.

### 8.4 HIGH — narrative template contradicts its own row

The fallback string:

> "Stable prescriber with consistent Rx activity this quarter (X Rx, prior
> quarter Y). No significant competitor pressure detected… No recent call
> activity on file. Consider a routine maintenance call this month."

fires on at least 12 records where it is wrong in two ways.

**"No recent call activity on file"** while `last_call_date` is within the
preceding two weeks:

```
Jurate Kunickaite  Aug 08    Sijun Yang     Aug 07    Tommy Pacana   Aug 04
Renee Middleton    Aug 06    Reda Kilani    Aug 05    Nadeem Ansari  Aug 07
Alexa Choy         Aug 06    Liji Mathew    Aug 03    Kaleem Khan    Aug 06
Darren Kastin      Aug 08    Ryan Tremb     Aug 08    Rachna Arora   Aug 08
```

A rep who visited an HCP last week is told there is no call on file. This
destroys trust in the panel faster than any other defect here.

**"Stable / consistent"** applied to substantial growth:

```
Jurate Kunickaite   900 vs 200  = +350%   described as consistent
Renee Middleton    1000 vs 400  = +150%   described as consistent
Darren Kastin       500 vs 200  = +150%   described as consistent
Kaleem Khan         300 vs 200  =  +50%   described as consistent
```

**Actions**
- Gate the fallback on the fields it asserts — emit the no-call clause only
  when `last_call_date` is genuinely absent or beyond threshold.
- Emit "stable" only below a defined growth band.
- Treat any narrative contradicting its own row as a generation failure and
  fall back to a structural summary.

**Status update.** The fallback string is not present in the latest capture.
Records that previously carried it now show a specific generated narrative
quoting the correct figures. This suggests the template has been replaced, but
the capture covers only part of the list — confirm across a full payload before
closing. A related defect persists: one narrative cites a prior-quarter date
that does not match `last_rx_date` on its own row.

### 8.5 MEDIUM — narrative addresses the wrong reader

Many insights are second person to the **HCP** though the reader is the **rep**:

> "Arthur Magun, your Rx volume has surged by 300.0% this quarter…"

Others mix within one paragraph:

> "Sunil Joseph has seen a notable Rx increase… in his practice. Given that
> **your** last call on August 4, 2026, had an unknown outcome…"

**Action.** Fix the prompt to fix the reader as the representative and the HCP
as third person throughout.

**Status update: still open.** The latest capture shows both voices in the same
list — some narratives address the HCP in second person, others correctly use
third person about the HCP. The inconsistency is now visible within a single
screen, which makes it more noticeable to a rep, not less.

### 8.6 MEDIUM — internal contradictions within single narratives

```
Arthur Magun   "surged by 300.0% ... indicating strong stability"
Lisa Siby      "remains stable at 500, a notable increase from 0"
```

Growth and stability fragments concatenated without a consistency check.

### 8.7 MEDIUM — competitor share values have no structured source

Nearly every narrative states the competitor holds 0% share. Two diverge:

```
Richard Weirich   "holds a 100% share in the market"
Jack-Ky Wang      "holding only 1% of the competitor share"
```

No competitor-share field exists in the record, so all three values are
produced without a source. **Action:** add the field or remove competitor share
from the narrative entirely.

### 8.8 MEDIUM — warm-introduction referrals ignore geography

Four Illinois HCPs are told to seek a warm introduction via a prescriber in the
Bronx, New York:

```
Terry Miller             Freeport, IL     → referrer in Bronx, NY
Carmen Fotso-Kouatchou   West Dundee, IL  → referrer in Bronx, NY
Hugo Dulce               Addison, IL      → referrer in Bronx, NY
Myrna Patricio           Elgin, IL        → referrer in Bronx, NY
```

The peer-match step has no locality constraint. One referral also carries a
stray space before its full stop, indicating raw template concatenation.

### 8.9 MEDIUM — documented contract does not match the implementation

**Documented, absent from payload**
```
affiliated_hospital        ai_rx_trend_direction     ai_engagement_category
ai_predicted_next_q_rx     ai_engagement_urgency     analysis_badges
```

**Present in payload, undocumented**
```
ai_score_reason            last_rx_date              segment
```

**Type mismatch on the score field**
```
documented:  ai_priority_score   numeric 0-100        e.g. 82.5
actual:      ai_score            percentage string    e.g. "67.40%"
```

Different name, type, and representation. Any consumer built from the document
alone will fail.

**Actions**
- Reconcile the guide against the implementation; decide which is correct.
- Version the API contract and generate the doc from a schema.

### 8.10 LOW — score quantisation

Across 68 HCPs there are 11 distinct scores.

```
22.40% ×48    26.62% ×1    32.40% ×1    37.40% ×2    52.40% ×5    67.40% ×6
26.01% ×1     30.73% ×1    35.73% ×1    48.51% ×1    62.40% ×1
```

48 of 68 share one score; 6 share the top score. The scorer behaves as a coarse
rule-based additive model rather than a ranking function, so ordering within the
low tier carries no information and the top of the list is a six-way tie.

**Action.** Add a continuous tie-breaking component, or stop presenting the list
as strictly ordered.

### 8.11 LOW — records that should probably be filtered out

```
Ekow Pinkrah     hcp_status = Inactive,  hcp_type = Non-Prescribing,  rx_q1 = 100
Angela Conklin   hcp_status = Inactive                                rx_q1 = 500
Madison Hester   hcp_type   = Non-Prescribing                         rx_q1 = 100
```

Inactive HCPs are still scored and ranked. Non-prescribing professionals carry
prescription counts, contradictory on its face. Decide whether these belong in
the priority list at all.

### 8.12 RESOLVED — screen versus payload divergence

**Status: no longer reproducible. Verified against a later capture.**

Previously recorded: a screen showed Total HCPs 60, High 6, Medium 4, Target 4
against a payload carrying 68, 7, 11, 5; LAST RX rendered "Apr 30, 2026" where
the payload carried "Jul 24, 2026"; LAST CALL rendered "142 days ago" against
early-August call dates.

A later capture reconciles on every field checked.

```
KPI cards          screen 68 / 7 / 11 / 5      payload 68 / 7 / 11 / 5    match
LAST RX            screen Jul 24, 2026         payload Jul 24, 2026       match

LAST CALL — elapsed days derived against the on-screen refresh date
  Arthur Magun         19d ago → Aug 05    payload Aug 05    match
  Gary Gordon          19d ago → Aug 05    payload Aug 05    match
  Sijun Yang           17d ago → Aug 07    payload Aug 07    match
  Rachna Arora         16d ago → Aug 08    payload Aug 08    match
  Sheena Patel Cooke   17d ago → Aug 07    payload Aug 07    match
```

**Conclusion.** The earlier divergence was a stale capture, not a rendering
defect. The elapsed-day conversion is correct and computes against
`last_refresh`, not against the current date.

**Consequence for §7.** The payload can be treated as authoritative, which is
what §7.1 already assumed. The protocol in §7.6 — ask whether Apply was pressed
rather than contradict the user — remains the right handling for a genuinely
stale screen, but it is no longer papering over a known defect.

### 8.15 LOW — field naming defects in the published schema

The formal `/territory/summary` schema introduces two nested blocks whose key
names are inconsistent with the rest of the contract and with each other.

**Misspelling.**

```
Warm_condidates      ← as published
Warm_candidates      ← intended
```

Every consumer must reproduce the misspelling exactly. Fixing it later is a
breaking change, so decide now: correct it before any client binds to it, or
accept it permanently.

**Casing is inconsistent within a single object.**

```
new_writer_id
    Non_writers_in_Territory     Capitalised words, snake separators
    Prescribing_in_class         Capitalised first word only
    Diagnosis_match              Capitalised first word only
    Warm_condidates              Capitalised first word only

objection_handler
    calls_analysed               lower snake
    objections_detected          lower snake
    recurring_patterns           lower snake
    High_frequency               Capitalised
```

Four styles across eight keys, against a payload that is otherwise uniformly
lower snake case. **Action:** normalise to lower snake case and version the
contract before external consumers bind.

---

### 8.13 Compliance register

| # | Issue | Severity | Blocks release |
|---|---|---|---|
| 1 | PDRP-restricted Rx data rendered to reps (§8.1) | Critical | **Yes** |
| 2 | Generated content recommending off-label discussion (§8.2) | Critical | **Yes** |
| 3 | Generated prose naming the wrong payer entity (Action Center) | High | Review |
| 4 | Rep name paired with non-matching email in deploy target | High | Review |
| 5 | Narrative asserting no call activity against a logged call (§8.4) | Medium | No |
| 6 | Competitor share figures with no structured source (§8.7) | Medium | No |
| 7 | Inactive and non-prescribing HCPs ranked and scored (§8.11) | Low | No |
| — | Screen versus payload divergence (§8.12) | — | **Resolved** |

Open for the delivery team and client compliance function:

- Validation and sign-off procedure for generated content used in HCP-facing
  conversations.
- Audit logging and retention expectations.
- Data residency and retention requirements.

### 8.14 What reconciles correctly

Recorded so the failures above are not read as systemic.

- `total_hcps`, `high_priority_count`, and `medium_priority_count` match the
  ranked list exactly.
- Percentage growth figures quoted in narratives match `rx_q1` and `rx_q4`
  wherever an explicit percentage is given — the errors are in qualitative
  wording, not arithmetic.
- The newer single-territory KPI payload reconciles fully.
- The filters hierarchy structure matches the documented contract exactly.
- The rendered screen now reconciles with the payload on every field checked —
  KPI counts, last Rx date, and all five elapsed-day call figures (§8.12).
- The elapsed-day conversion computes against `last_refresh`, which is the
  correct reference point.

The counting and arithmetic logic is sound. The defects are missing data, one
hard-coded constant, unguarded narrative templates, unenforced compliance flags,
and documentation drift.

---

## 9. OPEN ITEMS

### 9.1 Branding and platform naming

Three names are in play across the artifacts:

```
client overview doc   "Veeva AI Insight 360"
application header    "Insights 360™ V2"  +  "SLIPSTREAM"
attribution badge     "POWERED BY DATAstream AI"  /  "DATAstream™ Rx"
```

This document uses the on-screen names, since that is what users will say.
Confirm which is externally correct before this reaches customers, and whether
the client overview needs updating to match the shipped UI.

### 9.2 Unresolved questions

1. Which service produces the 1000-base payload versus the reconciling one?
2. Is the score field name `ai_score` or `ai_priority_score` in the target
   contract?
3. Should the six documented-but-absent fields be implemented, or removed from
   the guide?
4. ~~Is the screen-versus-payload divergence a capture artefact or a live
   rendering defect?~~ **Answered — capture artefact. See §8.12.**
5. Should Inactive and non-prescribing HCPs appear in the priority list?
6. Is a Low Priority card intended, and if so at what value?
7. Is `Warm_condidates` corrected before external consumers bind, or accepted
   permanently? (§8.15)
8. Has the narrative fallback template been retired across the whole list, or
   only on the records visible in the latest capture? (§8.4)

---

## 10. VOCABULARY

| Term | Meaning |
|---|---|
| **HCP** | Healthcare professional — prescriber or clinical staff |
| **Rep** | Field sales representative. The primary user |
| **Manager** | Owns a set of representatives; sees their combined scope |
| **Territory** | A geographic or account-based assignment owned by a rep |
| **Segment** | CRM-assigned classification. Not model output |
| **AI Priority** | Model-assigned tier. Not a CRM field |
| **Target** | Whether the HCP is on the official call plan |
| **Score** | The model's percentage ranking value |
| **Rx** | Prescription |
| **Rx Q1 / Rx Q4** | Current-quarter and prior-quarter prescription volume |
| **NRx** | New prescription, as opposed to a refill |
| **Decile rank** | A market-share ranking band used in score reasoning |
| **NPI** | National Provider Identifier |
| **PDRP** | AMA Prescriber Data Restriction Program. An enrolled prescriber has opted out of Rx data disclosure to sales |
| **MLR** | Medical, Legal and Regulatory review. Approved content only |
| **Period** | The reporting quarter in the data reference panel |
| **Last refresh** | When the pipeline last calculated. Not the current time |
| **Weekly target** | Recommended visits for the current week |
| **PERT / EPI** | Pancreatic enzyme replacement therapy / exocrine pancreatic insufficiency |
| **In-class** | Products treating the same indication, including competitors |
| **CF HCP** | Cystic fibrosis segment classification |

**Brand references are generalised by design.** Payloads use generic labels in
place of confidential product and competitor names. That generalisation is a
governance control, not a data defect — reproduce the label exactly as given.


---

# PART 2 — NEW WRITER ID

**Application:** My Insights — RepStream · **Platform module:** Module 2 of 7

## 1. MODULE

| | |
|---|---|
| **Module name** | New Writer ID |
| **Section heading** | New writer identification |
| **Technique badge** | ML PATTERN MATCHING |
| **Parent application** | My Insights — RepStream |
| **Position** | Tab 2 of 3 in RepStream; Module 2 of 7 on the platform |
| **Primary user** | Field sales representative |
| **Therapy context** | Pancreatic enzyme replacement therapy (PERT / EPI) |
| **Write capability** | None, except generating an approach brief on demand |
| **Refresh cadence** | Batch; shares `last_refresh` with the parent application |

**The question this module answers:** *who is not prescribing our product yet,
but should be — and who can introduce me?*

Territory Prioritization ranks HCPs who already prescribe. This module does the
opposite: it finds HCPs prescribing **in-class** — treating the same condition
with a competitor — who have not written this product. For each, it identifies
an existing writer in their peer network who could make a warm introduction,
and drafts approach messaging.

**The module's own description of how it works, as displayed on screen:**

> AI identifies non-writers prescribing in-class and cross-references peer
> networks against existing writers using graph neural networks. Generates warm
> approach briefs per HCP with access status and recommended messaging. Matches
> on target ICD-10 codes.

Four claims sit in that sentence — non-writer identification, peer-network
graph matching, warm-brief generation, and ICD-10 matching. Section 8 records
which of them the current implementation actually delivers.

**The platform informs the decision; the representative makes it.** Generated
approach text is decision support for review by a qualified user — never an
autonomous decision, never a clinical recommendation, and never a substitute
for MLR-approved messaging.

---

## 2. MODULE DETAILS

### 2.1 Position in the platform

```
Veeva AI Insight 360 — 7 modules
│
├── My Insights (RepStream)
│   ├── Territory Prioritization      existing writers, ranked by opportunity
│   ├── New Writer ID              ← THIS MODULE — non-writers, conversion
│   └── Objection Handler             objections and approved responses
│
└── Action Center — launch and market defence
    ├── Active Alerts            threat feed, three streams
    ├── HCP Awareness            per-HCP awareness scores and trend
    ├── Competitive Intel        competitor signals and counter-strategy
    └── Payer Access             formulary tiers and access risk
```

**Relationship to Territory Prioritization.** The two modules partition the
territory by prescribing status, not by priority. An HCP appears in one or the
other, not both:

```
prescribes the product        → Territory Prioritization, ranked by opportunity
prescribes in-class only      → New Writer ID, ranked by peer match
prescribes neither            → in neither list
```

### 2.2 Sibling modules — routing reference

| Destination | Location | Holds | Route when the user asks |
|---|---|---|---|
| **Territory Prioritization** | tab | Existing writers ranked by opportunity | who should I visit, my ranked list, priority tier, Rx trend for an existing writer |
| **Objection Handler** | tab | Objections from call transcripts with approved responses | what do I say when, they told me, pushback, objection response, SKU reference |
| **Active Alerts** | Action Center | Machine-detected threats in three streams — competitive script shifts, payer formulary changes, HCP awareness decline — each with severity, counter-script and recommended actions | alerts, what changed, what needs my attention, counter script, deploy to field, affected HCPs |
| **HCP Awareness** | Action Center | Per-HCP awareness score tracked across four weekly periods, with trend direction, risk score and a recommended re-engagement action | awareness, is this HCP going cold, declining engagement, awareness trend, who needs a call |
| **Competitive Intel** | Action Center | Competitor signals — rep-visit surges, share gains, messaging campaigns — scored by threat level with executive summary, business impact and talking points | competitor activity, what is the competition doing, threat level, talking points, counter strategy |
| **Payer Access** | Action Center | Formulary tier status per payer, with tier-change detection, abandonment risk, covered lives and a prior-authorisation bridge note | formulary, tier change, payer, prior auth, PA, coverage, covered lives, abandonment |

### 2.3 How candidates are produced

| Stage | Technique | Output |
|---|---|---|
| Identify non-writers | In-class prescribing filter | `ai_non_writer_flag` |
| Peer network match | Graph neural network over referral and practice-overlap signals | `ai_peer_match_score`, `ai_peer_name`, `ai_peer_hcp_id` |
| Diagnosis match | Target ICD-10 code matching | `ai_icd10_matched_codes`, `ai_icd10_match_count` |
| Warm approach | Generative narrative | `ai_warm_approach_text`, `ai_peer_rationale` |
| Full brief | Generative, on demand | `approach_brief` object |

**`ai_peer_match_score` is a genuine continuous score.** Unlike the priority
score in Territory Prioritization, values on this tab are distinct per HCP. Two
candidates with different peer match scores are meaningfully ordered.

**Card order is by descending peer match score.**

---

## 3. FRONTEND — OVERVIEW AND KEYS

### 3.1 Page structure

```
┌────────────────────────────────────────────────────────────────────────────┐
│ [Territory Prioritization]  [New Writer ID]  [Objection Handler]           │
├────────────────────────────────────────────────────────────────────────────┤
│  New writer identification                        [ML PATTERN MATCHING]    │
│                                                                            │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ How it works                                                         │  │
│  │ AI identifies non-writers prescribing in-class and cross-references │  │
│  │ peer networks against existing writers using graph neural networks. │  │
│  │ Generates warm approach briefs per HCP with access status and       │  │
│  │ recommended messaging. Matches on target ICD-10 codes.              │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  ┌─────────────────────────────┐  ┌─────────────────────────────┐          │
│  │  candidate card             │  │  candidate card             │          │
│  └─────────────────────────────┘  └─────────────────────────────┘          │
│  ┌─────────────────────────────┐  ┌─────────────────────────────┐          │
│  │  candidate card             │  │  candidate card             │          │
│  └─────────────────────────────┘  └─────────────────────────────┘          │
└────────────────────────────────────────────────────────────────────────────┘
```

**Two-column grid**, unlike the single-column list on Territory Prioritization.

The filter bar, DATA REFERENCE panel, and assistant launcher are shared
application chrome — they behave identically on all three tabs and are
documented in the Territory Prioritization module document.

### 3.2 Candidate card anatomy

```
┌──────────────────────────────────────────────────────────────┐
│  (J)  <name>                                                 │
│       <specialty>                                            │
│       NBRx: <date>                          ← green text     │
│                                                              │
│  ┌────────────────────────────────────────────────────┐      │
│  │ WARM APPROACH (AI-GENERATED)                 [AI]  │      │
│  │ <generated approach text>                          │      │
│  └────────────────────────────────────────────────────┘      │
│                                                              │
│  ┌────────────────────────────────────────────────────┐      │
│  │ TARGET ICD-10 MATCH                  [AI MATCHED]  │      │
│  │ <codes>                                            │      │
│  └────────────────────────────────────────────────────┘      │
│                                                              │
│  ┌────────────────────────────────────────────────────┐      │
│  │ TOP RX IN SAME CLASS (Q1 2026)                     │      │
│  │ <competitor brand>                      <n> Rx     │      │
│  └────────────────────────────────────────────────────┘      │
│                                                              │
│  Total in-class: <n> Rx/qtr        Peer match: <n.n>%  [AI]  │
│  Connected to <peer name>                                    │
│                                                              │
│  [        Generate Approach Brief        ]                   │
└──────────────────────────────────────────────────────────────┘
```

| Element | Notes |
|---|---|
| Avatar | Circular, first initial. Colour varies — see §9.2, meaning unconfirmed |
| Name | Bold, dark blue |
| Specialty | Muted grey |
| NBRx | Green. Date of most recent new prescription in-class |
| WARM APPROACH panel | Grey background, `AI` badge. Generated text |
| TARGET ICD-10 MATCH panel | Orange border, `AI MATCHED` badge |
| TOP RX IN SAME CLASS panel | Blue background. Competitor and volume |
| Total in-class | Bold, left of the footer row |
| Peer match | Bold green percentage with `AI` badge, right of the footer row |
| Connected to | Named peer who could make the introduction |
| Generate Approach Brief | Full-width dark button. Triggers on-demand generation |

### 3.3 Panel semantics

**TARGET ICD-10 MATCH** is the diagnosis-overlap evidence — which target
diagnosis codes this HCP treats. The `AI MATCHED` badge asserts a match was
found. See §8.3 for the current state of this panel.

**TOP RX IN SAME CLASS (Q1 2026)** names the competitor this HCP currently
prescribes and the volume. This is the substitution opportunity.

**Peer match** is the graph-model confidence that the named peer's network
overlaps this HCP's practice — the strength of the warm-introduction path, not
a likelihood of conversion.

---

## 4. BACKEND — KEY DETAILS

### 4.1 Data delivery

**Candidate cards arrive as one array** when the tab loads, ordered by
descending peer match score.

**The approach brief is generated on demand.** It is produced when Generate
Approach Brief is pressed, not returned with the candidate list. Until then
`approach_brief` is empty — the assistant cannot answer from it.

**KPI counts arrive with the shared application summary**, the same response
that serves the other two tabs. See §4.4.

**Territory scope is derived from the authenticated session**, not chosen
freely. Every figure corresponds to the filter currently in force.

### 4.2 Candidate payload — field inventory

| Field | Type | On card | Notes |
|---|---|---|---|
| `hcp_id` | string | No | Join key; path param for the brief |
| `name` | string | Yes | See §8.2 — delimiter defect |
| `specialty` | string | Yes | |
| `affiliated_hospital` | string | No | Often an empty string, not null |
| `city` / `state` | string | No | Practice location |
| `territory_id` | string | No | Owning territory |
| `segment` | string | No | CRM classification |
| `in_class_rx_q1` | integer | No | Current-quarter in-class volume |
| `brand_rx_q1` | integer | No | Current-quarter product volume |
| `brand_rx_q4` | integer | No | Prior-quarter product volume |
| `competitor_brand` | string | Yes | Named in TOP RX panel |
| `competitor_volume` | integer | Yes | Volume in TOP RX panel |
| `last_nrx_date` | string | Yes | Rendered as `NBRx: <date>` |
| `total_in_class_rx` | integer | Yes | Rendered as `<n> Rx/qtr` |
| `top_5_in_class_rx` | array | Yes¹ | Array of `{brand, rx}` objects |
| `ai_peer_match_score` | number | Yes | Bare number, **not** a percentage string |
| `ai_peer_name` | string | Yes | Rendered as `Connected to <name>` |
| `ai_peer_hcp_id` | string | No | Peer's identifier |
| `ai_peer_rationale` | string | No | Often identical to the warm approach text |
| `ai_icd10_matched_codes` | string | Yes | Often an empty string — §8.3 |
| `ai_icd10_match_count` | integer | No | Often zero — §8.3 |
| `ai_non_writer_flag` | boolean | No | Qualification flag |
| `ai_warm_approach_text` | string | Yes | WARM APPROACH panel body |
| `ai_approach_highlight` | string | No | Frequently null — §8.7 |
| `ai_approach_brief` | string | No | Frequently null — §8.7 |
| `approach_brief` | object | On click | Empty until generated — §4.3 |
| `analysis_badges` | array | No | e.g. ML_PATTERN_MATCHING, AI_GENERATED |
| `ai_is_identified` | boolean | No | Relationship to `ai_non_writer_flag` unconfirmed |

¹ Only the top entry is rendered, despite the field name.

**Type contrast worth noting.** `ai_peer_match_score` is a bare number here,
while `ai_score` on Territory Prioritization is a percentage **string**. Two
scores, two representations, one application. Do not apply one tab's handling
to the other.

### 4.3 `approach_brief` object

Populated only after Generate Approach Brief is pressed. Structure observed:

```
approach_brief
    email
        to                      recipient address
        to_name                 recipient display name
        subject                 email subject line
        email_body              full drafted message, newline-delimited
    key_discussion_points       array of short strings
```

**`email.to_name` is correctly spaced** even when the top-level `name` field is
delimiter-broken — evidence the defect in §8.2 is introduced by whatever builds
`name`, not by the source record.

### 4.4 KPI block — `new_writer_id`

Delivered with the shared application summary, which serves all three tabs.

```
new_writer_id
    Non_writers_in_Territory   integer   HCPs not prescribing the product
    Prescribing_in_class       integer   of those, prescribing a competitor
    Diagnosis_match            integer   of those, matching target ICD-10 codes
    Warm_condidates            integer   of those, with a viable peer path
```

**These are a funnel, narrowing left to right.** Each count should be less than
or equal to the one before it.

`Warm_condidates` is spelled exactly as returned. See §8.8.

---

## 5. FRONTEND ↔ BACKEND MAPPING

### 5.1 Candidate card

| UI element | Payload field | Transform |
|---|---|---|
| Avatar initial | `name` | First character |
| Name | `name` | Direct — comma not corrected, §8.2 |
| Specialty | `specialty` | Direct |
| `NBRx: <date>` | `last_nrx_date` | Prefixed "NBRx: " |
| WARM APPROACH body | `ai_warm_approach_text` | Direct |
| TARGET ICD-10 MATCH body | `ai_icd10_matched_codes` | Direct |
| `AI MATCHED` badge | — | **Static, not conditional** — §8.3 |
| TOP RX brand | `competitor_brand` | Direct |
| TOP RX volume | `competitor_volume` | Suffixed " Rx" |
| `Total in-class: <n> Rx/qtr` | `total_in_class_rx` | Suffixed " Rx/qtr" |
| `Peer match: <n.n>%` | `ai_peer_match_score` | Suffixed "%" — no division |
| `Connected to <name>` | `ai_peer_name` | Prefixed "Connected to " |
| Generate Approach Brief | `hcp_id` | Identifies which HCP to generate for |
| *(not rendered)* | `city`, `state`, `segment`, `brand_rx_q1`, `brand_rx_q4`, `in_class_rx_q1`, `affiliated_hospital`, `ai_peer_rationale`, `ai_peer_hcp_id`, `analysis_badges` | Available, unused on card |

### 5.2 KPI block

| KPI | Payload field | Rendered on this tab |
|---|---|---|
| Non-writers in territory | `new_writer_id.Non_writers_in_Territory` | Header area |
| Prescribing in class | `new_writer_id.Prescribing_in_class` | Header area |
| Diagnosis match | `new_writer_id.Diagnosis_match` | Header area |
| Warm candidates | `new_writer_id.Warm_condidates` | Header area |

### 5.3 Mapping traps

**`ai_peer_match_score` needs no conversion.** It arrives as a bare number and
renders with a `%` suffix. Multiplying by 100 produces a figure in the
thousands.

**`AI MATCHED` is a static badge.** It renders regardless of whether
`ai_icd10_matched_codes` contains anything. The badge is not evidence that a
match occurred — check the field.

**`top_5_in_class_rx` is an array but only its top entry is rendered.** The
remaining entries are available and unused.

**Three similarly named approach fields exist.** `ai_approach_highlight`,
`ai_approach_brief`, and `approach_brief`. Only the last carries the generated
brief. See §8.7.

**Empty string is not null.** `affiliated_hospital` and
`ai_icd10_matched_codes` arrive as `""`. A null check will not catch them.

---

## 6. GRAPHICAL FLOW

### 6.1 Candidate qualification funnel

```
   All HCPs in territory
            │
            ▼
   ai_non_writer_flag = true            ── not prescribing the product
            │                              → Non_writers_in_Territory
            ▼
   in-class prescribing > 0             ── treating the condition with
            │                              a competitor
            │                              → Prescribing_in_class
            ▼
   target ICD-10 code overlap           ── diagnosis match
            │                              → Diagnosis_match
            ▼
   peer network path exists             ── an existing writer connects
            │                              → Warm_condidates
            ▼
   Candidate card, ordered by ai_peer_match_score descending
```

### 6.2 Page lifecycle

```
   Rep opens New Writer ID
            │
            ▼
   Territory scope resolved from the authenticated session
            │
            ├──────────► KPI counts          Non_writers_in_Territory
            │                                Prescribing_in_class
            │                                Diagnosis_match
            │                                Warm_condidates
            │
            └──────────► Candidate card grid
                              ordered by descending peer match
                                        │
                                        ▼
                          [Generate Approach Brief] pressed
                                        │
                                        ▼
                              approach_brief populated
                              ├── email {to, to_name, subject, email_body}
                              └── key_discussion_points []

   Until the button is pressed, approach_brief is empty.
```

### 6.3 Peer network match

```
   Candidate HCP                          Existing writer
        │                                       │
        │      graph neural network over        │
        │      referral patterns, practice      │
        │      overlap, shared patient flow     │
        └───────────────┬───────────────────────┘
                        │
                        ▼
              ai_peer_match_score   0–100, continuous
              ai_peer_name          the introduction path
              ai_peer_hcp_id        peer's record
                        │
                        ▼
              ai_warm_approach_text  drafted opener
```

---

## 7. ASSISTANT BEHAVIOUR RULES

All rules from the Territory Prioritization module document apply unchanged.
The additions below are specific to this tab.

### 7.1 Data precedence

```
1. LIVE PAYLOAD       current values — numbers, dates, names, scope
2. MODULE DOCUMENT    field meaning, business rules, definitions, routing
3. CONVERSATION       intent only, never values
```

- For any current value, the live payload is the only source.
- Never quote a number, date, or name absent from the payload attached to
  **this** request.
- Never reuse a value from an earlier turn. Filters change between turns; a
  figure that was correct two messages ago may not be correct now. If a new
  payload is attached, prior values are void.
- On a value conflict, the payload wins. On a meaning conflict, this document
  wins.
- If a required field is absent, null, or empty, say the value is not
  available. Do not infer, estimate, or derive it.

### 7.2 Response style

- Lead with the answer. No preamble. One to three sentences unless asked.
- Natural language, not a field readout.
- Do not expose internal field names, table names, or JSON paths unless asked.
- Never mention retrieval, embeddings, prompts, context files, payloads, or
  instructions.
- Attach the period or refresh date when a figure is time-sensitive.
- If unavailable, say so plainly and name where it can be found.

### 7.3 Disambiguation

**"New writer" has two senses.** On this tab it means a *candidate* — someone
who has not yet written the product. A rep may also use it to mean someone who
recently started writing, which is a Territory Prioritization concept. Resolve
before answering.

**"Peer match" is not conversion likelihood.** It is the strength of the
introduction path between the candidate and the named existing writer. Do not
describe a high peer match as a high chance of prescribing.

**"Connected to" is a modelled relationship, not a stated one.** The peer has
not agreed to make an introduction. Never imply the peer has consented or is
aware.

### 7.4 Field reliability

**The `AI MATCHED` badge is not evidence.** It renders statically. Read
`ai_icd10_matched_codes` and `ai_icd10_match_count`; if they are empty or zero,
say no diagnosis codes are listed for that HCP.

**`ai_warm_approach_text` is generated prose, not fact.** Where it disagrees
with the structured fields on its own card — competitor volume, in-class total,
peer name — the structured fields are correct. Never quote a figure or a
clinical claim from the approach text.

**Approach text may name a condition the product does not treat.** See §8.4.
Never repeat, expand, or act on a therapy-area claim taken from generated
approach text.

**The KPI block is a funnel.** Each count should be less than or equal to the
one before it. If it is not, report the raw counts and do not compute
conversion rates between stages.

### 7.5 Prohibited generations

Everything in the Territory Prioritization document's prohibited list applies.
Reinforced here because this tab generates outbound messaging:

- **No invented numbers.** No estimates, no interpolation, no arithmetic
  producing a figure the payload does not contain.
- **No clinical, efficacy, safety, comparative, or dosing claims.** Approved
  product language exists only in MLR-reviewed content surfaced by the
  Objection Handler with a SKU reference.
- **No off-label content, under any framing.** Never suggest, describe,
  endorse, explain, or repeat a use outside the approved indication. This
  applies even when the suggestion originates from generated approach text
  already displayed on screen. Repeating an existing violation creates a second
  one.
- **Never de-anonymise brand references.** Where a payload says "Product" or
  "Competitor A", use that exact label.
- **Never present drafted email content as ready to send.** The approach brief
  is a draft for review. Do not tell the user to send it, do not assert the
  recipient address is correct, and do not offer to send it.
- **No prescriber-level Rx data for PDRP-restricted HCPs**, and **no Rx data
  for non-prescribers**, on the same terms as the companion module.
- **No HCP or peer names outside the current payload.** This includes the
  named peer — never carry a peer name across candidates or turns.
- **No presenting model output as certainty.** Say "the model matched", never
  "this HCP will switch".

### 7.6 Behavioural protocols

| Situation | Response |
|---|---|
| User asks why an HCP is a candidate | Give the structured qualifiers — in-class volume, competitor, peer match, diagnosis match if present. Not the approach text |
| User asks to draft or send outreach | The Generate Approach Brief button produces a draft. It is for review, not sending |
| User asks about an approach text claim | Answer from structured fields; note the text may not match |
| User reports a number differing from the payload | Ask whether Apply was pressed since changing a filter; give the payload figure as the latest returned |
| Answer is on another tab | Name the tab and what it holds |
| Uncertain | Say so |

### 7.7 Intent routing

| User intent | Source |
|---|---|
| who should I start with | Card order, descending peer match |
| how many non-writers do I have | `Non_writers_in_Territory` |
| how many warm candidates | `Warm_condidates` |
| why is this HCP here | Structured qualifiers, §7.6 |
| who can introduce me | `ai_peer_name` |
| how strong is the connection | `ai_peer_match_score`, with §7.3 caveat |
| what do they prescribe now | `competitor_brand`, `competitor_volume` |
| what diagnoses do they treat | `ai_icd10_matched_codes` — check it is populated |
| draft me an email | Generate Approach Brief — draft only |
| when did they last write in class | `last_nrx_date` |
| my ranked list / priority tier | Territory Prioritization tab |
| what do I say when they object | Objection Handler tab |
| alerts / what changed | Active Alerts — Action Center |
| is this HCP going cold | HCP Awareness — Action Center |
| what is the competitor doing | Competitive Intel — Action Center |
| formulary / tier / prior auth | Payer Access — Action Center |

### 7.8 What this module can and cannot answer

**Available:** any KPI value and its meaning; for any listed candidate — name,
specialty, last in-class NBRx date, competitor and volume, total in-class
volume, peer match score, named peer, and diagnosis codes where populated; what
any panel, badge, or button does; how candidates are qualified.

**Not available:** the approach brief until the button is pressed; prescribing
history beyond the fields on the card; anything belonging to sibling modules;
whether the named peer has agreed to introduce; likelihood of conversion.

---

## 8. DATA QUALITY REGISTER

Ordered by severity.

### 8.1 CRITICAL — approach text recommending off-label discussion

A generated approach narrative recommends discussing "potential off-label uses"
during an HCP visit. Promotion of unapproved uses is a regulatory violation
regardless of intent, and this reached a rendered screen.

**Actions**
- Add an off-label term filter to the generation post-check that **blocks** the
  output rather than flagging it.
- Review the generation prompt for anything inviting discussion of uses outside
  the approved indication.
- Report the instance through the MLR process.

### 8.2 CRITICAL — approach text proposes an unrelated indication

Two candidate cards carry approach text of the form:

> "Based on shared patient referral patterns with <peer>, your C-diff
> recurrence patients could benefit from the Product starter program."

The product on this platform is a pancreatic enzyme replacement therapy for
exocrine pancreatic insufficiency. *Clostridioides difficile* recurrence is a
different condition with a different treatment pathway. The sentence proposes
the product for a population it is not indicated for, and it is presented to
the rep as ready-to-use opening messaging.

This is the same class of failure as §8.1 but harder to spot, because it does
not contain the phrase "off-label" — it simply names the wrong disease.

**Actions**
- Constrain the generation prompt to the approved indication. The therapy area
  must not be a free variable in the template.
- Add an indication allow-list to the post-check, not just a term deny-list.
- Audit every template variant currently in rotation, not only the ones
  observed.
- Report through the MLR process alongside §8.1.

### 8.3 HIGH — TARGET ICD-10 MATCH renders empty with a match badge

Every observed candidate card displays the TARGET ICD-10 MATCH panel with an
`AI MATCHED` badge and **no codes inside it**. The schema defaults are
consistent with this:

```
ai_icd10_matched_codes    ""     empty string, not null
ai_icd10_match_count      0
```

The badge asserts a diagnosis match that the data does not support. A rep
reading the card concludes the HCP treats the target diagnoses; nothing in the
payload says so.

The module's own "How it works" text claims it "matches on target ICD-10
codes". On current evidence that stage produces nothing.

**Actions**
- Make the badge conditional on `ai_icd10_match_count > 0`.
- Hide the panel entirely when the code list is empty.
- Investigate whether the ICD-10 matching stage is running at all.
- Until fixed, the `Diagnosis_match` KPI should be treated as unverified.

### 8.4 HIGH — warm approach text is template mail-merge, labelled AI-GENERATED

Eight observed cards carry four distinct sentence templates, with only the peer
name and institution substituted:

```
template A   "<peer> at <hospital> has seen strong results with Product
              for EPI patients — worth a warm intro conversation around
              your current PERT cases."                          3 cards
template B   "Given your patient profile overlap with <peer>'s practice,
              Product's dosing flexibility may address your current
              access concerns."                                  2 cards
template C   "Based on shared patient referral patterns with <peer>, your
              C-diff recurrence patients could benefit from the Product
              starter program."                                  2 cards
template D   "Your colleague <peer> recently switched 3 patients from
              Competitor A to Product and reported improved tolerability."
                                                                 1 card
```

The panel is labelled **WARM APPROACH (AI-GENERATED)** and carries an `AI`
badge. Four rotating templates with slot substitution is not generation, and
the label overstates what the system does. Template D additionally asserts a
specific clinical outcome — "switched 3 patients… improved tolerability" — with
no field in the payload to source it from.

**Actions**
- Either generate genuinely per-HCP text, or relabel the panel to reflect
  templated messaging.
- Remove the unsourced clinical claim in template D.
- Reconcile with §8.2 — template C is one of the four.

### 8.5 HIGH — same peer, two different institutions

```
Dr. James Wilson at "Philadelphia Medical"    on one candidate card
Dr. James Wilson at "Chicago Medical"         on another
```

The same named peer is attributed to two institutions in the same view. Either
the peer record has no canonical affiliation, or the institution is being
filled from the candidate's own location rather than the peer's.

**Action.** Source the institution from the peer's record via
`ai_peer_hcp_id`, or omit it from the template.

### 8.6 MEDIUM — candidate qualifies with zero in-class volume

One card shows `Total in-class: 0 Rx/qtr` while the module premise is
"non-writers **prescribing in-class**". An HCP writing nothing in-class does
not meet the stated qualification criterion, yet appears in the list with a
peer match score.

**Action.** Confirm the qualification filter. If zero in-class is intentional —
for example a diagnosis-only match — the "How it works" description needs to
say so.

### 8.7 MEDIUM — three approach fields, two of them null

```
ai_approach_highlight    string    frequently null
ai_approach_brief        string    frequently null
approach_brief           object    holds the actual content
```

Two of the three are consistently empty while a third, differently named field
carries the payload. This looks like two generations of the field coexisting.
Any consumer that reads `ai_approach_brief` expecting the brief gets nothing.

**Action.** Remove the dead fields or document their intended purpose.

### 8.8 MEDIUM — name field is comma-delimited

Every observed candidate name renders with a comma where a space belongs:

```
"Jessica,Fligge"          should be "Jessica Fligge"
"Jeffrey Christian,Tang"  should be "Jeffrey Christian Tang"
```

All eight observed cards are affected — this is systematic, not sporadic.

**The same person's name is correct inside `approach_brief.email.to_name`**,
which confirms the source record is fine and the defect is introduced by
whatever assembles the top-level `name` field — most likely a last/first
concatenation using the wrong separator.

**Action.** Fix the concatenation at source. Do not patch at render time, or
the two representations will drift.

### 8.9 MEDIUM — duplicate narrative fields

`ai_peer_rationale` and `ai_warm_approach_text` have been observed
byte-identical. The same paragraph is stored twice per record.

**Action.** Keep one, or give them distinct purposes.

### 8.10 LOW — missing values render with their label

One card displays `NBRx:` with no date. The label renders whether or not
`last_nrx_date` is populated.

**Action.** Suppress the label when the value is empty.

### 8.11 LOW — field naming defects in the KPI block

```
Warm_condidates          ← as published; "candidates" is intended
```

Casing is also inconsistent within the block — `Non_writers_in_Territory`,
`Prescribing_in_class`, `Diagnosis_match`, `Warm_condidates` use three
different styles against an otherwise lower-snake payload.

**Action.** Correct and normalise before external consumers bind. Fixing it
later is a breaking change.

### 8.12 LOW — empty strings where null is meant

`affiliated_hospital` and `ai_icd10_matched_codes` arrive as `""` rather than
null. Null checks miss them and they render as blank-but-present.

**Action.** Return null, or coerce at the API layer.

### 8.13 Compliance register

| # | Issue | Severity | Blocks release |
|---|---|---|---|
| 1 | Approach text recommending off-label discussion (§8.1) | Critical | **Yes** |
| 2 | Approach text proposing an unrelated indication (§8.2) | Critical | **Yes** |
| 3 | `AI MATCHED` badge asserting an unsupported match (§8.3) | High | Review |
| 4 | Unsourced clinical outcome claim in template D (§8.4) | High | Review |
| 5 | Generated messaging labelled AI when template-driven (§8.4) | Medium | No |
| 6 | Peer institution inconsistent across cards (§8.5) | Medium | No |
| 7 | Candidate qualifying with zero in-class volume (§8.6) | Medium | No |

Items 1 and 2 are the same underlying failure — the generation prompt does not
constrain therapy area — and should be fixed together.

Open for the delivery team and client compliance function:

- Validation and sign-off procedure for approach text used in HCP-facing
  conversations. This module produces outbound messaging, so the exposure is
  higher than on Territory Prioritization.
- Whether drafted emails may be sent from the application at all, and under
  what review.
- Audit logging for generated briefs.

### 8.14 What works correctly

Recorded so the failures above are not read as systemic.

- **`ai_peer_match_score` is genuinely continuous.** Seven observed values,
  seven distinct — unlike the heavily quantised priority score on the companion
  tab. The ordering carries real information.
- **Card order matches descending peer match** in every observed case.
- **`competitor_volume` and `total_in_class_rx` agree** on every card where
  both are visible.
- **`approach_brief.email.to_name` is correctly formatted**, which is what
  isolates the §8.8 defect to the `name` assembly step.
- The funnel structure of the KPI block is coherent and matches the
  qualification stages.

---

## 9. OPEN ITEMS

### 9.1 Unresolved questions

1. Is the ICD-10 matching stage running at all? (§8.3)
2. What distinguishes `ai_non_writer_flag` from `ai_is_identified`?
3. Is zero in-class volume a valid qualification, or a filter defect? (§8.6)
4. What are `ai_approach_highlight` and `ai_approach_brief` for? (§8.7)
5. Is `Warm_condidates` corrected before external consumers bind? (§8.11)
6. How many approach templates are in rotation in total? Four were observed;
   §8.2 requires auditing all of them.
7. Can drafted emails be sent from the application, or is it copy-only?
8. Are the four KPI counts guaranteed monotonic, or can a later stage exceed an
   earlier one?

### 9.2 Avatar colour

Candidate avatars render in at least two colours. The two highest peer-match
cards observed were one colour and the remainder another, which is consistent
with a threshold — but the sample is too small to confirm, and no field in the
payload obviously drives it.

**Action.** Confirm what the colour encodes and document it, or make it
uniform. An unexplained colour difference reads as meaningful to a rep.

---

## 10. VOCABULARY

| Term | Meaning |
|---|---|
| **New writer** | On this tab, a *candidate* — an HCP not yet prescribing the product |
| **Non-writer** | An HCP with no product prescriptions in the period |
| **In-class** | Products treating the same indication, including competitors |
| **NBRx** | New brand prescription — the most recent in-class new start |
| **NRx** | New prescription, as opposed to a refill |
| **Rx/qtr** | Prescriptions per quarter |
| **Peer match** | Graph-model confidence in the introduction path. Not conversion likelihood |
| **Warm approach** | Drafted opening message using the peer relationship |
| **Approach brief** | Fuller on-demand output: drafted email plus discussion points |
| **Connected to** | The existing writer the model identified as an introduction path |
| **ICD-10** | Diagnosis coding system used for the target-condition match |
| **Target ICD-10** | The diagnosis codes the product's indication covers |
| **Starter program** | A patient-initiation support programme |
| **Graph neural network** | The model class used for peer-network matching |
| **HCP** | Healthcare professional — prescriber or clinical staff |
| **Rep** | Field sales representative. The primary user |
| **Segment** | CRM-assigned classification. Not model output |
| **PDRP** | AMA Prescriber Data Restriction Program |
| **MLR** | Medical, Legal and Regulatory review. Approved content only |
| **PERT / EPI** | Pancreatic enzyme replacement therapy / exocrine pancreatic insufficiency |

**Brand references are generalised by design.** Payloads use generic labels in
place of confidential product and competitor names. That generalisation is a
governance control, not a data defect — reproduce the label exactly as given.

---

**If any part of this document is used as machine-readable context, exclude
sections 8 and 9.** They contain named records and concrete figures, including
the exact generated text §7.5 forbids the assistant from repeating.


---

# PART 3 — OBJECTION HANDLER

**Application:** My Insights — RepStream · **Platform module:** Module 3 of 7

## 1. MODULE

| | |
|---|---|
| **Module name** | Objection Handler |
| **Section heading** | Pattern objection handler |
| **Technique badge** | NLP ANALYSIS |
| **Parent application** | My Insights — RepStream |
| **Position** | Tab 3 of 3 in RepStream; Module 3 of 7 on the platform |
| **Primary user** | Field sales representative |
| **Therapy context** | Pancreatic enzyme replacement therapy (PERT / EPI) |
| **Write capability** | One action — Add to Next Call Prep |
| **Refresh cadence** | Batch; shares `last_refresh` with the parent application |

**The question this module answers:** *what are HCPs actually pushing back on,
and what am I approved to say in response?*

The other two RepStream tabs decide **who** to visit. This one prepares **what
to say**. It reads call transcripts, classifies the objections raised, ranks
them by how often they recur, and pairs each with an MLR-reviewed response
carrying a SKU reference.

**The module's own description, as displayed on screen:**

> AI analyzes call transcripts using NLP to surface top objections by HCP
> segment. ML models calculate which MLR-approved responses have the highest
> conversion rates for each objection type.

Three claims sit in that sentence — transcript NLP, segmentation by HCP, and
conversion-rate optimisation of responses. Section 8 records which the current
implementation delivers.

**This is the only module that surfaces approved product language.** Every
other tab generates prose. Here the response body is MLR-reviewed copy with an
auditable SKU. That distinction governs how the text may be used — see §7.5.

---

## 2. MODULE DETAILS

### 2.1 Position in the platform

```
Veeva AI Insight 360 — 7 modules
│
├── My Insights (RepStream)
│   ├── Territory Prioritization      existing writers, ranked by opportunity
│   ├── New Writer ID                 non-writers, conversion candidates
│   └── Objection Handler          ← THIS MODULE — what to say
│
└── Action Center — launch and market defence
    ├── Active Alerts            threat feed, three streams
    ├── HCP Awareness            per-HCP awareness scores and trend
    ├── Competitive Intel        competitor signals and counter-strategy
    └── Payer Access             formulary tiers and access risk
```

**Relationship to the sibling tabs.** Territory Prioritization and New Writer ID
partition HCPs by prescribing status. This module is not HCP-scoped at all — it
aggregates across calls in the territory. A card describes a *pattern*, not a
person.

```
Territory Prioritization    one card = one HCP who prescribes
New Writer ID               one card = one HCP who does not
Objection Handler           one card = one recurring objection
```

### 2.2 Sibling modules — routing reference

| Destination | Location | Holds | Route when the user asks |
|---|---|---|---|
| **Territory Prioritization** | tab | Existing writers ranked by opportunity | who should I visit, my ranked list, priority tier, Rx trend |
| **New Writer ID** | tab | Non-writers with peer-match introduction paths | who should I start, non-writers, warm intro, draft an email |
| **Active Alerts** | Action Center | Machine-detected threats in three streams, with severity, counter-script and recommended actions | alerts, what changed, what needs my attention, deploy to field |
| **HCP Awareness** | Action Center | Per-HCP awareness score across four weekly periods, with trend and re-engagement action | awareness, is this HCP going cold, declining engagement |
| **Competitive Intel** | Action Center | Competitor signals scored by threat level, with executive summary, business impact and talking points | competitor activity, threat level, talking points, counter strategy |
| **Payer Access** | Action Center | Formulary tier per payer with abandonment risk and a PA bridge note | formulary, tier change, payer, prior auth, coverage |

**The nearest neighbour is Competitive Intel.** Both produce things to say.
This module answers a *stated* objection from a transcript; Competitive Intel
answers a *detected* market signal. If the rep says "they told me…", route here.
If they say "what is the competitor doing", route there.

### 2.3 How objections are produced

| Stage | Technique | Output |
|---|---|---|
| Transcript analysis | NLP over call notes and transcripts | `objection_text` |
| Classification | NLP categorisation into objection types | `objection_type` |
| Frequency ranking | Occurrence count across calls in the period | `ai_call_count`, `ai_frequency_label` |
| Response pairing | Selection from the MLR-approved response library | `ai_mlr_response`, `ai_sku` |
| Conversion scoring | ML over historical response outcomes | `ai_conversion_score` |

**Card order is by descending frequency**, not by conversion score.

### 2.4 Frequency banding

`ai_frequency_label` bands `ai_call_count`:

```
HIGH     more than 10 calls in the period
MEDIUM   5 to 9 calls
LOW      fewer than 5 calls
```

The label is a display band. `ai_call_count` is the underlying number, and it
is the more useful answer when a rep asks how often something comes up.

### 2.5 Conversion score

`ai_conversion_score` is the modelled rate at which the paired response moved
the conversation forward historically. It is a property of the **response**,
not of the objection and not of any individual HCP.

Values are genuinely continuous and differ per card, so two responses with
different conversion scores are meaningfully ordered.

**It is not a promise.** A high conversion score does not mean this HCP will be
persuaded. See §7.3.

---

## 3. FRONTEND — OVERVIEW AND KEYS

### 3.1 Page structure

```
┌────────────────────────────────────────────────────────────────────────────┐
│ [Territory Prioritization]  [New Writer ID]  [Objection Handler]           │
├────────────────────────────────────────────────────────────────────────────┤
│  Pattern objection handler                              [NLP ANALYSIS]     │
│                                                                            │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ How it works                                                         │  │
│  │ AI analyzes call transcripts using NLP to surface top objections    │  │
│  │ by HCP segment. ML models calculate which MLR-approved responses    │  │
│  │ have the highest conversion rates for each objection type.          │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  COMMON OBJECTIONS (<date range>)                                          │
│                                                                            │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  objection card                                                      │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  objection card                                                      │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────────┘
```

**Single-column, full-width cards** — unlike the two-column grid on New Writer
ID. Each card is wide because the response body is the payload.

The filter bar, DATA REFERENCE panel and assistant launcher are shared
application chrome, documented in the Territory Prioritization module document.

### 3.2 Objection card anatomy

```
┌────────────────────────────────────────────────────────────────────────┐
│  "<objection text>"                              [HIGH FREQUENCY]      │
│                                                                        │
│  Mentioned in <n> calls (<date range>) Conversion score: <n>%          │
│                                                                        │
│  [DETECTED BY AI]                                                      │
│                                                                        │
│  ┌──────────────────────────────────────────────────────────────┐      │
│  │ RECOMMENDED RESPONSE (MLR-APPROVED)            [AI OPTIMIZED] │      │
│  │                                                              │      │
│  │ "<response text>"                                            │      │
│  │                                                              │      │
│  │ <response text> (SKU: <sku>)                                 │      │
│  └──────────────────────────────────────────────────────────────┘      │
│                                                                        │
│  [ Add to Next Call Prep ]     <objection type>                        │
└────────────────────────────────────────────────────────────────────────┘
```

| Element | Notes |
|---|---|
| Objection text | Bold dark blue, wrapped in quotation marks. The verbatim pattern |
| Frequency badge | Top right. Orange for HIGH, blue for MEDIUM |
| Metrics line | Call count bold, date range in parentheses, conversion score bold green |
| DETECTED BY AI | Purple badge under the metrics line |
| Response panel | Grey background, `AI OPTIMIZED` badge top right |
| Response body | **Rendered twice** — see §8.2 |
| SKU | Appended to the second paragraph, in parentheses |
| Add to Next Call Prep | Outlined button, bottom left. The only write action |
| Objection type chip | Blue text, right of the button |

### 3.3 Panel semantics

**RECOMMENDED RESPONSE (MLR-APPROVED)** is the compliance boundary of this
module. The text inside is reviewed copy; the SKU is its audit reference. This
is the only place in RepStream where approved product language is surfaced.

**The `AI OPTIMIZED` badge** sits on the same panel. Its intended meaning is
that the model *selected* this approved response, not that it rewrote one.
See §8.3 — the label is ambiguous in a way that matters.

**DETECTED BY AI** indicates the objection pattern was surfaced by transcript
analysis rather than manually catalogued.

**Add to Next Call Prep** attaches the objection and its response to the rep's
preparation for their next call. It is the only state-changing action in
RepStream.

---

## 4. BACKEND — KEY DETAILS

### 4.1 Data delivery

**Objection cards arrive as one array** when the tab loads, ordered by
descending frequency.

**KPI counts arrive with the shared application summary**, the same response
that serves the other two tabs. See §4.3.

**Add to Next Call Prep is a write.** Everything else on this tab is read-only.

**Territory scope is derived from the authenticated session**, not chosen
freely. Every figure corresponds to the filter currently in force.

### 4.2 Objection payload — field inventory

| Field | Type | On card | Notes |
|---|---|---|---|
| `objection_id` | string | No | Record identifier — see §8.4 |
| `objection_type` | string | Yes | Chip beside the button |
| `objection_text` | string | Yes | Card heading, quoted |
| `period` | string | Yes | Rendered in the metrics line |
| `territory_id` | string | No | Owning territory |
| `hcp_segment` | string | No | Observed null throughout — §8.5 |
| `ai_frequency_label` | string | Yes | HIGH / MEDIUM / LOW badge |
| `ai_call_count` | integer | Yes | "Mentioned in `<n>` calls" |
| `ai_date_range` | string | No | Duplicate of `period` — §8.6 |
| `ai_conversion_score` | integer | Yes | Rendered with a `%` suffix |
| `ai_mlr_response` | string | Yes | Response body, first paragraph |
| `ai_sku` | string | Yes | Appended in parentheses |
| `ai_supporting_materials` | string | Yes | Second paragraph — §8.2 |
| `analysis_badges` | array | Yes | DETECTED_BY_AI, NLP_ANALYSIS, AI_OPTIMIZED |

**`ai_conversion_score` is a bare integer** and renders with a `%` suffix. It
is not a fraction and not a percentage string.

**Score representation differs across all three tabs.** Territory
Prioritization returns a percentage *string*, New Writer ID a bare *decimal*,
this tab a bare *integer*. Never carry one tab's handling to another.

### 4.3 KPI block — `objection_handler`

Delivered with the shared application summary, which serves all three tabs.

```
objection_handler
    calls_analysed         integer   transcripts processed in the period
    objections_detected    integer   objection instances found across them
    recurring_patterns     integer   distinct objection types after grouping
    High_frequency         integer   of those, banded HIGH
```

**These narrow left to right**, but the second is not a subset of the first in
the usual sense — one call can raise several objections, so
`objections_detected` may exceed `calls_analysed`. The narrowing begins at
`recurring_patterns`.

`High_frequency` is capitalised inconsistently with its siblings. See §8.8.

---

## 5. FRONTEND ↔ BACKEND MAPPING

### 5.1 Objection card

| UI element | Payload field | Transform |
|---|---|---|
| Card heading | `objection_text` | Wrapped in quotation marks |
| Frequency badge | `ai_frequency_label` | Suffixed " FREQUENCY"; colour by value |
| "Mentioned in `<n>` calls" | `ai_call_count` | Prefixed / suffixed |
| Date range in parentheses | `period` | Direct |
| "Conversion score: `<n>`%" | `ai_conversion_score` | Suffixed "%" — no division |
| DETECTED BY AI badge | `analysis_badges` | Presence check |
| AI OPTIMIZED badge | `analysis_badges` | Presence check |
| Response paragraph 1 | `ai_mlr_response` | Wrapped in quotation marks |
| Response paragraph 2 | `ai_supporting_materials` | Direct — §8.2 |
| SKU in parentheses | `ai_sku` | Already embedded in paragraph 2 |
| Objection type chip | `objection_type` | Direct |
| Add to Next Call Prep | `objection_id` | Identifies which objection to attach |
| *(not rendered)* | `territory_id`, `hcp_segment`, `ai_date_range` | Available, unused |

### 5.2 Section header

| UI element | Source | Notes |
|---|---|---|
| "COMMON OBJECTIONS (`<range>`)" | `period` of the first card | **Not the union** — §8.7 |

### 5.3 KPI block

| KPI | Payload field |
|---|---|
| Calls analysed | `objection_handler.calls_analysed` |
| Objections detected | `objection_handler.objections_detected` |
| Recurring patterns | `objection_handler.recurring_patterns` |
| High frequency | `objection_handler.High_frequency` |

### 5.4 Mapping traps

**`ai_conversion_score` needs no conversion.** Bare integer, rendered with `%`.
Multiplying by 100 produces a four-digit figure.

**The response body renders twice.** `ai_mlr_response` and
`ai_supporting_materials` are separate fields that hold near-identical text,
and the card displays both. Quote one, never both.

**`ai_sku` is already inside `ai_supporting_materials`.** Rendering the SKU
field separately alongside that paragraph would show it twice.

**The section header range is not the reporting period.** It is one card's
`period`. Do not use it to describe the overall window.

**`period` and `ai_date_range` are the same value.** Use `period`.

---

## 6. GRAPHICAL FLOW

### 6.1 Objection pipeline

```
   Call transcripts and notes in the territory
                │
                ▼
   NLP extraction          ── what was raised
                │             → objection_text
                ▼
   Classification          ── which category
                │             → objection_type
                ▼
   Grouping                ── same objection across calls
                │             → recurring_patterns
                ▼
   Frequency count         ── how often
                │             → ai_call_count → ai_frequency_label
                ▼
   Response pairing        ── from the MLR-approved library
                │             → ai_mlr_response + ai_sku
                ▼
   Conversion scoring      ── historical effectiveness of that response
                │             → ai_conversion_score
                ▼
   Card list, ordered by descending frequency
```

### 6.2 Page lifecycle

```
   Rep opens Objection Handler
            │
            ▼
   Territory scope resolved from the authenticated session
            │
            ├──────────► KPI counts        calls_analysed
            │                              objections_detected
            │                              recurring_patterns
            │                              High_frequency
            │
            └──────────► Objection card list
                              ordered by descending frequency
                                        │
                                        ▼
                          [Add to Next Call Prep] pressed
                                        │
                                        ▼
                        objection + response attached to
                        the rep's next-call preparation
```

### 6.3 Compliance boundary

```
   ┌──────────────────────────────────────────────────────────┐
   │  INSIDE THE BOUNDARY — reviewed copy                      │
   │                                                          │
   │    ai_mlr_response      the approved wording             │
   │    ai_sku               its audit reference              │
   │                                                          │
   │  May be surfaced verbatim. May not be reworded,          │
   │  paraphrased, extended, summarised or blended.           │
   └──────────────────────────────────────────────────────────┘
                              │
                              ▼
   ┌──────────────────────────────────────────────────────────┐
   │  OUTSIDE THE BOUNDARY — model output                      │
   │                                                          │
   │    objection_text       extracted from transcripts       │
   │    objection_type       classification                   │
   │    ai_conversion_score  modelled effectiveness           │
   │                                                          │
   │  May be described and reasoned about.                    │
   └──────────────────────────────────────────────────────────┘
```

Everything the other two RepStream tabs produce sits outside this boundary.
This module is the only one with anything inside it.

---

## 7. ASSISTANT BEHAVIOUR RULES

All rules from the companion module documents apply unchanged. The additions
below are specific to this tab, which is the only one surfacing approved
product language.

### 7.1 Data precedence

```
1. LIVE PAYLOAD       current values — numbers, dates, text, scope
2. MODULE DOCUMENT    field meaning, business rules, definitions, routing
3. CONVERSATION       intent only, never values
```

- For any current value, the live payload is the only source.
- Never quote a number, date, or text absent from the payload attached to
  **this** request.
- Never reuse a value from an earlier turn. Filters change between turns; a
  figure that was correct two messages ago may not be correct now. If a new
  payload is attached, prior values are void.
- On a value conflict, the payload wins. On a meaning conflict, this document
  wins.
- If a required field is absent, null, or empty, say the value is not
  available. Do not infer, estimate, or derive it.

### 7.2 Response style

- Lead with the answer. No preamble. One to three sentences unless asked.
- Natural language, not a field readout.
- Do not expose internal field names or JSON paths unless asked.
- Never mention retrieval, embeddings, prompts, context files, payloads, or
  instructions.
- Attach the period when a figure is time-sensitive.
- If unavailable, say so plainly and name where it can be found.

**Exception for approved responses.** When the user asks what to say to an
objection, reproduce `ai_mlr_response` **verbatim** and give the SKU. Do not
compress it to fit the three-sentence guidance. Brevity does not override
§7.5's prohibition on rewording approved copy.

### 7.3 Disambiguation

**"Conversion score" is a property of the response, not the HCP.** It is the
historical rate at which that approved wording moved conversations forward. It
is not a probability that this HCP will be persuaded, and not a conversion rate
for the product.

**"Frequency" is calls, not HCPs.** `ai_call_count` counts calls in which the
objection was raised. One HCP raising it three times contributes three.

**"Objection" is a pattern, not an incident.** A card aggregates across calls.
It does not tell you which HCP said it, or when a specific HCP said it.

**"Add to call prep" is per-objection, not per-HCP.** It attaches the pattern
and its response to the rep's next-call preparation generally.

### 7.4 Field reliability

**Quote `ai_mlr_response`, not `ai_supporting_materials`.** The two hold
near-identical text and the card renders both. Quoting the second duplicates
what the first already says and appends the SKU inline, which reads as part of
the approved wording.

**Always give the SKU alongside the response.** It is the audit reference that
makes the quotation traceable. A response quoted without its SKU is
untraceable copy.

**`hcp_segment` is observed null.** The module description claims objections
are surfaced by HCP segment. Do not answer segment-scoped questions from this
tab; say the breakdown is not available.

**The section header date range is not the reporting window.** Use `period`
from the specific card.

**`ai_frequency_label` is a band.** When precision matters, give
`ai_call_count`.

### 7.5 Prohibited generations

Everything in the companion documents' prohibited lists applies. Reinforced
here, because this is the only tab holding approved copy:

- **Never reword, paraphrase, summarise, shorten, extend, or blend
  `ai_mlr_response`.** It is MLR-reviewed copy. Any alteration voids the review
  that makes it usable. Reproduce it verbatim or not at all.
- **Never compose a new response to an objection.** If no approved response
  exists for what the user describes, say so. Do not fill the gap.
- **Never combine two responses**, and never take a sentence from one and a
  sentence from another. Each SKU covers one approved block of wording.
- **Never state or imply a response is approved for an objection it is not
  paired with.**
- **No clinical, efficacy, safety, comparative, or dosing claims of your own.**
  Where such claims appear inside approved copy, they may be reproduced
  verbatim with the SKU — never restated in your own words.
- **No off-label content, under any framing**, including any use outside the
  approved indication implied by an objection the rep describes.
- **Never de-anonymise brand references.** Where a payload says "Product" or
  "Competitor A", use that exact label.
- **No medical advice**, and no opinion on what a prescriber should prescribe.
- **No presenting conversion score as certainty.** Say "this response has
  historically converted at", never "this will work".
- **Never assert the response was approved for a specific HCP.** Approval is of
  the wording, not of its use with any individual.

### 7.6 Behavioural protocols

| Situation | Response |
|---|---|
| User asks what to say to a listed objection | Reproduce `ai_mlr_response` verbatim, give the SKU, name the objection type |
| User describes an objection not in the list | Say no approved response is listed for it. Do not compose one. Suggest the closest listed objection if one genuinely matches |
| User asks you to shorten or reword a response | Decline and explain the wording is MLR-reviewed. Offer the verbatim text |
| User asks which response works best | Give conversion scores with the §7.3 caveat that it is a property of the response |
| User asks who raised an objection | Not available — cards are patterns, not incidents |
| User asks for a segment breakdown | Not available — §7.4 |
| Answer is on another tab | Name the tab and what it holds |
| Uncertain | Say so |

### 7.7 Intent routing

| User intent | Source |
|---|---|
| what do I say when they say X | Matching card's `ai_mlr_response` + `ai_sku` |
| what are the top objections | Card list, descending frequency |
| how often does this come up | `ai_call_count`, not the band |
| which response works best | `ai_conversion_score`, with §7.3 caveat |
| what type of objection is this | `objection_type` |
| how many calls were analysed | `calls_analysed` |
| how many objections were found | `objections_detected` |
| what is the SKU for this | `ai_sku` |
| who said this / which HCP | Not available — §7.6 |
| by segment | Not available — §7.4 |
| who should I visit | Territory Prioritization |
| who should I start | New Writer ID |
| what is the competitor doing | Competitive Intel — Action Center |
| formulary / tier / prior auth | Payer Access — Action Center |
| alerts / what changed | Active Alerts — Action Center |
| is this HCP going cold | HCP Awareness — Action Center |

### 7.8 What this module can and cannot answer

**Available:** any KPI value and its meaning; for any listed objection — the
verbatim text, type, call count, frequency band, period, conversion score,
approved response and SKU; what any panel, badge or button does; how objections
are surfaced and banded.

**Not available:** which HCP raised an objection; when a specific HCP raised
it; a breakdown by segment; a response for an objection not in the list; any
reworded version of an approved response; content belonging to sibling modules.

---

## 8. DATA QUALITY REGISTER

Ordered by severity.

### 8.1 HIGH — duplicate records across two source object types

Objection records duplicate across two source-system object prefixes,
identical in every field except `objection_id`. In one captured territory pair,
five of fifteen records were duplicates — one extra copy for each of five
distinct objections.

Because the IDs genuinely differ, no uniqueness constraint catches them. They
load cleanly and then double-count in any aggregation by objection type.

**Actions**
- Deduplicate on `(objection_type, territory_id, ai_sku)` at the API layer.
- Identify why two source object types feed the same pipeline and union them
  without dedup at source.
- Verify `objections_detected` and `recurring_patterns` are not inflated by
  the duplicates.

### 8.2 HIGH — the response body renders twice

Each card displays the approved response as two consecutive paragraphs:

```
paragraph 1   ai_mlr_response            quoted, no SKU
paragraph 2   ai_supporting_materials    unquoted, SKU appended
```

The two are identical except for the trailing `(SKU: …)`. The rep reads the
same wording twice in a row, inside a panel labelled MLR-APPROVED — which makes
it look deliberate rather than a rendering fault.

`ai_supporting_materials` is not supporting materials. It is
`ai_mlr_response` with the SKU concatenated. The field name describes something
the field does not contain.

**Actions**
- Render `ai_mlr_response` once, with the SKU displayed as a separate labelled
  element.
- Either remove `ai_supporting_materials` or repopulate it with actual
  materials — the Active Alerts module has a working precedent for a
  materials list.

### 8.3 HIGH — MLR-APPROVED and AI OPTIMIZED on the same panel

The response panel is titled **RECOMMENDED RESPONSE (MLR-APPROVED)** and
carries an **AI OPTIMIZED** badge.

The intended reading is that the model *selected* the best-converting approved
response. The available reading is that the model *modified* approved copy —
which would void the approval, since MLR review attaches to specific wording.

A rep cannot tell which is meant. Neither can an auditor.

**Actions**
- Relabel to something unambiguous — "AI SELECTED" or "BEST CONVERTING" —
  if selection is what happens.
- If any generative step touches the response text after review, that is a
  compliance finding, not a labelling one. Confirm before relabelling.
- Document the relationship between the response library and the review
  process, so the SKU's meaning is auditable.

### 8.4 MEDIUM — call counts are not territory-scoped

`ai_call_count` has been observed identical for the same objection across
different territories. If the figure is meant to be "calls in this territory",
it is currently a global count repeated per territory row, and each territory
appears to have independently logged the same number of calls.

**Action.** Confirm the intended scope and either scope the count to the
territory or relabel it.

### 8.5 MEDIUM — segmentation claimed but not delivered

The module description states objections are surfaced "by HCP segment".
`hcp_segment` is observed null on every record, and no segment control appears
on the page.

**Actions**
- Populate `hcp_segment`, or remove the claim from the description.
- Until then, treat segment-scoped questions as unanswerable on this tab.

### 8.6 MEDIUM — `ai_date_range` duplicates `period`

The two fields hold byte-identical values on every observed record. The same
string is stored twice per row and only one is rendered.

**Action.** Remove one, or give them distinct meanings — for example `period`
as the reporting window and `ai_date_range` as the actual span of observed
mentions, which would be genuinely useful.

### 8.7 MEDIUM — section header range understates the window

The section is headed `COMMON OBJECTIONS (<range>)`, and the range shown
matches the **first card only**. Cards below it carry earlier start dates, so
the header excludes mentions it is presenting.

**Action.** Compute the header as the union across displayed cards, or label it
as the reporting period rather than a data range.

### 8.8 LOW — field naming inconsistency in the KPI block

```
calls_analysed         lower snake
objections_detected    lower snake
recurring_patterns     lower snake
High_frequency         capitalised
```

One key in four breaks the convention, against a payload that is otherwise
uniformly lower snake case.

**Action.** Normalise before external consumers bind. Fixing it later is a
breaking change.

### 8.9 LOW — date ranges lack a year

`period` values are of the form `Mon DD – Mon DD` with no year. They cannot be
parsed into dates without assuming one, and a range crossing a year boundary is
ambiguous.

**Action.** Emit ISO dates, or include the year.

### 8.10 Compliance register

| # | Issue | Severity | Blocks release |
|---|---|---|---|
| 1 | MLR-APPROVED and AI OPTIMIZED on the same panel (§8.3) | High | **Review** |
| 2 | Approved response rendered twice, one copy with SKU inline (§8.2) | High | Review |
| 3 | Duplicate objection records inflating counts (§8.1) | High | No |
| 4 | Call counts not territory-scoped (§8.4) | Medium | No |
| 5 | Segmentation claimed but not delivered (§8.5) | Medium | No |

**Item 1 is the one to resolve first**, and it is a process question before it
is an engineering one. If a generative step modifies reviewed copy, the SKU no
longer identifies what the rep is reading, and the audit trail this module
exists to provide does not hold.

Open for the delivery team and client compliance function:

- Confirmation that no generative step alters response text after MLR review.
- The relationship between the SKU, the response library and the review record.
- Whether Add to Next Call Prep is captured in the audit log.

### 8.11 What works correctly

Recorded so the failures above are not read as systemic.

- **Frequency banding is correct** on every observed card. Counts of 12 and 18
  band HIGH, a count of 7 bands MEDIUM, consistent with the documented
  thresholds.
- **`ai_conversion_score` is genuinely continuous** — every observed value
  distinct, unlike the heavily quantised priority score on Territory
  Prioritization.
- **Card order matches descending frequency** in every observed case.
- **Every response carries a SKU.** The audit reference is present throughout,
  which is what makes §8.3 a labelling question rather than a missing-trail
  one.
- **The objection text is verbatim from transcripts**, not paraphrased — which
  is what makes the patterns recognisable to a rep who was in the call.

---

## 9. OPEN ITEMS

### 9.1 Unresolved questions

1. Does any generative step modify response text after MLR review? (§8.3)
2. What does `ai_supporting_materials` hold in the target design? (§8.2)
3. Is `ai_call_count` intended to be territory-scoped? (§8.4)
4. Why do two source object types feed the same pipeline? (§8.1)
5. Is `hcp_segment` planned, or should the description change? (§8.5)
6. Is `High_frequency` corrected before external consumers bind? (§8.8)
7. Is Add to Next Call Prep captured in the audit log, and where does the
   prepared list surface?
8. Can a rep mark a response as used or ineffective, feeding conversion
   scoring back?

### 9.2 Unconfirmed display behaviour

The `LOW FREQUENCY` band is documented but was not observed on screen. Confirm
its badge colour and whether low-frequency objections are displayed at all or
filtered out of the card list.

---

## 10. VOCABULARY

| Term | Meaning |
|---|---|
| **Objection** | A concern an HCP raised during a call, extracted from the transcript |
| **Objection type** | The classification bucket — efficacy, cost, dosing, competitor preference, safety |
| **Pattern** | A recurring objection aggregated across calls, not a single incident |
| **Frequency band** | HIGH / MEDIUM / LOW, derived from call count |
| **Conversion score** | Historical rate at which the paired response moved conversations forward. A property of the response |
| **MLR** | Medical, Legal and Regulatory review. Approved content only |
| **MLR-approved** | Wording reviewed and cleared for use with HCPs. Alteration voids it |
| **SKU** | The audit reference identifying a specific approved response |
| **Call prep** | The rep's preparation set for an upcoming visit |
| **Transcript** | Recorded or written record of a call, the input to this module |
| **NLP** | Natural language processing — used for extraction and classification |
| **HCP** | Healthcare professional — prescriber or clinical staff |
| **Rep** | Field sales representative. The primary user |
| **Segment** | CRM-assigned HCP classification |
| **PERT / EPI** | Pancreatic enzyme replacement therapy / exocrine pancreatic insufficiency |
| **In-class** | Products treating the same indication, including competitors |

**Brand references are generalised by design.** Payloads use generic labels in
place of confidential product and competitor names. That generalisation is a
governance control, not a data defect — reproduce the label exactly as given,
including inside approved response text.

---

**If any part of this document is used as machine-readable context, exclude
sections 8 and 9.** They contain concrete figures and defect evidence,
including the exact rendering behaviour §7.4 tells the assistant to work
around.


---

# PART 4 — ACTIVE ALERTS

**Application:** Action Center — Launch & Market Defense · **Platform module:** Module 4 of 7

## 1. MODULE

| | |
|---|---|
| **Module name** | Active Alerts |
| **Section heading** | Action Center — Launch & Market Defense |
| **Tagline, as displayed** | Real-time competitive intelligence and HCP awareness monitoring |
| **Parent application** | Action Center |
| **Parent platform** | Veeva AI Insight 360 (UI shows "Insights 360™ V2") |
| **Position** | Tab 1 of 4 in Action Center; Module 4 of 7 on the platform |
| **Primary user** | Field sales representative |
| **Secondary user** | Sales manager (consolidated multi-territory view) |
| **Therapy context** | Pancreatic enzyme replacement therapy (PERT / EPI) |
| **Access model** | Role-based, derived from the authenticated session |
| **Write capability** | None on this tab. "Deploy to Field" and "Dismiss" are recorded actions, not record edits — see §7.5 |
| **Refresh cadence** | Batch detection; surfaced as `last_refresh` on the shared data-reference panel |

**The question this module answers:** *what changed in my territory since I last
looked, and what do I do about it right now?*

It is the threat feed for the whole platform. Three independent detection
methods run against three different data sources and land in three separate
lists on one page — a competitor taking share, a payer downgrading the
product's formulary tier, and an HCP's awareness quietly declining. Each
finding is enriched with generated prose (a title, a description, and for two
of the three streams an MLR-approved counter-script) and a severity so the rep
knows what to act on first.

**The module's own description, as given in the module guide:**

> Active Alerts is the main intelligence feed of the Action Center. It uses
> machine learning to automatically detect three types of threats in the sales
> rep's territory — competitive threats (competitor gaining Rx share), payer
> access changes (formulary tier downgrades), and HCP awareness decline
> (doctors losing awareness of the product). Each alert is enriched by GPT-4o
> with a description, counter-script, and recommended actions.

**The platform detects and drafts; the representative decides and acts.**
Generated content — titles, descriptions, counter-scripts — is decision
support for review by a qualified user, never an autonomous decision and
never a clinical recommendation. See §7.5 for what may never be repeated
verbatim to an HCP.

---

## 2. MODULE DETAILS

### 2.1 Position in the platform

```
Veeva AI Insight 360 — 7 modules
│
├── My Insights (RepStream)
│   ├── Territory Prioritization      existing writers, ranked by opportunity
│   ├── New Writer ID                 non-writers, conversion candidates
│   └── Objection Handler             what to say when pushed back on
│
└── Action Center — launch and market defence
    ├── Active Alerts               ← THIS MODULE — threat feed, three streams
    ├── HCP Awareness                 per-HCP awareness scores and trend
    ├── Competitive Intel             competitor signals and counter-strategy
    └── Payer Access                  formulary tiers and access risk
```

Value chain the platform implements:

```
Data → Intelligence → Insight → Recommendation → Action
```

This module contributes the **Intelligence** stage — it is the detector that
the other three Action Center tabs each go on to specialise. HCP Awareness,
Competitive Intel, and Payer Access are the drill-down destinations for the
three alert types raised here.

### 2.2 Sibling modules — routing reference

| Destination | Location | Holds | Route when user asks |
|---|---|---|---|
| **Territory Prioritization** | RepStream tab | Existing writers ranked by opportunity, with score reason | who should I visit, my ranked list, priority tier, Rx trend |
| **New Writer ID** | RepStream tab | Non-writers, peer-match score, warm-introduction path, drafted email | who should I start, non-writers, warm intro, draft an email |
| **Objection Handler** | RepStream tab | Objections from call transcripts, ranked by frequency, MLR-approved responses | what do I say when, they told me, pushback, objection |
| **HCP Awareness** | Action Center tab | Per-HCP awareness score across four weekly periods, trend, risk score, recommended re-engagement action | is this specific HCP going cold, awareness trend, who needs a call |
| **Competitive Intel** | Action Center tab | Competitor signals — rep-visit surges, share gains, messaging campaigns — with executive summary and talking points | what is the competition doing, threat level, talking points, counter strategy |
| **Payer Access** | Action Center tab | Full formulary status for every payer, not only the ones that changed; abandonment risk, PA bridge note | formulary status of a payer not in an alert, coverage, prior auth in general |

**This module is the summary; the other three Action Center tabs are the
detail.** An Active Alerts card gives severity, headline numbers, and a
counter-script. If the user wants the full trend line for one HCP, the full
competitor threat writeup, or the full payer list including payers that have
*not* changed, route to the owning tab — this module's payload does not carry
that depth.

### 2.3 Three detection streams

Each stream is a different model reading a different source, landing in a
different array of the same response.

| Stream | Array | Trigger | Technique | Source table |
|---|---|---|---|---|
| **Competitive** | `competitive_alerts` | Sudden, anomalous competitor Rx activity | IsolationForest anomaly detection | (rep call / Rx activity, per guide) |
| **Payer** | `payer_alerts` | A payer's formulary tier changes | Direct read, no ML model | Payer formulary records |
| **HCP awareness** | `hcp_awareness_alerts` | Gradual decline in detailing frequency / awareness | Linear regression on drift | (detailing log, per guide) |

All three then pass through GPT-4o, which writes the `title`, `description`,
and — for competitive and payer alerts — the counter-script or action note.
**Payer alerts draw on the same underlying payer formulary data that the
sibling Payer Access tab reads in full** — this tab shows only the payers with
a detected change; Payer Access shows all of them, changed or not.

**Detection method is not the same field as severity.** `ai_detection_method`
records *how* the alert was found (`ANOMALY_DETECTION`, `AUTO_DETECTED`,
`ML_MODEL`); `ai_severity` records *how urgent* it is (`CRITICAL`, `HIGH`,
`MEDIUM`). Do not conflate the two when answering "how was this caught."

### 2.4 Access scope

Visibility follows the same organisational hierarchy as the rest of the
platform. Users see only what their authenticated identity and organisational
position permit.

```
Manager  →  User (representative)  →  Territory  →  Alert
```

**Territory scope derives from the authenticated session, not free choice.**
Every alert, every KPI tile, and the banner message all correspond to the
filter currently in force. When the USERS or TERRITORY NAME filter changes,
the alert lists change with it.

### 2.5 Two API responses feed one page

Like Territory Prioritization, this tab is built from two separate round
trips that must both be current for the page to be internally consistent.

| Response | Feeds |
|---|---|
| **Summary** | 5 KPI tiles, yellow banner text, filter dropdowns |
| **Alert list** | The three alert-card sections underneath |

**They are not guaranteed to reconcile.** The summary's counts are a rollup
computed separately from the list; §8.1 records a case where they visibly
diverge. Never derive one from the other — quote whichever the user is asking
about, from its own response.

### 2.6 A field means two different things depending on alert type

`ai_territory_reach` is reused across alert types with an entirely different
unit and meaning in each:

```
competitive_alerts   ai_territory_reach = "3/12"      sub-territories affected, as a fraction
payer_alerts          ai_territory_reach = "89000"      covered lives, as a raw integer
hcp_awareness_alerts   — field does not appear on this card type at all
```

**Never assume the shape.** Before quoting `ai_territory_reach`, check which
array the alert came from. Reading a payer alert's `"89000"` as "89 thousand
out of some total" or a competitive alert's `"3/12"` as covered lives are both
wrong in the same way — the field is overloaded, not consistent.

### 2.7 Severity and risk vocabulary

Two related-looking fields are not the same thing:

| Field | Meaning | Observed values |
|---|---|---|
| `ai_severity` | How urgently the *alert itself* needs review | `CRITICAL`, `HIGH`, `MEDIUM` — always upper case |
| `ai_rx_risk` | The *commercial* risk level the alert describes | `High` (competitive, title case) / `HIGH` (payer, upper case) — see §8.7 |

A CRITICAL-severity alert and a HIGH `ai_rx_risk` value can co-occur on the
same card; they answer different questions ("how urgent is this notification"
versus "how bad is the underlying risk") and should not be merged into one
answer.

---

## 3. FRONTEND — OVERVIEW AND KEYS

### 3.1 Application shell

```
┌────────────────────────────────────────────────────────────────────────────┐
│ ☰   ▮▮ Insights 360™  [V2]   ⚡SLIPSTREAM              ⊞  </>              │
├──────────────────┬─────────────────────────────────────────────────────────┤
│ ▫ Insights 360 V1│  Action Center - Launch & Market Defense                 │
│ ▫ My Insights    │  [POWERED BY DATAstream AI]                              │
│ ▪ Action Center  │  Real-time competitive intelligence and HCP awareness    │
│                  │  monitoring                                              │
│ ⏻ Logout         │  USERS [All ▾]   TERRITORY NAME [All ▾]   [Apply]        │
└──────────────────┴─────────────────────────────────────────────────────────┘
```

Same shell as My Insights (§3.1 of the Territory Prioritization document) with
**Action Center** active in the left nav instead of My Insights. The assistant
launcher (circular chat button, fixed bottom-right) is present here too and is
governed by §7 of this document while the user is on this tab.

### 3.2 Data reference panel (upper left, display only)

| Line | Source |
|---|---|
| `Q3 2026 (Jul - Sep)` | `period` |
| `Last updated: Aug 25, 2026` | `last_refresh` |

Shared with the rest of the platform — the same period and refresh date apply
across every tab in a given session.

### 3.3 Alert banner

A yellow banner sits directly under the data-reference panel whenever the
summary response carries one:

```
🔔  New alerts require action                              [View Alerts]
    Competitive script shifts detected in your territory
```

Sourced entirely from `ai_banner_message` (§4.2). **Do not construct this
message from the individual alert list** — treat it as a single pre-composed
string, and if it is absent or empty, say no banner is currently showing
rather than inventing one from the alert counts.

### 3.4 KPI summary tiles — five, left to right

| # | Tile label | Badge / subtitle | Source field |
|---|---|---|---|
| 1 | Critical alerts | `AI DETECTED` | `ai_critical_count` |
| 2 | High priority | `AI DETECTED` | `ai_high_count` |
| 3 | Medium priority | "No change" (plain text, **no badge**) | `ai_medium_count` |
| 4 | HCP drift detected | `ML MODEL` | `ai_hcp_drift_detected` |
| 5 | Early detection | "vs 6-8 traditional" (plain text, **no badge**) | `ai_early_detection_weeks`, suffixed "weeks" |

**Only tiles 1, 2, and 4 carry a technique badge.** Tile 3 (Medium priority)
shows the static subtitle "No change" regardless of the actual value, and
tile 5 shows a fixed comparison string. This asymmetry is real, not a
rendering gap — see §8.8.

**These 5 tiles are shared across all four Action Center tabs** and appear
identically regardless of which of the four is active — they are not
recomputed per tab.

### 3.5 Tab bar

```
[ Active Alerts ]  HCP Awareness   Competitive Intel   Payer Access
```

Active Alerts is the leftmost, default tab. Switching tabs does not reissue
the summary call (§3.4's tiles persist) but does issue a new call for that
tab's own data (§2.2).

### 3.6 Alert card anatomy — competitive and HCP-drift alerts share a shape

```
┌────────────────────────────────────────────────────────────────────────┐
│ ┃ [CRITICAL] [ANOMALY DETECTION]        Detected: 2026-08-05 08:15      │
│ ┃                                                                        │
│ ┃ <generated title>                                                     │
│ ┃ <generated description, 2-3 sentences>                                │
│ ┃                                                                        │
│ ┃ ┌── IMPACT ANALYSIS ───────────────┐ ┌── RECOMMENDED COUNTER-SCRIPT ─┐│
│ ┃ │ Affected HCPs   Territory Reach  │ │ (MLR-APPROVED)                ││
│ ┃ │ Risk                             │ │ <generated counter-script>    ││
│ ┃ │ TARGET ICD-10 CODES AFFECTED     │ │ Supporting materials: …        ││
│ ┃ │ [code  label (n HCPs)] × n       │ │                                 ││
│ ┃ │ Prescribing drift detected: …    │ │                                 ││
│ ┃ └───────────────────────────────────┘ └─────────────────────────────┘│
│ ┃ [Deploy to Field]  [View Affected HCPs]  [Dismiss]                    │
└────────────────────────────────────────────────────────────────────────┘
```

HCP-awareness ("drift") alerts use a shorter version of the same shell: badge
row, title, description, and a two-button footer — **no** impact-analysis
panel, no counter-script panel, no ICD-10 chips.

```
┌────────────────────────────────────────────────────────────────────────┐
│ ┃ [CRITICAL] [ML MODEL]                  Detected: 2026-08-06 09:45     │
│ ┃                                                                        │
│ ┃ <generated title>                                                     │
│ ┃ <generated description>                                               │
│ ┃                                                                        │
│ ┃ [Schedule Calls]  [Review Later]                                      │
└────────────────────────────────────────────────────────────────────────┘
```

### 3.7 Alert card anatomy — payer alerts

```
┌────────────────────────────────────────────────────────────────────────┐
│ ┃ [HIGH PRIORITY] [AUTO-DETECTED]        Detected: 2026-08-04            │
│ ┃                                                                        │
│ ┃ Payer formulary update — <PAYER NAME> Tier change                     │
│ ┃ <PAYER NAME> moved our product from <from tier> to <to tier>          │
│ ┃ effective <date>. Affects approximately <n> covered lives.            │
│ ┃                                                                        │
│ ┃ ┌── IMPACT ANALYSIS ────────────────────────────────────────────────┐│
│ ┃ │ Affected HCPs   Territory Reach   Rx Risk                          ││
│ ┃ │ Action needed: <drift-note text>                                    ││
│ ┃ └──────────────────────────────────────────────────────────────────┘│
│ ┃ [View HCP List]  [Access Resources]  [Acknowledge]                    │
└────────────────────────────────────────────────────────────────────────┘
```

#### Severity chip label differs by stream

| Stream | Chip text pattern |
|---|---|
| Competitive / HCP awareness | `CRITICAL` / `HIGH PRIORITY` / `MEDIUM PRIORITY` — bare severity word for CRITICAL, "PRIORITY" suffix otherwise |
| Payer | `HIGH PRIORITY` observed; chip always carries the "PRIORITY" suffix regardless of severity word |

#### Detection-method chip text is not the raw field value

| `ai_detection_method` (payload) | Chip text (screen) |
|---|---|
| `ANOMALY_DETECTION` | ANOMALY DETECTION |
| `AUTO_DETECTED` | AUTO-DETECTED (hyphenated on screen, underscore in payload) |
| `ML_MODEL` | ML MODEL |

---

## 4. BACKEND — KEY DETAILS

### 4.1 Data delivery

**The summary and the alert list are two separate calls** (§2.5). Neither
alert-card content nor the KPI tiles are recomputed client-side — each is
whatever its own response carried at load time.

**Territory scope is derived from the authenticated session**, not chosen
freely, exactly as in Territory Prioritization §4.1. Every alert corresponds
to the filter currently in force.

**Alert numbering restarts per stream.** Keys are `alert_1`, `alert_2`, …
independently inside `competitive_alerts`, `payer_alerts`, and
`hcp_awareness_alerts` — `alert_1` is not a unique identifier across streams,
only `alert_id` is.

### 4.2 Summary payload — field inventory

| Field | Type | Rendered | Notes |
|---|---|---|---|
| `ai_critical_count` | integer | Yes | Tile 1 |
| `ai_high_count` | integer | Yes | Tile 2 |
| `ai_medium_count` | integer | Yes | Tile 3, no badge |
| `ai_hcp_drift_detected` | integer | Yes | Tile 4 — see §8.4 for how it is actually composed |
| `ai_early_detection_weeks` | number | Yes | Tile 5, suffixed "weeks" |
| `ai_banner_message` | string | Yes | Banner body text |
| `filters` | object | Yes | Same manager → employee → territory hierarchy as Territory Prioritization §4.3 |

### 4.3 Competitive alert — field inventory (13 keys + 2 nested arrays)

| Field | Type | Rendered | Notes |
|---|---|---|---|
| `alert_id` | string | No | e.g. `AL-001` — never shown on screen, see §8.6 |
| `alert_type` | string | No | Always `"competitive"` |
| `ai_severity` | string | Yes | Chip |
| `ai_detection_method` | string | Yes | Chip, re-worded — §3.7 |
| `detected_at` | string | Yes | `YYYY-MM-DD HH:MM` |
| `title` | string | Yes | Generated. **Regenerates per capture — §8.5** |
| `description` | string | Yes | Generated. **Regenerates per capture — §8.5** |
| `ai_affected_hcp_count` | integer | Yes | Impact analysis panel |
| `ai_territory_reach` | string | Yes | `"n/12"` fraction — §2.6 |
| `ai_rx_risk` | string | Yes | Title case in this stream — §8.7 |
| `ai_icd10_codes_affected` | array of objects | Yes | `{code, label, hcp_count}` — chips. **Reconciles exactly with screen — see §8.9** |
| `ai_prescribing_drift_note` | string | Yes | "Prescribing drift detected:" line |
| `ai_counter_script` | string | Yes | MLR-approved panel body. **Regenerates per capture — §8.5** |
| `ai_supporting_materials` | array of objects | Yes | `{title, sku}` — `sku` is `null` on every observed record and is rendered literally as text — §8.10 |
| `recommended_actions` | array of strings | Yes, as buttons | Reliable for this stream — §8.11 |
| `view_affected_hcp` | array of objects | On click | 6 keys per HCP — §4.6 |
| `deploy_to_field` | array of objects | On click | Rep + territory + affected-HCP list — §4.7. Frequently empty |

### 4.4 Payer alert — field inventory (documented 10 keys; actual payload carries more)

| Field | Type | Rendered | Notes |
|---|---|---|---|
| `alert_id` | string | No | e.g. `PAYER-19267` |
| `alert_type` | string | No | Always `"payer"` |
| `ai_severity` | string | Yes | Chip |
| `ai_detection_method` | string | Yes | Observed only as `AUTO_DETECTED` |
| `detected_at` | string | Yes | `YYYY-MM-DD` (no time component, unlike the other two streams) |
| `title` | string | Yes | Generated, **byte-identical to screen — §8.5** |
| `description` | string | Yes | Generated, **byte-identical to screen — §8.5** |
| `ai_affected_hcp_count` | integer | Yes | Impact analysis panel |
| `ai_territory_reach` | string | Yes | **Covered lives, not a fraction — §2.6** |
| `ai_rx_risk` | string | Yes | Upper case in this stream — §8.7 |
| `ai_prescribing_drift_note` | string | Yes | Rendered as "Action needed:" — **undocumented in the module guide's 10-key table; duplicated into `recommended_actions` — §8.2** |
| `recommended_actions` | array of strings | **No — buttons are hardcoded** | Holds a single string, a duplicate of `ai_prescribing_drift_note` — §8.2 |
| `view_hcp_list` | array of objects | On click | `{name}` only — no specialty, segment, or location, unlike `view_affected_hcp` |
| `resources` | array of objects | On click | `{title, url}` — **identical 4-item list on every payer alert observed — §8.3** |
| `tier_change` | object | Implied in description | `{from, to}` |

### 4.5 HCP-awareness alert — field inventory (6 keys, no HCP-level detail)

| Field | Type | Rendered | Notes |
|---|---|---|---|
| `alert_id` | string | No | e.g. `AL-003` |
| `alert_type` | string | No | Always `"hcp_awareness"` |
| `ai_severity` | string | Yes | Chip |
| `ai_detection_method` | string | Yes | Observed only as `ML_MODEL` |
| `detected_at` | string | Yes | `YYYY-MM-DD HH:MM` |
| `title` | string | Yes | Generated — §8.5 |
| `description` | string | Yes | Generated — carries the affected-HCP count and specialties **in prose only, with no structured field behind it — §8.4, §8.12** |
| `recommended_actions` | array of strings | Yes, as buttons | `["Schedule Calls", "Review Later"]` observed |

**This card type has no `ai_affected_hcp_count`, no `view_affected_hcp`, no
ICD-10 codes, and no counter-script.** Whatever the description says about how
many HCPs or which cities are involved is the only place that information
exists in this payload — treat it as prose, not structured fact (§7.4).

### 4.6 `view_affected_hcp` — 6 keys per HCP (competitive alerts only)

| Key | Notes |
|---|---|
| `hcp_id` | Join key |
| `name` | Trailing whitespace present in source, same as Territory Prioritization |
| `specialty` | |
| `segment` | CRM classification — same field, same caveats as §2.5 of the Territory document |
| `city` | |
| `state` | |

### 4.7 `deploy_to_field` — competitive alerts only, frequently empty

| Key | Notes |
|---|---|
| `rep_name` | |
| `rep_email` | **Observed mismatched against `rep_name` on the one populated record captured — §8.1** |
| `territory_id` | |
| `affected_hcps` | Array of name strings. Same set as `view_affected_hcp`, order not guaranteed to match |

Of the four competitive alerts observed, only one carried a populated
`deploy_to_field` array; the other three carried `[]`. Do not assume this
block is always present.

---

## 5. FRONTEND ↔ BACKEND MAPPING

### 5.1 KPI tiles

| UI tile | Payload field | Source | Transform |
|---|---|---|---|
| Critical alerts | `ai_critical_count` | Summary | Direct |
| High priority | `ai_high_count` | Summary | Direct |
| Medium priority | `ai_medium_count` | Summary | Direct |
| HCP drift detected | `ai_hcp_drift_detected` | Summary | Direct |
| Early detection | `ai_early_detection_weeks` | Summary | Suffixed "weeks" |
| Banner body | `ai_banner_message` | Summary | Direct |

### 5.2 Competitive / HCP-drift alert card

| UI element | Payload field | Transform |
|---|---|---|
| Severity chip | `ai_severity` | + " PRIORITY" unless CRITICAL |
| Detection chip | `ai_detection_method` | Underscore → space/hyphen re-rendering, §3.7 |
| Detected timestamp | `detected_at` | Direct |
| Headline | `title` | Direct, but not stable across loads — §8.5 |
| Body copy | `description` | Direct, but not stable across loads — §8.5 |
| Affected HCPs (impact panel) | `ai_affected_hcp_count` | Direct — competitive only |
| Territory Reach | `ai_territory_reach` | Direct — competitive only, fraction form |
| Risk | `ai_rx_risk` | Direct — competitive only |
| ICD-10 chips | `ai_icd10_codes_affected[]` | `code`, `label`, `(n HCPs)` |
| "Prescribing drift detected" line | `ai_prescribing_drift_note` | Direct — competitive only |
| Counter-script panel | `ai_counter_script` | Direct — competitive only, not stable across loads |
| Supporting materials line | `ai_supporting_materials[]` | `title (SKU: <sku or the literal word "null">)` |
| Action buttons | `recommended_actions[]` | Direct list → buttons |
| View Affected HCPs | `view_affected_hcp[]` | Opens on click |
| Deploy to Field | `deploy_to_field[]` | Opens on click; disabled or no-op when empty |

### 5.3 Payer alert card

| UI element | Payload field | Transform |
|---|---|---|
| Severity chip | `ai_severity` | Always renders with "PRIORITY" suffix |
| Detection chip | `ai_detection_method` | `AUTO_DETECTED` → "AUTO-DETECTED" |
| Detected date | `detected_at` | Direct, date only |
| Headline | `title` | Direct, **byte-identical to payload — §8.5** |
| Body copy | `description` | Direct, **byte-identical to payload — §8.5** |
| Affected HCPs | `ai_affected_hcp_count` | Direct |
| Territory Reach | `ai_territory_reach` | Direct — **covered lives here, not a fraction** |
| Rx Risk | `ai_rx_risk` | Direct, upper case |
| "Action needed" line | `ai_prescribing_drift_note` | Direct, **byte-identical to payload** |
| View HCP List / Access Resources / Acknowledge buttons | **Not sourced from `recommended_actions`** | Hardcoded per card type — §8.2 |

### 5.4 HCP-awareness alert card

| UI element | Payload field | Transform |
|---|---|---|
| Severity chip | `ai_severity` | + " PRIORITY" unless CRITICAL |
| Detection chip | `ai_detection_method` | `ML_MODEL` → "ML MODEL" |
| Detected timestamp | `detected_at` | Direct |
| Headline | `title` | Direct, not stable across loads — §8.5 |
| Body copy | `description` | Direct, not stable across loads — §8.5, and see §8.12 for geography |
| Schedule Calls / Review Later buttons | `recommended_actions[]` | Direct |

### 5.5 Mapping notes and traps

**Only one alert type keeps its generated text stable between the screen and
the payload.** Payer alerts are byte-identical; competitive and HCP-awareness
alerts are close paraphrases, not exact matches, between any two captures of
the "same" underlying event. See §8.5 for the evidence and §7.3 for how to
talk about this with a user.

**`ai_territory_reach` changes meaning by alert type** — §2.6. Never carry a
unit assumption from one stream to another.

**`recommended_actions` is reliable for two of three streams and actively
misleading for the third.** For competitive and HCP-awareness alerts it is the
literal button label list. For payer alerts it duplicates
`ai_prescribing_drift_note` and the real buttons are hardcoded — §8.2. Do not
tell a user what buttons a payer alert "should" have based on this field.

**`alert_id` never appears on screen, in any stream.** The only way to
correlate a rendered card with its payload record is the combination of
`detected_at`, the affected-HCP count, and the location named in the title —
and per §8.5 that combination is the most that can be relied on, because the
wording itself is not stable.

---

## 6. GRAPHICAL FLOW

### 6.1 Page lifecycle

```
   Rep opens Active Alerts (Action Center, default tab)
                │
                ▼
   Territory scope resolved from the authenticated session
                │
       ┌────────┴────────┐
       ▼                 ▼
  Summary response   Alert-list response
       │                 │
       ▼                 ▼
  ┌─────────────┐   ┌──────────────────────────────┐
  │ 5 KPI tiles │   │ 3 sections, independently     │
  │ + banner    │   │ numbered: competitive, payer, │
  │ + filters   │   │ hcp_awareness                 │
  └─────────────┘   └──────────────────────────────┘
                            │
                ┌───────────┼────────────────┐
                ▼           ▼                ▼
      [View Affected HCPs] [View HCP List] [Schedule Calls]
      [Deploy to Field]    [Access Resources]
                │           │
                ▼           ▼
       nested arrays already in the alert-list response
       (no further round trip for these two actions)
       │
       ▼
   Rep changes USERS or TERRITORY NAME
                │
                ▼
   Presses Apply ──► both responses refetch with the new scope
```

### 6.2 Detection pipeline — three independent paths into one page

```
   COMPETITIVE                 PAYER                    HCP AWARENESS
   Rx / call activity          Payer formulary data       detailing log
        │                           │                          │
        ▼                           ▼                          ▼
   IsolationForest              Direct read                Linear regression
   anomaly detection            (tier vs prior tier)       on drift slope
        │                           │                          │
        ▼                           ▼                          ▼
   GPT-4o writes title,        GPT-4o writes title,       GPT-4o writes title,
   description, counter-       description, action        description only
   script, materials list      note                        (no counter-script)
        │                           │                          │
        ▼                           ▼                          ▼
   competitive_alerts[]        payer_alerts[]             hcp_awareness_alerts[]
        │                           │                          │
        └──────────────┬────────────┴──────────────┬───────────┘
                        ▼                            ▼
              GET /alerts (three arrays)   GET /alerts/summary (5 rollup counts)
                        │                            │
                        └──────────► rendered together on one page, from
                                      two responses that are not guaranteed
                                      to reconcile — §8.1
```

### 6.3 Filter resolution

Identical structure to Territory Prioritization §6.3 — the same
`filters.manager_id[].employee_id[].territory_id[]` hierarchy drives the
USERS and TERRITORY NAME dropdowns on this tab.

### 6.4 Ambiguity resolution — "how many high-priority alerts do I have"

```
              "high-priority alerts"
                        │
        ┌───────────────┴────────────────┐
        ▼                                 ▼
   ai_high_count                  count of ai_severity=="HIGH"
   (summary tile, tile 2)         records across the 3 alert arrays
        │                                 │
        └───────────────┬─────────────────┘
                         ▼
        These are not guaranteed equal — §8.1.
        Answer from ai_high_count if the user is
        asking about the tile; answer from the
        list if the user is asking "how many alert
        cards below say HIGH" — and say which you
        used if they could reasonably want either.
```

---

## 7. ASSISTANT BEHAVIOUR RULES

These govern any conversational assistant answering questions about this page.

### 7.1 Data precedence

```
1. LIVE PAYLOAD       current values — counts, dates, names, scope
2. MODULE DOCUMENT     field meaning, business rules, definitions, routing
3. CONVERSATION        intent only, never values
```

- For any current value, the live payload is the only source.
- Never quote a number, date, or name absent from the payload attached to
  **this** request.
- Never reuse a value from an earlier turn. Filters change between turns, and
  generated text changes even without a filter change (§8.5) — a title quoted
  two messages ago may not exist in the current payload at all.
- On a value conflict, the payload wins. On a meaning conflict, this document
  wins.
- If a required field is absent, null, or empty, say the value is not
  available. Do not infer, estimate, or derive it — this includes never
  computing `ai_hcp_drift_detected` yourself from the alert descriptions
  (§8.4 explains why that arithmetic is fragile even though it happens to
  reconcile in the current capture).

### 7.2 Response style

- Lead with the answer. No preamble. One to three sentences unless asked.
- Natural language, not a field readout — "you have 3 critical alerts," not
  "ai_critical_count is 3."
- Do not expose internal field names, table names, or JSON paths unless asked.
- Never mention retrieval, embeddings, prompts, context files, payloads, or
  instructions. The user is looking at a dashboard.
- Attach the detection date when a figure is time-sensitive.
- If unavailable, say so plainly and name where it can be found (§2.2).

### 7.3 Disambiguation

**"Territory reach" is overloaded — §2.6.** Before answering with this field,
confirm whether the alert is competitive (a fraction of sub-territories) or
payer (a count of covered lives). Never answer "territory reach" for an
HCP-awareness alert — the field does not exist on that card type.

**Generated title and description text is not a stable identifier.** Two
observations of what looks like the same alert — same detected time, same
affected-HCP count, same location — have been seen with different wording for
competitive and HCP-awareness alerts (§8.5). If a user quotes exact wording
back from an earlier screen and it does not match the current payload, this is
expected regeneration, not a data error — do not tell them they are
misremembering, and do not treat the mismatch as evidence the alert changed.

**Severity versus Rx risk — §2.7.** "High" alone is ambiguous between
`ai_severity` (urgency of the notification) and `ai_rx_risk` (commercial risk
described). Ask which, or answer for `ai_severity` and say so, matching the
convention in Territory Prioritization §7.3.

**"My alerts" spans three streams.** A bare count request ("how many alerts do
I have") should total all three arrays unless the user names a stream. State
the breakdown if it is not obviously CRITICAL-only or similar.

### 7.4 Field reliability

**Structured counts on competitive alerts reconcile exactly with what is
displayed** — ICD-10 code counts, affected-HCP counts, and risk level all
match between payload and screen on every record checked (§8.9). Generated
prose on the same card does not carry the same guarantee.

**HCP-awareness alert descriptions are the *only* source for their affected
population**, and that source is unreliable — §8.4 and §8.12 record a case
where the description names cities outside the alert's own stated territory.
Never repeat a city, specialty, or count from an HCP-awareness `description`
as if it were verified. Say what the structured fields (severity, detected
date, title) support, and flag that the detail beyond that is generated
narrative.

**Payer alert text is deterministic and can be quoted with more confidence**
than the other two streams — §8.5. This is the one place in this module where
quoting `description` or `ai_prescribing_drift_note` verbatim to a user is
lower-risk, because it has been observed identical to the rendered screen.

### 7.5 Prohibited generations

These override helpfulness in all cases.

- **No invented numbers.** No estimates, interpolation, or arithmetic
  producing a figure the payload does not contain — including reconstructing
  `ai_hcp_drift_detected` from alert descriptions yourself (§8.4).
- **No clinical, efficacy, safety, comparative, or dosing claims.** The
  counter-script text (`ai_counter_script`) is presented as MLR-approved, but
  this document does not independently verify that claim — treat it the same
  as any other generated field for purposes of what the assistant may
  originate, extend, or paraphrase. Quote it; do not build on it.
- **Never de-anonymise brand references.** Payloads use "Product" and
  "Competitor A" / "Competitor B" as a governance control, matching the
  Territory Prioritization convention (§7.5 there). Reproduce the label
  exactly as given — never substitute a real brand or molecule name, even if
  the module guide or another document names one.
- **No off-label content, under any framing.** Same prohibition as Territory
  Prioritization §7.5.
- **No medical advice**, and no opinion on what a prescriber should prescribe.
- **No asserting a contact detail is correct.** `deploy_to_field.rep_email`
  has been observed not matching the paired `rep_name` on the one record
  available (§8.1). Never instruct the user to send anything to an address
  pulled from this field without a caveat.
- **No treating "Dismiss," "Acknowledge," "Deploy to Field," "Schedule Calls,"
  or "Review Later" as data-changing actions.** This is a read-only knowledge
  layer; these are recorded user actions in the host application, not
  something the assistant can perform or confirm.
- **No presenting model output as certainty.** Say "the model flagged," never
  "this competitor is definitely taking share."
- **No filling in `resources` as if it were alert-specific.** The four
  resource links have been observed identical across every payer alert
  (§8.3) — describe them as general-purpose templates, not something
  generated for this payer or this tier change.

### 7.6 Behavioural protocols

| Situation | Response |
|---|---|
| User reports a KPI tile number differing from what they see in the alert list below it | Do not tell them they are wrong. Both are real, independently-sourced numbers (§2.5, §8.1) — give both and say they come from separate responses |
| User quotes alert wording that doesn't match the current payload | Explain generated text is not guaranteed stable between loads (§8.5); do not imply their memory or the earlier screen was wrong |
| Answer is on another tab | Name the tab and what it holds (§2.2). Do not attempt the answer from this payload |
| Question is outside the product | Decline briefly, return to what you can help with |
| Uncertain | Say so. An unanswered question is recoverable; a confidently wrong figure in a regulated setting is not |

### 7.7 Output contract

Responses are validated before reaching the user and rejected if they contain
a numeric token absent from the live payload, an HCP or payer name absent from
the live payload, or a reference to internal system machinery.

### 7.8 Intent routing

| User intent | Source |
|---|---|
| how many critical / high / medium alerts | `ai_critical_count` / `ai_high_count` / `ai_medium_count` — summary, tile value |
| how many HCPs are drifting | `ai_hcp_drift_detected` — summary tile; do not recompute (§7.5) |
| what's the banner say / why am I seeing a banner | `ai_banner_message` |
| what changed with a specific payer | `payer_alerts[]` — `title`, `description`, `tier_change` |
| what changed competitively in an area | `competitive_alerts[]` |
| which HCPs are losing awareness of us | `hcp_awareness_alerts[]` — description only, flagged as narrative (§7.4) |
| what do I say to this HCP / this account | `ai_counter_script` (competitive) or route to Objection Handler (§2.2) |
| who is affected by this alert | `view_affected_hcp` (competitive) or `view_hcp_list` (payer); not available for HCP-awareness alerts |
| who do I deploy this to | `deploy_to_field`, with the email caveat §7.5 |
| what resources are attached | `resources` / `ai_supporting_materials`, with the genericness caveat §8.3/§7.5 |
| is this alert urgent | `ai_severity` |
| how bad is the commercial risk | `ai_rx_risk`, with the casing/scale note §2.7 |
| how far has this spread | `ai_territory_reach`, with the dual-meaning note §2.6 |
| when was this detected | `detected_at` |
| is this current | `last_refresh`, `period` — shared with rest of platform |
| can I dismiss / acknowledge / deploy this from here | Yes, as a recorded UI action; not a data mutation the assistant performs — §7.5 |
| this HCP's full awareness trend | HCP Awareness tab — §2.2 |
| this competitor's full activity | Competitive Intel tab — §2.2 |
| this payer's status even though it's not alerted | Payer Access tab — §2.2 |
| who should I visit / non-writers / what do I say generally | Territory Prioritization / New Writer ID / Objection Handler — §2.2 |

### 7.9 What this module can and cannot answer

**Available:** any KPI tile value and what it means; the banner text; for any
listed alert — severity, detection method, detected date, title, description
(with the reliability caveats above), and every structured field specific to
its stream (impact numbers, ICD-10 codes, risk, counter-script and materials
for competitive; tier change and action note for payer); who is affected,
where that nested list exists; what any control, chip, or button does.

**Not available:** anything on a sibling tab (§2.2); a payer's status if it
has not generated an alert; an HCP's full multi-period awareness trend from
this payload; the source of the affected-HCP count or city list on an
HCP-awareness alert beyond the generated description itself; certainty that
quoted generated text will still read the same on a future reload; any record
change — the platform is read-only here.

---

## 8. DATA QUALITY REGISTER

> **Internal section.** Contains named records and concrete figures. The
> constraints these defects impose are stated qualitatively in §7.3–§7.5.
> If any part of this document is used as machine-readable context, exclude
> section 8 — it contains exactly the values §7.5 forbids repeating as fact.

Ordered by severity.

### 8.1 HIGH — KPI tiles do not reconcile with the alert list beneath them

```
                    summary tile     counted from the 3 alert arrays
ai_critical_count         3          AL-001, AL-002, AL-003            3   match
ai_high_count              3          AL-005, PAYER-19267, PAYER-19498,
                                       PAYER-6469, AL-004                5   MISMATCH (+2)
ai_medium_count            2          AL-008, AL-007                    2   match
```

Critical and Medium reconcile exactly. High does not: the tile reads 3, but
five alerts across the three streams carry `ai_severity: "HIGH"` — one
competitive (AL-005), all three payer alerts, and one HCP-awareness alert
(AL-004). No combination of "HIGH excluding one stream" produces exactly 3
either, so this is not simply a scoping difference by stream.

**Action.** Confirm whether the summary and list responses are backed by the
same computation, and at what point in the pipeline they diverge (compare to
the resolved divergence pattern in Territory Prioritization §8.12 — this one
has not been confirmed resolved). Until confirmed, do not tell a user "you
have exactly 3 high-priority alerts" without noting the tile and the list
disagree.

### 8.2 HIGH — `recommended_actions` is repurposed on payer alerts and no longer drives the buttons

Documented contract (module guide, payer alert card): `recommended_actions`
holds a short list of button labels, e.g. `["View HCP List", "Access
Resources"]`.

Actual payload, all three payer alerts observed:

```
recommended_actions: [ "<the exact text of ai_prescribing_drift_note>" ]
```

One string, duplicating another field, not a button-label list. The screen
nonetheless renders three buttons — **View HCP List**, **Access Resources**,
**Acknowledge** — that are hardcoded in the frontend for this card type and do
not come from `recommended_actions` at all. "Acknowledge" appears on screen
with no field backing it anywhere in the payload.

**Actions**
- Decide whether `recommended_actions` should carry the button labels (fixing
  the payload to match competitive/HCP-awareness behaviour) or be removed from
  the payer alert schema entirely, since it is currently dead data.
- Document where "Acknowledge" actually originates.

### 8.3 MEDIUM — payer alert `resources` are identical across every payer alert

The same four resource entries — Patient Assistance Program enrollment form,
Prior Authorization support document, Copay/Bridge program material, and
formulary appeal template, at the same four static URLs — appear on all three
payer alerts observed (Fairview, MM Industries, City of Detroit), regardless
of tier-change type (Tier 3 → Non-Formulary vs Tier 2 → Tier 3 vs Tier 1 →
Tier 2) or payer.

**Action.** Confirm whether this is intended as a fixed template set or
whether resources are meant to vary by tier-change severity or payer;
currently nothing in the payload distinguishes them.

### 8.4 MEDIUM — the "HCP drift detected" tile has no structured field behind it

`ai_hcp_drift_detected` = 19 in the summary payload. No single field in
`hcp_awareness_alerts[]` sums to 19 — the card type carries no
`ai_affected_hcp_count` at all (§4.5). The figure reconciles only by parsing
the HCP counts named in each alert's own free-text `title`/`description`:

```
AL-003  "... 6 healthcare professionals ..."     6
AL-004  "... 9 HCPs ..."                          9
AL-007  "... 4 practitioners ..."                 4
                                                  --
                                                  19   matches the tile
```

This reconciles in the current capture, but the only source for each
component is generated prose, not a counted field — the same class of risk
flagged for HCP-awareness descriptions generally in §8.12. A future
description that phrases its count differently (a range, a word instead of a
digit, an omitted count) would silently break this rollup.

**Action.** Add a structured `ai_affected_hcp_count` to the HCP-awareness card
type so the tile total is computed from data, not parsed from prose.

### 8.5 MEDIUM — generated title/description/counter-script text is not stable between the rendered screen and the payload, except for payer alerts

Comparing the four captured screenshots against the JSON alert-list payload
for what is evidently the same underlying alert (same detected timestamp,
same affected-HCP count, same location):

**Competitive and HCP-awareness alerts diverge in wording every time:**

```
AL-001 title
  screen:   "Critical Competitive Shift Detected Among 8 HCPs in San Francisco, CA"
  payload:  "Critical Competitive Script Shift Affecting 8 HCPs in San Francisco, CA"

AL-002 title
  screen:   "Critical Competitive Shift Affecting 11 HCPs in Pittsburgh North, PA"
  payload:  "Critical Competitive Script Shift Affecting 11 HCPs in Pittsburgh North PA"

AL-004 title
  screen:   "HCP Detailing Frequency Decline Affecting 9 HCPs in San Francisco, CA"
  payload:  "High Alert: Detailing Frequency Decline Among 9 HCPs in San Francisco, CA"
```

Descriptions and the AL-001 counter-script diverge the same way — same gist,
different sentences, on every record checked.

**Payer alerts are the exception — byte-identical on every field checked:**

```
PAYER-19267 title        screen and payload match exactly
PAYER-19267 description  screen and payload match exactly
PAYER-19267 "Action needed" line / ai_prescribing_drift_note   match exactly
PAYER-6469  same pattern, all match exactly
```

**Reading.** Payer-alert text appears to be generated once and stored, or is
otherwise deterministic. Competitive and HCP-awareness text is either
regenerated on each read or the two captures compared were genuinely two
different generation passes over the same underlying event — either way, it
should not be treated as a fixed value once written down (§7.3).

**Action.** Confirm whether competitive/HCP-awareness GPT-4o content is cached
per alert or regenerated per request; if the latter, decide whether that is
intended, since it means no two reps (or the same rep on two visits) reliably
see the same wording for the same event.

### 8.6 MEDIUM — `alert_id` is never surfaced in the UI

No chip, label, or hidden attribute on any of the four captured screens
displays `alert_id`. The only way to correlate a rendered card back to its
payload record is the combination of detected timestamp, affected-HCP count,
and the location named in the title — and §8.5 shows that combination is the
most that can be relied on, since the wording itself moves.

**Action.** Consider surfacing `alert_id` in a low-visibility spot (e.g. a
tooltip or the "View Affected HCPs" modal) so support and QA can reference a
specific alert unambiguously.

### 8.7 MEDIUM — `ai_rx_risk` casing is inconsistent between streams

```
competitive_alerts   ai_rx_risk = "High"    (title case)
payer_alerts           ai_rx_risk = "HIGH"    (upper case)
```

Both streams use the same field name for the same concept but render it in a
different case. A consumer matching on the literal string will fail silently
on one stream or the other.

**Action.** Normalise to one case across streams; version the change if any
downstream consumer already matches on the current casing.

### 8.8 LOW — KPI tile treatment is inconsistent within the same row

Tiles 1, 2, and 4 (Critical, High, HCP drift) carry a technique badge
(`AI DETECTED` or `ML MODEL`). Tile 3 (Medium) carries the static text "No
change" instead of a badge, regardless of whether the medium count actually
changed period over period — nothing in the summary payload (§4.2) supplies a
"changed since last period" signal for this or any tile, so "No change" cannot
currently be verified against data. Tile 5 (Early detection) carries a
different kind of static subtitle ("vs 6-8 traditional") that is also not
sourced from the payload.

**Action.** Either back "No change" with a real period-over-period
comparison, or replace it with the same badge treatment as tiles 1/2/4 for
visual consistency.

### 8.9 What reconciles correctly

Recorded so the failures above are not read as systemic.

- Every structured numeric field on competitive alerts checked against its
  screenshot — `ai_affected_hcp_count`, all four `ai_icd10_codes_affected[]`
  `hcp_count` values, `ai_territory_reach`, `ai_severity`, `ai_rx_risk` —
  matches exactly on AL-002 and AL-008, the two records with a full-card
  screenshot available.
- `recommended_actions` correctly drives the visible buttons for both
  competitive alerts (`Deploy to Field` / `View Affected HCPs` / `Dismiss`)
  and HCP-awareness alerts (`Schedule Calls` / `Review Later`) — only the
  payer stream has repurposed this field (§8.2).
- Every payer-alert field checked — title, description, affected-HCP count,
  territory reach (covered lives), Rx risk, and the action-needed line —
  matches exactly between screen and payload on both PAYER-19267 and
  PAYER-6469.
- `tier_change.from` / `tier_change.to` matches the tier wording embedded in
  each payer alert's own `title` and `description` on every record.
- `deploy_to_field.affected_hcps` matches `view_affected_hcp` as a set (order
  differs, membership does not) on AL-001, the one record with both populated.

The detection and counting logic behind each stream appears sound. The
defects found are concentrated in generated-text stability (§8.5), one
repurposed field (§8.2), one unreconciled rollup (§8.1), and presentation
polish (§8.6, §8.8) — not in the underlying numbers.

### 8.10 LOW — null SKU is rendered to the user as the literal word "null"

`ai_supporting_materials[].sku` is `null` on every observed record. The card
renders this as, e.g., "APEX Trial Results (SKU: null)" — the raw absence
marker reaches the screen as visible text.

**Action.** Suppress the "(SKU: …)" suffix entirely when `sku` is null, rather
than stringifying the null.

### 8.11 What is reliable enough to quote directly

- Competitive and HCP-awareness `recommended_actions` → button labels.
- Every structured field in §4.3's inventory except the generated-text fields
  flagged in §8.5.
- All of payer alerts' fields, per §8.5 and §8.9.

### 8.12 HIGH — an HCP-awareness alert's own description names cities outside its stated territory

AL-004 ("High Alert: Detailing Frequency Decline Among 9 HCPs in San
Francisco, CA") — payload description:

> "...for 9 HCPs across various specialties in San Francisco, CA... among HCPs
> in Internal Medicine, Hematology/Oncology, Family Medicine, and
> Gastroenterology."

Rendered screen description for the same alert:

> "...among HCPs in San Francisco, CA, particularly impacting specialties such
> as Gastroenterology and General Practice. This trend has been observed over
> the past few months, affecting a total of 9 HCPs across various locations
> including Nashville, Weirton, and Albany."

The specialty list differs between the two versions (expected, given §8.5),
but more importantly the screen version names three cities — Nashville,
Weirton, and Albany — that are not in California and are not consistent with
a "San Francisco, CA" territory alert. Nashville is in Tennessee, Weirton in
West Virginia; Albany could be New York or Georgia — none plausibly part of a
San Francisco-area territory.

A related, smaller divergence appears on AL-003 ("Critical Detailing Decline
for 6 HCPs in Pittsburgh North PA"): the payload description says the trend
"has been observed from August 2026" while the rendered screen says "from
early July to early August 2026" — a materially longer window than the
payload itself states.

**Action.** Treat this as the HCP-awareness-stream equivalent of the
Territory Prioritization warm-introduction geography defect (§8.8 there) —
the generation step is not constrained to the alert's own territory or its
own detected date range. Add a locality and date-range check to the
generation post-process for this stream, and until fixed, never repeat a
city, specialty, or date range from an HCP-awareness `description` as
verified fact (§7.4).

---

## 9. OPEN ITEMS

### 9.1 Branding and platform naming

Same three names in play as documented in Territory Prioritization §9.1
(`Veeva AI Insight 360` / `Insights 360™ V2` + `SLIPSTREAM` / `POWERED BY
DATAstream AI`). This document uses the on-screen names.

### 9.2 Unresolved questions

1. Are the summary and alert-list responses backed by the same underlying
   computation? If so, why does §8.1's High count diverge while Critical and
   Medium reconcile?
2. Is competitive/HCP-awareness generated text (title, description,
   counter-script) cached per alert, or regenerated on every read? (§8.5)
3. Should `recommended_actions` be fixed to carry button labels for payer
   alerts, matching the other two streams, or removed from that schema
   entirely? (§8.2)
4. Should `resources` vary by payer or tier-change type, or is a fixed
   four-document template intended? (§8.3)
5. Should HCP-awareness alerts carry a structured `ai_affected_hcp_count`
   instead of requiring the tile total to be parsed from three separate
   description strings? (§8.4)
6. Is the AL-004 city list (Nashville, Weirton, Albany) a generation defect,
   or does it reflect a real cross-territory rollup that the description is
   correctly reporting and the title is mislabeling as "San Francisco, CA"?
   Needs a source-data check, not a guess. (§8.12)
7. Should `alert_id` be surfaced somewhere in the UI for support/QA
   correlation? (§8.6)
8. Should `ai_rx_risk` casing be normalised across streams before an external
   consumer binds to one form or the other? (§8.7)

---

## 10. VOCABULARY

| Term | Meaning |
|---|---|
| **HCP** | Healthcare professional — prescriber or clinical staff |
| **Rep** | Field sales representative. The primary user |
| **Manager** | Owns a set of representatives; sees their combined scope |
| **Territory** | A geographic or account-based assignment owned by a rep |
| **Alert** | One machine-detected finding in one of the three streams below |
| **Stream** | One of `competitive_alerts`, `payer_alerts`, `hcp_awareness_alerts` |
| **Severity** | `ai_severity` — CRITICAL / HIGH / MEDIUM, how urgent the alert is |
| **Rx risk** | `ai_rx_risk` — commercial risk level described by the alert, not the same axis as severity |
| **Territory reach** | Overloaded field — sub-territory fraction for competitive alerts, covered lives for payer alerts, absent for HCP-awareness alerts |
| **Drift** | Gradual decline in either prescribing (competitive stream's drift note) or detailing/awareness (HCP-awareness stream) |
| **Counter-script** | MLR-labelled response text for engaging an HCP, present only on competitive alerts |
| **Tier / tier change** | A payer's formulary placement for the product, and any detected movement between tiers |
| **PA** | Prior authorization — a payer requirement gating access, distinct from the platform's own "PA" resource template naming |
| **Covered lives** | Number of patients whose insurance plan is affected by a payer's tier change |
| **Abandonment risk** | Estimated likelihood a patient does not fill a prescription after a tier downgrade |
| **MLR** | Medical, Legal and Regulatory review. Approved content only |
| **Deploy to Field** | Action surfaced on competitive alerts to route the alert to a named rep and territory |
| **Period** | The reporting quarter in the data-reference panel, shared platform-wide |
| **Last refresh** | When the pipeline last calculated, shared platform-wide |
| **PERT / EPI** | Pancreatic enzyme replacement therapy / exocrine pancreatic insufficiency |

**Brand references are generalised by design.** Payloads use generic labels
("Product", "Competitor A") in place of confidential product and competitor
names, exactly as in Territory Prioritization §10 — reproduce the label
exactly as given.


---

# PART 5 — HCP AWARENESS

**Application:** Action Center — Launch & Market Defense · **Platform module:** Module 5 of 7

## 1. MODULE

| | |
|---|---|
| **Module name** | HCP Awareness |
| **Section heading, as displayed** | HCP awareness monitoring |
| **Technique badge** | PREDICTIVE ANALYTICS |
| **Parent application** | Action Center |
| **Parent platform** | Veeva AI Insight 360 (UI shows "Insights 360™ V2") |
| **Position** | Tab 2 of 4 in Action Center; Module 5 of 7 on the platform |
| **Primary user** | Field sales representative |
| **Secondary user** | Sales manager (consolidated multi-territory view) |
| **Therapy context** | Pancreatic enzyme replacement therapy (PERT / EPI) |
| **Access model** | Role-based, derived from the authenticated session |
| **Write capability** | None. "Schedule Call" is a recorded action, not a record edit — see §7.5 |
| **Refresh cadence** | Batch; shares `last_refresh` with the rest of the platform |

**The question this module answers:** *which doctors are losing awareness of
our product, and how urgently?*

It tracks a per-HCP awareness score across four weekly periods, fits a trend
to it, and surfaces a card per HCP with the direction of movement, the size of
the change, and a generated narrative on what the HCP has apparently been
doing (reading competitor content, going quiet, engaging positively). A
territory-wide bar chart gives the same trend at the aggregate level.

**The module's own description, as shown on screen ("How it works"):**

> AI monitors HCP awareness scores, competitive script shifts, payer access,
> and prescribing drift in real time. Detects HCP drift within 2–4 weeks vs
> 6–8 weeks with traditional monthly reporting. Tracks engagement by ICD-10
> codes and AIM XR article views for niche drugs.

This description reaches well beyond what this tab's own data actually
contains — competitive script shifts and payer access are Active Alerts /
Payer Access content, and ICD-10 tracking does not appear anywhere in this
tab's payload. Section 8.2 records this in detail.

**The platform detects and drafts; the representative decides whether and how
to act.** The generated activity narrative on each card is decision support,
not a verified record of what the HCP actually did — see §7.4.

---

## 2. MODULE DETAILS

### 2.1 Position in the platform

```
Veeva AI Insight 360 — 7 modules
│
├── My Insights (RepStream)
│   ├── Territory Prioritization      existing writers, ranked by opportunity
│   ├── New Writer ID                 non-writers, conversion candidates
│   └── Objection Handler             what to say when pushed back on
│
└── Action Center — launch and market defence
    ├── Active Alerts                 threat feed, three streams
    ├── HCP Awareness               ← THIS MODULE — per-HCP score and trend
    ├── Competitive Intel             competitor signals and counter-strategy
    └── Payer Access                  formulary tiers and access risk
```

### 2.2 Sibling modules — routing reference

| Destination | Location | Holds | Route when user asks |
|---|---|---|---|
| **Active Alerts** | Action Center tab | The same declining-awareness HCPs re-surfaced as alert cards, alongside two unrelated streams (competitive, payer) and a territory-wide "HCP drift detected" rollup | the alert version of this, what needs my attention, deploy to field, the "19" HCP drift figure — see §2.6 |
| **Competitive Intel** | Action Center tab | Which competitor is behind the pressure, scored by threat level, with talking points | what is the competitor doing, threat level, talking points |
| **Payer Access** | Action Center tab | Whether a formulary change is contributing to the drop, for any payer, not just alerted ones | is this a coverage issue, formulary, tier, prior auth |
| **Territory Prioritization** | RepStream tab | Whether this HCP is also ranked by prescribing opportunity | is this HCP a priority to visit, their Rx trend |
| **Objection Handler** | RepStream tab | What to say if the HCP raises a specific objection during the scheduled call | what do I say when, pushback, objection |

**This module is HCP-scoped, one card per doctor — the same unit as Territory
Prioritization and New Writer ID, but for a different population.** Territory
Prioritization covers existing writers; New Writer ID covers non-writers; this
module covers whichever HCPs the awareness model has scored, regardless of
whether they currently prescribe.

### 2.3 How the trend is produced

| Technique | Contribution |
|---|---|
| Four-period score read | `awareness_trend` — territory-wide average per weekly period |
| Linear regression | `ai_trend_direction`, `ai_score_change_pct` per HCP |
| NLP classification | Root-cause categorisation feeding the generated narrative |
| Generative narrative | `ai_aim_xr_activity` — what the HCP appears to have been doing |

**The three `analysis_badges` values are split across three different places
on screen, not shown together on any one element:**

```
PREDICTIVE_ANALYTICS   → section-heading badge ("HCP awareness monitoring")
AI_SCORING              → trend-chart badge ("Awareness Score Trend")
NLP_ANALYSIS            → per-HCP card badge ("PRESCRIBING PATTERNS" panel)
```

Do not expect all three badges to appear on an individual HCP card — only
`NLP_ANALYSIS` does.

### 2.4 Access scope

Same organisational hierarchy as the rest of the platform — visibility follows
the authenticated session, and every figure on the page corresponds to the
USERS / TERRITORY NAME filter currently in force.

**Note on filters in this payload.** The sample captured for this document did
not include a `filters` block. The rest of the platform uses a consistent
manager → employee → territory hierarchy for its two dropdowns (documented in
full in Territory Prioritization §4.3); this tab is presumed to share it, but
that has not been directly confirmed against this module's own response —
flagged in §9.

### 2.5 One combined response, unlike Territory Prioritization or Active Alerts

Territory Prioritization and Active Alerts each split their data across two
separate responses (KPI/summary and detail list). **HCP Awareness delivers the
trend chart and the per-HCP cards together, in one response.** There is no
separate summary call to reconcile against — the trend array and the item
list either both reflect the current filter scope or the whole response is
stale; there is no possibility of the KPI-vs-list divergence documented for
the sibling modules (Territory Prioritization §8.12, Active Alerts §8.1)
occurring within this tab specifically.

### 2.6 Do not confuse this module's numbers with the Active Alerts "HCP drift" tile

The Active Alerts summary carries a tile, **HCP drift detected**, whose value
in the captured sample was 19. This module's own item list, in the same
capture window, contains 15 HCPs total, of which 8 carry
`ai_trend_direction: "Declining"`. Neither 15 nor 8 equals 19.

The 19 figure is documented in the Active Alerts module as deriving from the
HCP counts embedded in that module's own `hcp_awareness_alerts` descriptions
(6 + 9 + 4), not from this module's declining-HCP count. **Never answer "how
many HCPs are drifting" using this module's list when the user is actually
asking about the Active Alerts tile, and vice versa — they are different
figures from different sources that happen to describe related things.**

### 2.7 Three fields answer three different questions — do not conflate them

| Field | Question it answers | Values observed |
|---|---|---|
| `ai_awareness_level` | Where the score currently sits on an absolute band | `Medium`, `High` (no `Low` observed — §9) |
| `ai_trend_direction` | Which way the score is moving | `Declining`, `Stable`, `Improving` |
| `ai_score_change_pct` | How much it moved, as a signed percentage | e.g. `-31.9`, `+24.6` |

**In the captured sample, every Declining HCP is level Medium and every
Improving HCP is level High** — a pattern in this particular data, not a rule
enforced anywhere in the schema. Stable HCPs span both levels (Chelsey Field
and Sam Pappas are Medium; Mary Shick is High). Do not assume level implies
trend, or trend implies level, when answering — check both fields.

---

## 3. FRONTEND — OVERVIEW AND KEYS

### 3.1 Application shell, data reference, KPI tiles, tab bar

Shared with Active Alerts — same shell, same data-reference panel
(`period` / `last_refresh`), same five KPI tiles at the top of the page
(§3.4 of the Active Alerts document), same four-tab bar with **HCP Awareness**
as the second tab. None of these are recomputed per tab; switching to this tab
does not change the tile values.

### 3.2 "How it works" panel

```
┌─ How it works ──────────────────────────────────────── [PREDICTIVE ANALYTICS]
│ AI monitors HCP awareness scores, competitive script shifts, payer access,
│ and prescribing drift in real time. Detects HCP drift within 2–4 weeks vs
│ 6–8 weeks with traditional monthly reporting. Tracks engagement by ICD-10
│ codes and AIM XR article views for niche drugs.
└──────────────────────────────────────────────────────────────────────────
```

Static descriptive copy, not sourced from this module's own response — see
§8.2 for the specific claims in this text that this tab's payload does not
support.

### 3.3 Awareness Score Trend chart

```
┌─ Awareness Score Trend (Mar 25 - Apr 22, 2026) ──────────── [AI SCORING] ─┐
│ 100%                                                                       │
│  90%                                                                       │
│  80%                                                                       │
│  70%   71.5%        69.7%        68.8%        65.5%                        │
│  60%   ██(green)    ██(orange)   ██(orange)   ██(orange)                   │
│  50%   Jan 29        Feb 26       Mar 25       Apr 22                       │
└─────────────────────────────────────────────────────────────────────────┘
```

Four bars, one per period in `awareness_trend`. The heading date range is
`ai_declining_period`, reused here purely as a label for the window being
charted — the chart itself plots all four periods, not only the declining
ones.

**Colour rule observed:** the first (earliest / baseline) period renders
green; every subsequent period renders orange, consistent with each of them
sitting below the Jan 29 starting value. This has not been tested against a
capture where a later period recovers above the baseline.

### 3.4 "HCPs with declining awareness" section and card anatomy

```
┌─ HCPs with declining awareness (Mar 25 - Apr 22, 2026) ───────────────────┐
│                                                                             │
│ ┌───────────────────────────────────┐  ┌───────────────────────────────┐ │
│ │ (LL) Leslie Lewis    Awareness     │  │ (MP) Marc Piper    Awareness  │ │
│ │      Gastroenterology  score       │  │      Gastroenterology score   │ │
│ │      [Schedule Call]   40.6%       │  │      [Schedule Call]  45.5%   │ │
│ │              ↓ 31.9% from Jan29 [AI]│  │            ↓ 31.2% from Jan29[AI]│
│ │ ┌─ PRESCRIBING PATTERNS ─[NLP ANALYSIS]┐│ ┌─ PRESCRIBING PATTERNS ─[NLP ANALYSIS]┐│
│ │ │ AIM XR Activity: <generated text>  ││ │ AIM XR Activity: <generated text>││
│ │ └────────────────────────────────────┘│ └──────────────────────────────┘ │
│ └───────────────────────────────────┘  └───────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

Two-column grid, one card per HCP.

#### Card elements

| Element | Position | Notes |
|---|---|---|
| Avatar | Left, circular, initials | Colour keyed to the record — see §8.5 for an observed anomaly |
| Name | Header, bold | |
| Specialty | Under name, muted | |
| Schedule Call button | Top right | Present on every card regardless of trend direction — §8.4 |
| Awareness score | Right, large, coloured | `ai_awareness_score`, percentage |
| Change line | Under score | Arrow (↑/↓) + `\|ai_score_change_pct\|` + "from " + `ai_change_from_period`, with an `AI` badge |
| Panel header | Card footer | Reads **"PRESCRIBING PATTERNS"** with an `NLP ANALYSIS` badge — see §8.1 |
| Panel body | Card footer | Prefixed **"AIM XR Activity:"**, then `ai_aim_xr_activity` |

**The section heading says "declining," but the grid is not filtered to
declining HCPs.** All 15 captured records — 8 Declining, 4 Improving, 3
Stable — render under this one heading, distinguished only by score colour
and the arrow direction on the change line. See §8.3.

---

## 4. BACKEND — KEY DETAILS

### 4.1 Data delivery

**Trend chart data and the per-HCP card list arrive together in one
response** (§2.5) — a structural difference from Territory Prioritization and
Active Alerts, both of which split their data across two calls.

**Territory scope is derived from the authenticated session**, consistent
with the rest of the platform.

### 4.2 Summary-level fields

| Field | Type | Rendered | Notes |
|---|---|---|---|
| `awareness_trend` | array of `{period, avg_score}` | Yes | Drives the 4-bar chart, §3.3 |
| `ai_declining_period` | string | Yes | Date-range label on both the chart heading and the card-grid heading |

### 4.3 Per-HCP item — field inventory (11 keys; 2 undocumented in the module guide)

| Field | Type | Rendered | Notes |
|---|---|---|---|
| `hcp_full_name` | string | Yes | |
| `specialty` | string | Yes | |
| `institution` | string or null | **No** | `null` on every record observed; never rendered when null |
| `ai_awareness_score` | number | Yes | Percentage |
| `ai_awareness_level` | string | **No, not as text** | Only ever implied through score colour — §2.7, §8.5 |
| `ai_trend_direction` | string | Yes | Drives the arrow direction and colour treatment |
| `ai_score_change_pct` | number | Yes | Signed; rendered as unsigned magnitude + arrow |
| `ai_change_from_period` | string | Yes | **Undocumented in the module guide's 9-key table.** Always `"Jan 29"` in the captured sample — the baseline period, not a rolling comparison |
| `ai_aim_xr_activity` | string | Yes | Generated narrative — reliability varies by record, §8.6 |
| `analysis_badges` | array of strings | Partially | Split across three UI locations, not shown together — §2.3 |
| `ai_icd10_prescribing_patterns` | array | **No, and always empty** | **Undocumented in the module guide.** Empty array on every record — see §8.1 |

---

## 5. FRONTEND ↔ BACKEND MAPPING

### 5.1 Trend chart

| UI element | Payload field | Transform |
|---|---|---|
| Chart heading date range | `ai_declining_period` | Direct |
| Bar labels | `awareness_trend[].period` | Direct |
| Bar heights / percentage labels | `awareness_trend[].avg_score` | Direct |
| Bar colour | Position in array | First = green, rest = orange (observed rule, §3.3) |

### 5.2 HCP card

| UI element | Payload field | Transform |
|---|---|---|
| Avatar initials | `hcp_full_name` | First letter of first two words |
| Avatar / score colour | Not clearly tied to one field | Correlates loosely with `ai_trend_direction` but has at least one exception — §8.5 |
| Name | `hcp_full_name` | Direct |
| Specialty | `specialty` | Direct |
| Awareness score | `ai_awareness_score` | Suffixed "%" |
| Change line | `ai_score_change_pct`, `ai_change_from_period` | Sign → arrow direction; magnitude shown unsigned; "from " + period |
| "PRESCRIBING PATTERNS" panel header | Nothing — **not** `ai_icd10_prescribing_patterns` | Static label; the field it appears to name is always empty — §8.1 |
| "AIM XR Activity:" body | `ai_aim_xr_activity` | Direct, prefixed label; not stable across captures for most records — §8.6 |
| Schedule Call button | Not conditioned on `ai_trend_direction` | Rendered unconditionally — §8.4 |
| *(not rendered anywhere)* | `ai_awareness_level` | §2.7, §8.5 |
| *(not rendered anywhere)* | `institution` | Always null in this capture |

### 5.3 Mapping notes and traps

**The card's most prominent label, "PRESCRIBING PATTERNS," names a field that
never has data.** `ai_icd10_prescribing_patterns` is an empty array on every
record in the captured sample. Whatever renders under that header is sourced
from `ai_aim_xr_activity` instead — a digital-engagement narrative, not a
prescribing pattern. Do not tell a user this panel shows prescribing data.

**`ai_awareness_level` has no on-screen label.** A user asking "is this HCP
High or Medium awareness" cannot get that answer by looking at the card; only
the payload carries it. Answer from the payload field directly rather than
inferring it from card colour, which has been observed to disagree with it
in at least one case (§8.5).

**The "How it works" copy over-describes this tab.** It references
competitive script shifts, payer access, and ICD-10 tracking — none of which
this tab's own payload provides (ICD-10 is always empty; competitive/payer
content lives on the sibling Active Alerts, Competitive Intel, and Payer
Access tabs). Do not use this copy as a source of what this module's data
actually contains — use §4 instead.

---

## 6. GRAPHICAL FLOW

### 6.1 Page lifecycle

```
   Rep opens HCP Awareness (Action Center, second tab)
                │
                ▼
   Territory scope resolved from the authenticated session
                │
                ▼
   Single combined response
                │
        ┌───────┴────────┐
        ▼                ▼
  Trend chart data   Per-HCP item list
        │                │
        ▼                ▼
  4-bar chart       Card grid, "declining" heading,
  (all 4 periods)   all trend directions rendered — §8.3
                            │
                            ▼
                  [Schedule Call] clicked
                            │
                            ▼
                  recorded as a rep action;
                  no further data returned to this tab
       │
       ▼
   Rep changes USERS or TERRITORY NAME
                │
                ▼
   Presses Apply ──► response refetches with the new scope
```

### 6.2 Scoring pipeline

```
   SOURCE
   ├── 4 weekly awareness-score reads per HCP
   └── Digital engagement / detailing signal
                │
                ▼
   ┌────────────────────────────────────────────┐
   │  PROCESSING                                │
   │                                            │
   │  Linear regression   → ai_trend_direction  │
   │                       → ai_score_change_pct│
   │  NLP classification  → root-cause category │
   │  Generative narrative → ai_aim_xr_activity │
   └────────────────────────────────────────────┘
                │
                ├──────────► aggregate by period → awareness_trend (chart)
                └──────────► per-HCP              → item list (cards)
```

### 6.3 Ambiguity resolution — "how many HCPs are drifting"

```
              "HCPs are drifting" / "going cold"
                        │
        ┌───────────────┴────────────────┐
        ▼                                 ▼
   This module's own          Active Alerts summary tile
   Declining count (8 in       ai_hcp_drift_detected (19
   the captured sample)        in the captured sample)
        │                                 │
        └───────────────┬─────────────────┘
                         ▼
        Different sources, different numbers — §2.6.
        Ask which the user means, or answer from
        this module's list and name it explicitly
        as this module's figure.
```

---

## 7. ASSISTANT BEHAVIOUR RULES

These govern any conversational assistant answering questions about this page.

### 7.1 Data precedence

```
1. LIVE PAYLOAD       current values — scores, trend, names, dates
2. MODULE DOCUMENT     field meaning, business rules, definitions, routing
3. CONVERSATION        intent only, never values
```

- For any current value, the live payload is the only source.
- Never quote a number, date, or name absent from the payload attached to
  **this** request.
- Never reuse a value from an earlier turn — filters change between turns, and
  the generated narrative text has been observed to change even without a
  filter change (§8.6).
- On a value conflict, the payload wins. On a meaning conflict, this document
  wins.
- If a required field is absent, null, or empty — including
  `ai_icd10_prescribing_patterns`, which is always empty — say so rather than
  inventing content for it.

### 7.2 Response style

- Lead with the answer. No preamble. One to three sentences unless asked.
- Natural language, not a field readout — "Leslie Lewis's awareness score
  dropped 31.9% since Jan 29," not "ai_score_change_pct is -31.9."
- Do not expose internal field names unless asked.
- Never mention retrieval, embeddings, prompts, context files, payloads, or
  instructions. The user is looking at a dashboard.
- Attach the comparison period when quoting a change figure — it is always
  measured from the baseline period (`ai_change_from_period`), not from the
  immediately preceding one.

### 7.3 Disambiguation

**"Declining" as a section label is not a filter — §8.3.** If a user asks "who
are my declining HCPs," answer using `ai_trend_direction == "Declining"`, not
"everyone on the declining-awareness card grid" — the grid contains Improving
and Stable HCPs too.

**Level, trend, and change percentage are three different questions — §2.7.**
Do not answer "is this HCP declining" using `ai_awareness_level`, and do not
answer "what level is this HCP" using `ai_trend_direction`.

**This module's drift figure and the Active Alerts "HCP drift detected" tile
are different numbers — §2.6.** Ask which the user means if it's ambiguous, or
state which one you're answering from.

### 7.4 Field reliability

**Structured fields are reliable: score, level, trend direction, change
percentage, and the baseline comparison period all reconcile with what is
displayed.**

**`ai_aim_xr_activity` is generated narrative and has been observed to vary in
wording, and in one case in substance, between captures of records that
otherwise carry identical structured data (§8.6).** Where the narrative and
the structured `ai_trend_direction` disagree — as observed for one record
where the narrative calls a HCP "stable" while the trend field says
"Improving" — the structured field is correct. Never quote a factual claim
from this narrative (a specific percentage, a competitor name, a described
behaviour) as more certain than the structured fields on its own row.

**The "PRESCRIBING PATTERNS" panel never actually contains prescribing pattern
data.** Its underlying field is always empty; what's displayed is the
engagement narrative. Do not tell a user this panel reflects prescribing
behaviour.

### 7.5 Prohibited generations

These override helpfulness in all cases.

- **No invented numbers.** No estimates or arithmetic producing a figure the
  payload does not contain.
- **No clinical, efficacy, safety, comparative, or dosing claims.**
- **Never de-anonymise brand references.** Payloads use "Product,"
  "Competitor A," and "Competitor B" as a governance control, consistent with
  every other module in this platform. Reproduce the label exactly as given.
- **No off-label content, under any framing.**
- **No medical advice**, and no opinion on what a prescriber should prescribe.
- **No presenting the generated activity narrative as a verified fact about
  what the HCP did.** Say "the model describes," never "this HCP has been
  reading."
- **No treating "Schedule Call" as a data-changing action the assistant can
  perform.** It is a recorded rep action in the host application; the
  assistant does not have write access here.
- **No filling in `institution` when null**, and no inferring a hospital or
  clinic affiliation from name or specialty alone.

### 7.6 Behavioural protocols

| Situation | Response |
|---|---|
| User asks for "declining" HCPs and expects the full card grid | Clarify that the grid shown includes Improving and Stable HCPs too, and offer the actual Declining subset if that's what they want |
| User quotes activity-narrative wording that doesn't match the current payload | Explain generated text is not guaranteed stable between loads, matching the convention in Active Alerts §7.3; do not imply their memory was wrong |
| User conflates this module's drift count with the Active Alerts tile | Give both figures, named by source, per §2.6 |
| Answer is on another tab | Name the tab and what it holds (§2.2). Do not attempt the answer from this payload |
| Uncertain | Say so. An unanswered question is recoverable; a confidently wrong figure in a regulated setting is not |

### 7.7 Output contract

Responses are validated before reaching the user and rejected if they contain
a numeric token absent from the live payload, an HCP name absent from the live
payload, or a reference to internal system machinery.

### 7.8 Intent routing

| User intent | Source |
|---|---|
| what's this HCP's current awareness score | `ai_awareness_score` |
| is this HCP High or Medium awareness | `ai_awareness_level` — not on screen, answer from payload |
| is this HCP's awareness going up or down | `ai_trend_direction` |
| by how much has it changed | `ai_score_change_pct`, with `ai_change_from_period` |
| why — what's driving the change | `ai_aim_xr_activity`, flagged as narrative — §7.4 |
| who is actually declining (not just on the grid) | Filter on `ai_trend_direction == "Declining"` — §7.3 |
| what's the territory-wide trend | `awareness_trend[]` |
| how many HCPs are drifting overall | This module's Declining count, or Active Alerts' `ai_hcp_drift_detected` — ask which, §2.6 |
| what's the prescribing pattern for this HCP | Not available on this tab — the field exists but is always empty; route to Territory Prioritization for actual Rx data |
| what's the payer / competitive angle here | Payer Access / Competitive Intel — §2.2 |
| schedule a call | Recorded UI action, not something the assistant performs — §7.5 |
| is this current | `last_refresh`, `period` — shared platform-wide |

### 7.9 What this module can and cannot answer

**Available:** any HCP's current score, level, trend direction, and change
percentage; the territory-wide four-period trend; the generated activity
narrative (with the reliability caveat in §7.4); what any badge, panel
header, or button represents — including where that label is misleading
(§8.1).

**Not available:** actual ICD-10 prescribing-pattern data (the field exists,
is always empty, and is not the same thing as the panel it's shown under);
institution/hospital affiliation (always null in this capture); a true count
of only-declining HCPs from the section heading alone (§8.3); reconciliation
between this module's drift count and the Active Alerts tile (§2.6); anything
belonging to a sibling tab (§2.2); any record change — the platform is
read-only here.

---

## 8. DATA QUALITY REGISTER

> **Internal section.** Contains named records and concrete figures. The
> constraints these defects impose are stated qualitatively in §7.3–§7.5.
> If any part of this document is used as machine-readable context, exclude
> section 8 — it contains exactly the values §7.5 forbids repeating as fact.

Ordered by severity.

### 8.1 HIGH — the card panel titled "PRESCRIBING PATTERNS" never shows prescribing data

Every one of the 15 captured records carries
`"ai_icd10_prescribing_patterns": []` — an empty array. The panel on screen
that is headed **"PRESCRIBING PATTERNS"** does not display anything from this
field; it displays `ai_aim_xr_activity` instead, labelled underneath as "AIM
XR Activity." The panel header therefore names a data category the card never
actually populates, and silently substitutes a different field (digital
engagement narrative, not prescribing behaviour) under that header.

**Action.** Either populate `ai_icd10_prescribing_patterns` and show it under
its own header, or rename the panel to reflect what it actually contains
("Digital Engagement" / "AIM XR Activity"), so the label matches the data.

### 8.2 MEDIUM — the "How it works" copy describes capabilities this tab's data does not contain

On-screen text: "AI monitors HCP awareness scores, **competitive script
shifts, payer access**, and prescribing drift in real time... Tracks
engagement by **ICD-10 codes** and AIM XR article views."

Checked against this tab's own payload:

```
competitive script shifts   → not in this payload (lives on Active Alerts)
payer access                → not in this payload (lives on Payer Access)
ICD-10 code engagement      → field present but always empty (§8.1)
prescribing drift           → not in this payload (lives on Territory
                                Prioritization / Active Alerts' competitive
                                stream)
```

The only claim in this copy that this tab's data actually supports is
tracking "HCP awareness scores." The rest describes the platform generally,
not this specific tab.

**A related, smaller inconsistency:** this copy states detection happens
"within 2–4 weeks," while the Active Alerts tab's own "Early detection" KPI
tile, describing the same general capability, shows a specific value of "0.3
weeks" against the same "6-8 traditional" baseline both texts cite. The two
numbers describing the same claim do not agree.

**Actions**
- Either tailor this tab's "How it works" copy to only what this endpoint
  returns, or clearly present it as a platform-level description rather than
  a tab-level one.
- Reconcile the "2–4 weeks" range against the live "0.3 weeks" figure on
  Active Alerts, or clarify they measure different things.

### 8.3 HIGH — the "HCPs with declining awareness" heading does not filter to declining HCPs

Of the 15 records rendered under this heading in the captured sample:

```
Declining   8   (Leslie Lewis, Marc Piper, Julia Derenzi, Wayne Lucas,
                 Leslie Whitney, Leonid Frenkel, Jacob Berman, Diana McFarlane)
Improving   4   (Sohaib Jamil, Ardene Ballonado, Jeremy Herman, Gayleen Prausa)
Stable      3   (Chelsey Field, Sam Pappas, Mary Shick)
```

Fewer than 60% of the cards under "declining awareness" are actually
declining. The Improving HCPs are visually distinguishable (green colouring,
an upward arrow, a positive percentage such as "↑ 24.6% from Jan 29"), so a
careful reader can tell — but the section title itself is inaccurate for the
majority-adjacent population it also displays.

**Action.** Either rename the heading (e.g., "HCP awareness — all tracked
HCPs") or split the section so only genuinely declining HCPs appear under a
"declining" label, with Improving/Stable HCPs shown separately or omitted.

### 8.4 LOW — "Schedule Call" is offered unconditionally, including for improving HCPs

The action button is identical and equally prominent on every card regardless
of `ai_trend_direction` — an HCP whose awareness rose 24.6% (Sohaib Jamil)
gets the same "Schedule Call" prompt as one whose awareness fell 31.9%
(Leslie Lewis). Combined with §8.3, this weakens the prioritisation value of
the section: a rep skimming buttons rather than reading each card gets no
signal about which calls are actually urgent.

**Action.** Consider a different or absent call-to-action for Improving/Stable
HCPs, or a secondary visual cue distinguishing button urgency.

### 8.5 MEDIUM — one record's card styling and its own narrative disagree with its structured trend field

Gayleen Prausa: `ai_trend_direction: "Improving"`, `ai_awareness_level:
"High"`, score 71.5, change +20.4% from Jan 29 — structurally identical in
shape to the other three Improving/High HCPs (Sohaib Jamil, Ardene Ballonado,
Jeremy Herman).

Two things diverge for this one record:

- **The card's own generated narrative describes her as "stable":** "HCP
  engagement is **stable** with a significant increase in score, indicating
  positive interaction with our content" — using the word "stable" while the
  structured field says "Improving."
- **The card renders in the amber/orange treatment used elsewhere for
  Stable-tier cards**, rather than the green treatment the other three
  Improving/High HCPs receive.

Both the colour and the generated text point toward "stable" for a record
the structured field calls "Improving." Since her score (71.5) is
substantially lower than the other three Improving/High HCPs (80.1–85.3), one
plausible explanation is that card styling and narrative generation are keyed
to an absolute score threshold rather than purely to `ai_trend_direction`,
producing disagreement near that threshold.

**Action.** Confirm whether card colour and the narrative's stable/improving
word choice are meant to track `ai_trend_direction` exactly; if a score
threshold is intentionally involved, document it, and fix the generation
prompt so the narrative's own wording never contradicts the structured field
it sits beside.

### 8.6 MEDIUM — generated activity-narrative text is not stable across captures, for most but not all records

Comparing the JSON payload's `ai_aim_xr_activity` text against the rendered
screen text for the same HCP:

**Matches exactly (2 of the 8 declining records checked):**

```
Leslie Lewis    "...consumption of competitor articles, particularly on
                 Competitor A clinical data." — identical on screen and payload
Wayne Lucas     "...no rep visits in the last 6 weeks." — identical
Leslie Whitney  "...related to Competitor A and Competitor B." — identical
Ardene Ballonado "...no significant competitor content consumption noted."
                 — identical
```

**Diverges in wording or substance (remainder checked):**

```
Marc Piper       payload: "...competitor articles read, particularly on
                  Competitor A clinical data."
                  screen:  "...competitor content consumption, particularly
                  Competitor A clinical articles."

Julia Derenzi    payload: "...no visits in the last 6 weeks."
                  screen:  "...no recent visits, indicating a lack of
                  engagement."

Leonid Frenkel   payload: "...indicating a shift in prescribing behavior."
                  screen:  clause dropped entirely; reworded without it.

Jacob Berman     payload: generic, no figures.
                  screen:  cites the specific "20.2%" score drop and names
                  "Product" by name — materially more specific than the
                  payload version.

Sohaib Jamil     payload: "...no significant competitor content consumption
                  noted."
                  screen:  "...a significant score improvement, indicating
                  positive digital engagement." — different claim entirely.

Gayleen Prausa   see §8.5 — also a trend-direction word mismatch, not just
                  phrasing.
```

**Reading.** Roughly half the records checked match exactly; the rest
diverge, ranging from light rewording to materially different claims
(Sohaib Jamil, Jacob Berman). This is the same class of finding documented for
competitive and HCP-awareness alerts in the Active Alerts register (§8.5
there) — generated text should not be treated as a fixed value once written
down, and a user quoting exact wording from an earlier screen may see
different wording on the next load without anything else about the HCP
having changed.

**Action.** Confirm whether this narrative is cached per HCP or regenerated
per request; if regenerated, decide whether that is intended, given at least
one case (Sohaib Jamil) where regeneration changed the claim, not just the
phrasing.

### 8.7 LOW — only the Declining segment of the list is internally ordered by severity

```
Declining segment    -31.9, -31.2, -24.8, -24.0, -23.8, -22.4, -20.2, -16.3
                      strictly ordered, worst first

Improving segment    +24.6, +18.6, +18.1, +20.4
                      not ordered by magnitude

Stable segment        +1.6, -2.4, -1.3
                      not ordered by magnitude
```

Not a functional defect since these two segments are not the ones a rep is
triaging by urgency, but worth noting: only the Declining group carries a
guaranteed severity ordering.

### 8.8 What reconciles correctly

Recorded so the failures above are not read as systemic.

- `ai_awareness_score`, `ai_trend_direction` (except the one narrative/colour
  disagreement in §8.5), `ai_score_change_pct`, and `ai_change_from_period`
  all reconcile exactly between payload and screen on every record checked.
- The territory-wide `awareness_trend` bar values match the payload exactly
  on all four periods.
- The arrow direction and sign convention (positive → up-arrow/green family,
  negative → down-arrow/red family) is applied consistently.
- Roughly half of the per-HCP narrative text matches verbatim between payload
  and screen (§8.6) — the mechanism is not uniformly unreliable, only
  inconsistently so.

The scoring and trend arithmetic is sound. The defects found are concentrated
in mislabeled UI (§8.1), a section heading that doesn't match its contents
(§8.3), descriptive copy that oversells the tab (§8.2), and generated-text
stability (§8.5, §8.6) — not in the underlying numbers.

---

## 9. OPEN ITEMS

### 9.1 Unresolved questions

1. Should the "PRESCRIBING PATTERNS" panel be renamed, or should
   `ai_icd10_prescribing_patterns` actually be populated and shown under it?
   (§8.1)
2. Should the "How it works" copy be tab-specific, dropping the
   competitive/payer/ICD-10 claims this tab's data does not support? (§8.2)
3. Should the "declining awareness" section be renamed, split, or filtered so
   it matches its own heading? (§8.3)
4. Is `ai_awareness_level` ever `Low` in a full, unfiltered payload? Not
   observed in the 15-record sample captured for this document.
5. Does this module's response include a `filters` block matching the
   platform-wide manager → employee → territory hierarchy? Not present in the
   captured sample — needs confirmation against a live capture with the
   filter panel actually exercised.
6. Is the per-HCP activity narrative cached or regenerated per request, and
   if regenerated, is Sohaib Jamil's case (§8.6, where regeneration changed
   the underlying claim, not just its wording) an isolated incident or
   systematic?
7. Is card colour keyed to `ai_trend_direction`, `ai_awareness_level`, an
   absolute score threshold, or some combination — and is Gayleen Prausa
   (§8.5) evidence of an unintended threshold effect or of a deliberate rule
   that simply isn't documented anywhere?

---

## 10. VOCABULARY

| Term | Meaning |
|---|---|
| **HCP** | Healthcare professional — prescriber or clinical staff |
| **Awareness score** | `ai_awareness_score` — the model's current 0–100% estimate of an HCP's product awareness |
| **Awareness level** | `ai_awareness_level` — banded classification of the current score (Medium / High observed) |
| **Trend direction** | `ai_trend_direction` — Declining / Stable / Improving, from linear regression across the four periods |
| **Change percentage** | `ai_score_change_pct` — signed movement from the baseline period, not period-over-period |
| **Baseline period** | `ai_change_from_period` — the fixed comparison point (Jan 29 in the captured sample), not a rolling window |
| **AIM XR activity** | `ai_aim_xr_activity` — generated narrative describing the HCP's apparent digital/content engagement |
| **Drift** | Loss of awareness or detailing engagement over time; shared vocabulary with Active Alerts, but a different number in each module — §2.6 |
| **PERT / EPI** | Pancreatic enzyme replacement therapy / exocrine pancreatic insufficiency |
| **MLR** | Medical, Legal and Regulatory review. Approved content only |
| **Period** | The reporting quarter in the data-reference panel, shared platform-wide |
| **Last refresh** | When the pipeline last calculated, shared platform-wide |

**Brand references are generalised by design.** Payloads use generic labels
("Product", "Competitor A", "Competitor B") in place of confidential product
and competitor names, exactly as in every other module on this platform —
reproduce the label exactly as given.


---

# PART 6 — COMPETITIVE INTEL

**Application:** Action Center — Launch & Market Defense · **Platform module:** Module 6 of 7

## 1. MODULE

| | |
|---|---|
| **Module name** | Competitive Intel |
| **Section heading, as displayed** | Competitive intelligence feeds |
| **Technique badge** | SIGNAL DETECTION |
| **Parent application** | Action Center |
| **Parent platform** | Veeva AI Insight 360 (UI shows "Insights 360™ V2") |
| **Position** | Tab 3 of 4 in Action Center; Module 6 of 7 on the platform |
| **Primary user** | Field sales representative |
| **Secondary user** | Sales manager (consolidated multi-territory view) |
| **Therapy context** | Pancreatic enzyme replacement therapy (PERT / EPI) |
| **Access model** | Role-based, derived from the authenticated session |
| **Write capability** | None. This tab has no action buttons of its own — see §3.4 |
| **Refresh cadence** | Batch; shares `last_refresh` with the rest of the platform |

**The question this module answers:** *what is a specific competitor doing in
my territory right now, and what do I say about it?*

Unlike Active Alerts' competitive stream (which is HCP-scoped — one card per
group of affected HCPs), this module is signal-scoped: one card per detected
competitive event — a rep-visit surge, a share gain, a new messaging or
starter-kit campaign — named by competitor brand and territory, with a
generated headline, summary, and counter-strategy.

**The module's own description, as shown on screen ("Real-time monitoring"):**

> AI tracks competitive messaging, market share shifts, and HCP sentiment
> across your territory. Powered by DATAstream™, Compass, and anomaly
> detection models.

This claims HCP sentiment tracking and names a tool ("Compass") that do not
appear anywhere in this module's own payload — see §8.5.

**The platform detects and drafts; the representative decides and acts.**
Counter-strategy text is decision support, not a verified, ready-to-use script
— see §7.5 for what may never be repeated verbatim to an HCP.

---

## 2. MODULE DETAILS

### 2.1 Position in the platform

```
Veeva AI Insight 360 — 7 modules
│
├── My Insights (RepStream)
│   ├── Territory Prioritization      existing writers, ranked by opportunity
│   ├── New Writer ID                 non-writers, conversion candidates
│   └── Objection Handler             what to say when pushed back on
│
└── Action Center — launch and market defence
    ├── Active Alerts                 threat feed, three streams
    ├── HCP Awareness                 per-HCP awareness score and trend
    ├── Competitive Intel           ← THIS MODULE — one card per competitive signal
    └── Payer Access                  formulary tiers and access risk
```

### 2.2 Sibling modules — routing reference

| Destination | Location | Holds | Route when user asks |
|---|---|---|---|
| **Active Alerts** | Action Center tab | The same class of competitive threat, but re-scoped to affected HCPs, with a counter-script and a "Deploy to Field" action | which HCPs are affected, deploy this, view affected HCPs |
| **HCP Awareness** | Action Center tab | Whether a given HCP's own awareness score is falling, independent of any one competitive signal | is this specific HCP going cold, awareness trend |
| **Payer Access** | Action Center tab | Whether a formulary change, not competitor activity, explains a share shift | is this a coverage issue, formulary, tier, prior auth |
| **Territory Prioritization** | RepStream tab | Whether the HCPs in this territory are ranked by prescribing opportunity | who should I visit, priority tier, Rx trend |
| **Objection Handler** | RepStream tab | What to say if an HCP raises a specific objection tied to this competitor | what do I say when, pushback, objection |

**This module and Active Alerts' competitive stream cover overlapping
ground from two different angles.** Active Alerts asks "which HCPs are
affected and what do I do with them"; this module asks "what is the
competitor doing and what's the strategic response." A user asking about a
named competitor's activity belongs here; a user asking which specific HCPs
to call belongs on Active Alerts (§2.2 there).

### 2.3 How a signal is produced

| Technique | Contribution |
|---|---|
| Direct signal read | Base record — competitor, territory, the two headline metrics |
| Rule-based threat scoring | `risk_level`, `urgency_level` |
| NLP classification | Signal type — surge, share gain, messaging campaign, formulary |
| Generative narrative | `headline`, `executive_summary`, `business_impact`, `recommended_actions`, `field_force_talking_points` |
| Stored counter-strategy | `counter_strategy` — see §8.1 for why this behaves differently from the other generated fields |

**Signals are colour-coded by `risk_level`** — red for High (Critical not
observed in this capture), orange for Medium, blue for Low — matching the
convention on the rendered feed dot.

### 2.4 Access scope

Same organisational hierarchy and session-derived scoping as the rest of the
platform (Territory Prioritization §4.3). No `filters` block was present in
the captured sample for this module specifically — flagged in §9.

### 2.5 One combined response, like HCP Awareness

This tab delivers its full signal list — and, per the module guide, a
"featured" variant capped at one signal per threat tier (max 3) — from a
single call. **The captured screens show only the full-list behaviour**; the
featured/capped variant was not observed and its rendering location on this
tab is unconfirmed (§9).

The response also carries a `total` count (5 in the captured sample, matching
the length of `items`). Where this total is displayed, if anywhere, was not
confirmed in the captured screens — §9.

### 2.6 Signal ordering is not a simple date sort

Signals are sorted by `risk_level` first (High before Medium before Low,
consistent across the captured list and the module guide's documented rule),
but **within a tier, ordering is not reliably date-descending**:

```
HIGH tier      SIG-003  2026-08-05   (newest first — correct)
               SIG-001  2026-08-04

MEDIUM tier    SIG-004  2026-07-31   ← older
               SIG-002  2026-08-03   ← newer, but listed second
```

See §8.6 for the concrete evidence and action.

### 2.7 Fields that exist only as generated prose, with no structured backing

`recommended_actions` and `field_force_talking_points` are each a 3-item
array with real content in the payload. Neither carries a structured
HCP-count, account-count, or metric field alongside it — when a talking point
or recommended action references a number ("top 5 cardiology HCPs," "9 HCP
accounts"), that number exists only inside the generated string, the same
caution documented for HCP Awareness's activity narrative (§7.4 there).
**This module has no per-signal HCP-count field at all** — unlike Active
Alerts' competitive stream, which carries `ai_affected_hcp_count` structurally.

---

## 3. FRONTEND — OVERVIEW AND KEYS

### 3.1 Application shell, data reference, KPI tiles, tab bar

Shared with Active Alerts and HCP Awareness — same shell, same data-reference
panel, same five KPI tiles (unchanged values across all three tabs in the
captured session), same four-tab bar with **Competitive Intel** as the third
tab, same yellow banner. None of these are specific to this module.

### 3.2 Section header

```
Competitive intelligence feeds                          [SIGNAL DETECTION]
```

### 3.3 "Real-time monitoring" panel

```
┌─ Real-time monitoring ─────────────────────────────────────────────────┐
│ AI tracks competitive messaging, market share shifts, and HCP sentiment │
│ across your territory. Powered by DATAstream™, Compass, and anomaly     │
│ detection models.                                                       │
└──────────────────────────────────────────────────────────────────────┘
```

Same tinted-callout convention as HCP Awareness's "How it works" panel.
Static descriptive copy, not sourced from this module's own response — see
§8.5 for what it claims that this module's payload does not support.

### 3.4 "Recent competitive activity" feed and signal anatomy

```
┌─ Recent competitive activity ──────────────────────────────────────────┐
│                                                                          │
│ ● Aug 5, 2026  [ANOMALY]                                                │
│   Competitor A Rx Spike Post-KOL Presentation Threatens Product...      │
│   <generated executive summary, 1-2 sentences>                          │
│   ┌ Counter-strategy available: <generated counter-strategy text> ──┐   │
│   └──────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│ ● Aug 4, 2026  [AI DETECTED]                                            │
│   ...                                                                   │
└──────────────────────────────────────────────────────────────────────┘
```

A vertical timeline — one entry per signal, newest-of-tier first (§2.6),
connected by a rule line down the left edge with a coloured dot per entry.

#### Signal entry elements

| Element | Position | Source | Notes |
|---|---|---|---|
| Dot colour | Left edge | `risk_level` | Red = High, orange = Medium, blue = Low |
| Date | Top left | `signal_date` | `Mon D, YYYY` |
| Type badge | Top, beside date | `signal_type` | Rendered verbatim — no re-wording, unlike Active Alerts' detection-method chip |
| Headline | Below date row, bold link style | `headline` | Not stable across captures — §8.2 |
| Body copy | Below headline | `executive_summary` | Not stable across captures — §8.2 |
| Counter-strategy callout | Card footer, tinted box | `counter_strategy` | **Stable across every capture checked — §8.1** |

**No action buttons, no expandable detail, and no impact-metrics panel are
present on this feed in the captured screens.** This is a materially simpler
card than either Active Alerts' competitive-alert card or its own
HCP-awareness card. See §8.3 for what the payload computes that never
reaches this feed.

---

## 4. BACKEND — KEY DETAILS

### 4.1 Data delivery

Delivered as a single list response, like HCP Awareness (§2.5 of that
document) rather than split across a summary and a detail call like Territory
Prioritization and Active Alerts.

### 4.2 Signal — field inventory (18 keys observed; module guide documents 16, not identical)

| Field | Type | Rendered | Notes |
|---|---|---|---|
| `signal_id` | string | No | e.g. `SIG-003` — join key, not shown |
| `signal_type` | string | Yes | Badge text, verbatim |
| `signal_date` | string | Yes | `YYYY-MM-DD` |
| `territory_id` | string | No | **Undocumented in the module guide** |
| `territory_name` | string | **No, not as a labelled field** | **Undocumented in the module guide.** Sometimes embedded inside a generated headline, inconsistently — §8.2 |
| `region` | null | No | `null` on every record observed |
| `competitor_brand` | string | Implied in generated text | "Competitor A" / "Competitor B" — governance-generalised brand label, see §7.5 |
| `rx_change_percent` | number | **No, not as a standalone figure** | Sometimes embedded in generated text, inconsistently — §8.2 |
| `activity_change_percent` | number | **No, not as a standalone figure** | Same — §8.2 |
| `territory_sales` | null | No | `null` on every record observed |
| `headline` | string | Yes | Generated. Diverged from the on-screen text on every one of 5 records checked — §8.2 |
| `executive_summary` | string | Yes | Generated. Same — §8.2 |
| `counter_strategy` | string | Yes | **Matched the on-screen text exactly on every one of 4 records checked with a visible counter-strategy line — §8.1** |
| `risk_level` | string | **No, not as text** | Drives dot colour only, §2.3 |
| `urgency_level` | string | **No** | Not rendered anywhere in the captured feed; see §8.4 for a case where the narrative's own tone contradicts this field |
| `business_impact` | string | **No** | Generated, present in payload, not observed rendered anywhere in the captured screens — §8.3 |
| `recommended_actions` | array of 3 strings | **No** | Same — §8.3 |
| `field_force_talking_points` | array of 3 strings | **No** | Same — §8.3 |

**`analysis_badges` is documented in the module guide (Table 8) as a 16th
key holding `AI_DETECTED` / `ML_TREND` / `ANOMALY`, but does not appear in the
captured payload at all.** Those same three values instead populate
`signal_type` directly — one field appears to be doing the job the guide
describes for two. See §8.7.

---

## 5. FRONTEND ↔ BACKEND MAPPING

### 5.1 Signal entry

| UI element | Payload field | Transform |
|---|---|---|
| Dot colour | `risk_level` | High → red, Medium → orange, Low → blue |
| Date | `signal_date` | Reformatted to `Mon D, YYYY` |
| Type badge | `signal_type` | Direct, no re-wording |
| Headline | `headline` | Direct, but not stable across loads — §8.2 |
| Body copy | `executive_summary` | Direct, but not stable across loads — §8.2 |
| Counter-strategy box | `counter_strategy` | Direct, and stable across loads — §8.1 |
| *(not rendered)* | `territory_name`, `rx_change_percent`, `activity_change_percent`, `risk_level` (as text), `urgency_level`, `business_impact`, `recommended_actions`, `field_force_talking_points` | §4.2, §8.3 |

### 5.2 Mapping notes and traps

**Only one of the four generated-text fields is safe to treat as a stable
identifier for a signal.** `counter_strategy` matched the screen exactly on
every record checked; `headline` and `executive_summary` did not match on
any of the five records checked. If regeneration is happening per request
(§8.1's leading hypothesis), `counter_strategy` behaves as though it is
stored once and reused, while `headline`/`executive_summary` behave as
though they are recomputed on each read.

**Roughly a third of this module's own generated fields never reach the
screen at all**, in the captured feed view — `business_impact`,
`recommended_actions`, and `field_force_talking_points`, seven pieces of
generated content per signal in total, are computed and shipped but not
displayed anywhere observed. Do not assume a user looking at this feed has
seen these — they have not, unless an unobserved detail view exists (§9).

**Numeric metrics are inconsistently folded into prose.** `rx_change_percent`
and `activity_change_percent` have no dedicated UI element; some headlines
embed a version of one of these numbers (SIG-002's screen headline reads
"Gains 3.1% Market Share," pulling from `rx_change_percent`), most do not.
Never assume a percentage is displayed just because the underlying field
exists — check the specific rendered text.

---

## 6. GRAPHICAL FLOW

### 6.1 Page lifecycle

```
   Rep opens Competitive Intel (Action Center, third tab)
                │
                ▼
   Territory scope resolved from the authenticated session
                │
                ▼
   Single list response: signals[] + total
                │
                ▼
   Sorted risk_level desc, then (inconsistently) by date within tier — §2.6
                │
                ▼
   Rendered as a vertical timeline feed — headline, summary,
   counter-strategy box per entry; no buttons, no expand
                │
                ▼
   Rep changes USERS or TERRITORY NAME
                │
                ▼
   Presses Apply ──► response refetches with the new scope
```

### 6.2 Signal detection pipeline

```
   SOURCE
   └── Competitive signal data (Rx and rep-activity deltas, per competitor,
       per territory)
                │
                ▼
   ┌────────────────────────────────────────────┐
   │  PROCESSING                                │
   │                                            │
   │  Rule-based scoring   → risk_level          │
   │                       → urgency_level       │
   │  NLP classification  → signal_type          │
   │  Generative narrative → headline            │
   │                       → executive_summary   │
   │                       → business_impact     │
   │                       → recommended_actions │
   │                       → field_force_talking_points │
   │  Stored / cached      → counter_strategy    │  ← behaves differently, §8.1
   └────────────────────────────────────────────┘
                │
                ▼
   Sort: risk_level desc, then date (not always strictly desc within tier)
                │
                ▼
   items[] + total  ──► rendered feed, partial field set only — §8.3
```

### 6.3 Ambiguity resolution — "what's the competitor doing to me"

```
        "what's the competitor doing"
                    │
        ┌───────────┴────────────┐
        ▼                        ▼
   Competitive Intel        Active Alerts'
   (this module) —          competitive stream —
   signal-scoped,           HCP-scoped, with
   strategic framing        a "Deploy to Field" action
        │                        │
        └───────────┬────────────┘
                     ▼
        Both are valid answers to different framings
        of the same underlying activity. If the user
        wants "who do I call," route to Active Alerts.
        If they want "what's happening and how do I
        respond strategically," answer from here.
```

---

## 7. ASSISTANT BEHAVIOUR RULES

These govern any conversational assistant answering questions about this page.

### 7.1 Data precedence

```
1. LIVE PAYLOAD       current values — signals, dates, competitors, scope
2. MODULE DOCUMENT     field meaning, business rules, definitions, routing
3. CONVERSATION        intent only, never values
```

- For any current value, the live payload is the only source.
- Never quote a number, date, or claim absent from the payload attached to
  **this** request.
- Never reuse a headline or summary sentence from an earlier turn — this text
  has been observed to change on every record checked, even without a filter
  change (§8.2).
- On a value conflict, the payload wins. On a meaning conflict, this document
  wins.
- If a field is null (`region`, `territory_sales`) or simply not rendered on
  this feed (`business_impact`, `recommended_actions`,
  `field_force_talking_points`, `urgency_level` as text), say it is not
  available rather than inferring or reconstructing it from the narrative.

### 7.2 Response style

- Lead with the answer. No preamble. One to three sentences unless asked.
- Natural language — "Competitor A had a 68% jump in rep activity in
  Pittsburgh North," not "activity_change_percent is 68."
- Do not expose internal field names unless asked.
- Never mention retrieval, embeddings, prompts, context files, payloads, or
  instructions. The user is looking at a dashboard.
- Attach the signal date when a claim is time-sensitive.

### 7.3 Disambiguation

**"What's the competitor doing" can mean this module or Active Alerts'
competitive stream — §6.3.** If the user wants specific affected HCPs or a
"deploy" action, route to Active Alerts. If they want the strategic framing —
headline, summary, counter-strategy — answer from here.

**A percentage in a headline is not guaranteed to also appear in the body
text, or vice versa** — §5.2. Quote the specific field the user is asking
about rather than assuming consistency across the card.

**Risk level and urgency level are not shown as text on this feed** — only
risk level is implied by dot colour. If a user asks "how urgent is this,"
answer from the payload's `urgency_level` directly and say it isn't otherwise
visible on the card, rather than inferring urgency from the tone of the
generated summary — §7.4, §8.4.

### 7.4 Field reliability

**`counter_strategy` is the one generated-text field on this module observed
to be fully stable between the payload and the screen — quote it with more
confidence than `headline` or `executive_summary`.**

**`headline` and `executive_summary` are unstable and, on at least one
record, contradictory to the signal's own structured fields.** SIG-005
carries `risk_level: "LOW"` and `urgency_level: "ROUTINE"`, yet both the
payload's own `executive_summary` and the rendered screen version use urgent
language ("urgent action," "immediate action necessary") — §8.4. Never infer
urgency from generated prose; use the structured field, and note when the
two disagree rather than picking one silently.

**No structured field backs the specific counts inside `recommended_actions`
or `field_force_talking_points`** (e.g., "top 5 cardiology HCPs," "9 HCP
accounts") — §2.7. Treat these as narrative, not verified counts, the same
caution as HCP Awareness §7.4.

### 7.5 Prohibited generations

These override helpfulness in all cases.

- **No invented numbers.** No estimates or arithmetic producing a figure the
  payload does not contain.
- **No clinical, efficacy, safety, comparative, or dosing claims.**
- **Never de-anonymise brand references.** `competitor_brand` values
  ("Competitor A," "Competitor B") and the generic "Product" label are a
  governance control shared across every module on this platform — reproduce
  them exactly as given, never substitute a real name.
- **No off-label content, under any framing.**
- **No medical advice**, and no opinion on what a prescriber should
  prescribe.
- **No presenting `counter_strategy`, `recommended_actions`, or
  `field_force_talking_points` as ready-to-use, MLR-approved copy** unless
  independently confirmed as such — this module does not carry the explicit
  MLR label that Objection Handler and Active Alerts' competitive
  counter-script do. Treat this content the same as any other generated
  field for purposes of what may be extended, paraphrased, or built upon.
- **No presenting model output as certainty.** Say "the model flagged," never
  "Competitor A is definitely gaining share."
- **No surfacing `business_impact`, `recommended_actions`, or
  `field_force_talking_points` as if the user had already seen them on their
  own screen.** They are computed but, per §8.3, not rendered on the feed the
  user is looking at — if the user asks, answer from the payload but note
  this content isn't visible on the card itself.

### 7.6 Behavioural protocols

| Situation | Response |
|---|---|
| User quotes a headline that doesn't match the current payload | Explain generated text is not guaranteed stable between loads (§8.2), matching the convention documented for Active Alerts and HCP Awareness; do not imply their memory was wrong |
| User asks how urgent a signal is and its narrative sounds urgent | Answer from `urgency_level` directly; flag if the narrative's tone disagrees (§8.4) |
| Answer is on another tab | Name the tab and what it holds (§2.2). Do not attempt the answer from this payload |
| User asks for the "business impact" or "talking points" for a signal | Answer from the payload fields directly; note they are not shown on the card itself (§8.3) |
| Uncertain | Say so. An unanswered question is recoverable; a confidently wrong figure in a regulated setting is not |

### 7.7 Output contract

Responses are validated before reaching the user and rejected if they contain
a numeric token absent from the live payload, a competitor or territory name
absent from the live payload, or a reference to internal system machinery.

### 7.8 Intent routing

| User intent | Source |
|---|---|
| what is this competitor doing in my territory | `headline` + `executive_summary`, flagged as narrative (§7.4) |
| how bad is this / how urgent | `risk_level`, `urgency_level` — not shown as text on the card, answer from payload |
| what do I say / how do I respond | `counter_strategy` — the more reliable generated field, §7.4 |
| what should I actually do, step by step | `recommended_actions` — computed but not on the card, §8.3 |
| what do I say to the HCP directly | `field_force_talking_points` — same caveat |
| how does this affect revenue / share | `business_impact` — same caveat |
| how many HCPs / accounts are involved | Not a structured field here — narrative only, §2.7; route to Active Alerts' competitive stream for a structured HCP count |
| which competitor, which territory | `competitor_brand`, and `territory_name` only where it happens to appear in generated text — §4.2 |
| when was this detected | `signal_date` |
| is this current | `last_refresh`, `period` — shared platform-wide |
| which HCPs specifically / deploy this | Active Alerts — §2.2, §6.3 |
| is this a coverage/formulary issue instead | Payer Access — §2.2 |
| is this one HCP's awareness declining | HCP Awareness — §2.2 |

### 7.9 What this module can and cannot answer

**Available:** for any listed signal — competitor, territory (where it
appears in generated text), date, headline and summary (with the reliability
caveat in §7.4), counter-strategy (reliable), and — from the payload directly,
even though not shown on the card — business impact, recommended actions,
and field-force talking points.

**Not available:** a structured HCP or account count for any signal;
confirmation of urgency or risk beyond what the payload states (dot colour
only conveys risk, not urgency); anything belonging to a sibling tab (§2.2);
any record change — the platform is read-only here; and, per §9, whether a
"featured" (top-1-per-tier) view or a per-signal detail/expand view exists
beyond the full feed captured for this document.

---

## 8. DATA QUALITY REGISTER

> **Internal section.** Contains named records and concrete figures. The
> constraints these defects impose are stated qualitatively in §7.3–§7.5.
> If any part of this document is used as machine-readable context, exclude
> section 8 — it contains exactly the values §7.5 forbids repeating as fact.

Ordered by severity.

### 8.1 HIGH — `counter_strategy` is fully stable; `headline` and `executive_summary` are not, on the same records

Checked against all five captured signals with a visible counter-strategy
line on screen:

```
                  headline match   executive_summary match   counter_strategy match
SIG-003 (Aug 5)        No                    No                       Yes
SIG-001 (Aug 4)        No                    No                       Yes
SIG-004 (Jul 31)       No                    No                       Yes
SIG-002 (Aug 3)        No                    No                       Yes
SIG-005 (Aug 2)        No                    No             (not captured on screen)
```

Zero of five headlines and zero of five summaries match verbatim between the
payload and the rendered screen; four of four counter-strategy lines checked
match exactly, character for character.

**Reading.** This is a cleaner split than the same pattern observed on Active
Alerts and HCP Awareness (where some records matched and some didn't within
the same field). Here the split is by *field*, not by record — every
`counter_strategy` matches, no `headline` or `executive_summary` does. The
most likely explanation is that `counter_strategy` is stored once (from a
rules-based or cached source) while `headline` and `executive_summary` are
regenerated by GPT-4o on each read.

**Action.** Confirm the generation architecture directly. If
`headline`/`executive_summary` are intentionally regenerated per request,
document that so no downstream consumer treats them as fixed; if not
intentional, cache them the same way `counter_strategy` evidently is.

### 8.2 HIGH — generated text sometimes drops, and sometimes preserves, the specific figures in the underlying signal

```
SIG-001   payload executive_summary cites "68% increase," "declining by 4.2%"
          screen executive_summary drops both figures entirely, using only
          "significantly ramped up" / "potentially impacting"

SIG-004   payload executive_summary: "nine target HCP accounts"
          screen executive_summary: "across 9 HCP accounts"
          — the count is preserved (in numeral form) despite the wording
          otherwise diverging (§8.1's general pattern)

SIG-002   screen headline adds "3.1%" (not present in the payload's own
          headline, though it appears in the payload's own
          executive_summary and in rx_change_percent); the screen's own
          executive_summary for the same signal then omits any percentage
          — the figure appears in one part of the card but not the other
```

**Reading.** Regeneration is not uniformly lossy or additive — it drops a
concrete figure entirely on one record (SIG-001) and reproduces it correctly
on another (SIG-004), and on a third (SIG-002) the figure appears in one part
of the same card but not another. A rep cannot rely on a headline and its own
body text agreeing on whether a number is present at all.

**Action.** If precision (68%, 4.2%, 9 accounts) matters for field messaging,
move it out of free-text generation and into a structured, always-rendered
field, consistent with the recommendation for HCP Awareness §8.6.

### 8.3 HIGH — three fields of generated content, plus explicit risk/urgency text, are computed but not rendered anywhere in the captured feed

Every signal's payload includes `business_impact` (a full sentence),
`recommended_actions` (3 items), and `field_force_talking_points` (3 items) —
21 discrete pieces of generated content across the 5 captured signals. None
of it appears anywhere in the "Recent competitive activity" feed on any of
the three captured screens. `risk_level` and `urgency_level` are likewise
absent as text — only `risk_level` is conveyed indirectly through dot colour.

**This has not been confirmed as a permanent gap** — an unobserved
click-through or expand view could plausibly surface this content, and none
of the captured screens shows an expand affordance to rule that out (§9).

**Action.** Confirm whether a detail view exists. If not, either surface this
content (it is already being generated and paid for) or stop generating it,
since unused generation is wasted compute with no user-facing value.

### 8.4 HIGH — a LOW-risk, ROUTINE-urgency signal is narrated with urgent language, in both the payload and the screen

SIG-005: `risk_level: "LOW"`, `urgency_level: "ROUTINE"`.

Payload `executive_summary`: "...posing a **significant threat**. **Urgent
action is needed** to counteract their influence..."

Screen `executive_summary` (independently regenerated, per §8.1): "...
indicating potential market share loss. **Immediate action is necessary** to
counteract this trend..."

Both the stored/original generation and the regenerated screen version use
urgency language ("significant threat," "urgent action," "immediate action")
for a signal the structured fields classify as the lowest risk and least
urgent tier available. This is not a one-off regeneration artefact — it
persists across both captures, meaning the generation prompt itself is not
adequately conditioned on `risk_level`/`urgency_level` when producing the
summary tone.

**Action.** Constrain the summary-generation prompt to match tone to
`risk_level`/`urgency_level`, and add a post-generation check that flags
mismatches between narrative urgency language and the structured tier before
the content ships.

### 8.5 MEDIUM — the "Real-time monitoring" panel claims capabilities this module's data does not support

On-screen text: "AI tracks competitive messaging, market share shifts, and
**HCP sentiment** across your territory. Powered by DATAstream™, **Compass**,
and anomaly detection models."

Checked against the module's own 18-key field inventory (§4.2): there is no
sentiment field, sentiment-related array, or any field resembling one. There
is likewise no reference to "Compass" anywhere else in this module or any
sibling module document. Compare to the equivalent finding on HCP Awareness
(§8.2 there), where "How it works" copy similarly oversold ICD-10 tracking
that field never populates.

**Action.** Either implement HCP-sentiment tracking and surface it as a real
field, or remove the claim from the panel copy. Document what "Compass"
refers to, or remove the reference if it names a tool this module does not
actually use.

### 8.6 MEDIUM — sort order is not strictly date-descending within a risk tier

```
              risk tier    date          screen position
SIG-003       HIGH          2026-08-05    1st
SIG-001       HIGH          2026-08-04    2nd   (correct: newer HIGH first)
SIG-004       MEDIUM        2026-07-31    3rd
SIG-002       MEDIUM        2026-08-03    4th   ← older signal (SIG-004) is
                                                    listed before a newer one
                                                    (SIG-002) in the same tier
SIG-005       LOW           2026-08-02    5th
```

The primary sort (risk tier) is correct and matches the module guide's
documented rule. The secondary sort, within a tier, is correct for the HIGH
group but inverted for the MEDIUM group.

**Action.** Confirm the intended secondary sort key (most likely
`signal_date` descending) and apply it consistently across every tier.

### 8.7 MEDIUM — `analysis_badges` is documented but absent; `signal_type` appears to absorb its role

The module guide documents a 16th key, `analysis_badges`, holding exactly the
value set `AI_DETECTED` / `ML_TREND` / `ANOMALY`. No such field exists in the
captured payload. `signal_type` carries precisely those same three values on
every record observed, and is the only field rendered as the on-screen type
badge.

**Action.** Reconcile the module guide against the implementation: either
`analysis_badges` was consolidated into `signal_type` and the guide should
say so, or `analysis_badges` is genuinely missing and should be restored.

### 8.8 LOW — inconsistent trailing punctuation in generated headlines, present in the payload itself

```
SIG-003   "...Threatens Product Share."       trailing period
SIG-005   "...New GI Fellows in San Francisco." trailing period
SIG-001   "...Product Market Position in Pittsburgh North PA"   no period
SIG-004   "...Launching Starter Kits in Key Accounts"            no period
SIG-002   "...Gains Market Share in Pittsburgh North PA Region"  no period
```

Minor, but worth a single generation post-process pass for consistency.

### 8.9 What reconciles correctly

Recorded so the failures above are not read as systemic.

- `signal_date`, `signal_type` (rendered verbatim, no re-wording), and dot
  colour (driven by `risk_level`) all reconcile exactly between payload and
  screen on every one of the five signals checked.
- `territory_id` values correctly correlate to the same territory names
  documented elsewhere on the platform (`A0E000000013068` → San Francisco CA,
  `A0E000000013065` → Pittsburgh North PA), consistent with the filters
  example in the Active Alerts module document.
- The primary risk-tier sort (High before Medium before Low) is applied
  correctly across the full list.
- `counter_strategy` is completely stable — §8.1.
- Where a specific figure survives into generated text at all, it has been
  observed numerically correct against the underlying field (SIG-004's "9").

The detection and scoring logic behind each signal appears sound. The
defects found are concentrated in generation-text stability and
tone-consistency (§8.1, §8.2, §8.4), unused generated content (§8.3), a
documentation/schema mismatch (§8.7), and a secondary sort bug (§8.6) — not
in the underlying risk classification or metrics.

---

## 9. OPEN ITEMS

### 9.1 Unresolved questions

1. Does an expand/detail view exist for a signal, surfacing
   `business_impact`, `recommended_actions`, and `field_force_talking_points`?
   None of the three captured screens shows an affordance for one. (§8.3)
2. Where, if anywhere, does the `total` field (5 in the captured sample)
   render on this tab? Not observed in the captured screens.
3. Is `headline`/`executive_summary` intentionally regenerated per request
   while `counter_strategy` is cached, or is the stability difference an
   accident of the current implementation? (§8.1)
4. Does the "featured" (top-1-per-tier, max 3) variant documented in the
   module guide render anywhere on this tab, or only the full list captured
   here?
5. Does this module's response include a `filters` block matching the
   platform-wide manager → employee → territory hierarchy? Not present in
   the captured sample.
6. Was `analysis_badges` deliberately folded into `signal_type`, or is it a
   genuine gap against the documented contract? (§8.7)
7. What does "Compass," named in the on-screen "Real-time monitoring" copy,
   refer to? Not documented anywhere else across the platform's module
   documents. (§8.5)

---

## 10. VOCABULARY

| Term | Meaning |
|---|---|
| **Signal** | One detected competitive event — the unit this module is scoped to, distinct from an HCP or an alert |
| **Competitor brand** | `competitor_brand` — "Competitor A" / "Competitor B," a governance-generalised label, never a real name |
| **Risk level** | `risk_level` — HIGH / MEDIUM / LOW (Critical not observed); drives dot colour only, not shown as text |
| **Urgency level** | `urgency_level` — IMMEDIATE / STANDARD / ROUTINE; not rendered anywhere in the captured feed |
| **Counter-strategy** | `counter_strategy` — the one generated-text field observed to be fully stable across captures |
| **Executive summary** | `executive_summary` — generated narrative body text; not stable across captures |
| **Business impact** | `business_impact` — generated revenue/share framing; computed but not observed rendered on the feed |
| **Talking points** | `field_force_talking_points` — 3 generated conversation points; same caveat |
| **Recommended actions** | `recommended_actions` — 3 generated next steps; same caveat |
| **MSL** | Medical Science Liaison — referenced in some counter-strategy text as a resource a rep can request |
| **KOL** | Key Opinion Leader — a physician of outsized influence, referenced in SIG-003's signal |
| **PERT / EPI** | Pancreatic enzyme replacement therapy / exocrine pancreatic insufficiency |
| **Period** | The reporting quarter in the data-reference panel, shared platform-wide |
| **Last refresh** | When the pipeline last calculated, shared platform-wide |

**Brand references are generalised by design.** Payloads use generic labels
("Product", "Competitor A", "Competitor B") in place of confidential product
and competitor names, exactly as in every other module on this platform —
reproduce the label exactly as given.


---

# PART 7 — PAYER ACCESS

**Application:** Action Center — Launch & Market Defense · **Platform module:** Module 7 of 7

## 1. MODULE

| | |
|---|---|
| **Module name** | Payer Access |
| **Section heading, as displayed** | Payer access monitoring |
| **Technique badge** | REAL-TIME TRACKING |
| **Parent application** | Action Center |
| **Parent platform** | Veeva AI Insight 360 (UI shows "Insights 360™ V2") |
| **Position** | Tab 4 of 4 in Action Center; Module 7 of 7 on the platform |
| **Primary user** | Field sales representative |
| **Secondary user** | Sales manager (consolidated multi-territory view) |
| **Therapy context** | Pancreatic enzyme replacement therapy (PERT / EPI) |
| **Access model** | Role-based, derived from the authenticated session |
| **Write capability** | None. "View Action Plan" opens generated content, it does not edit a record |
| **Refresh cadence** | Batch; shares `last_refresh` with the rest of the platform |

**The question this module answers:** *what is my formulary access situation
with every major payer in my territory — not just the ones that changed?*

Unlike Active Alerts' payer stream, which surfaces only payers with a
detected tier change, **this module lists every major payer, changed or
not** — one card per payer, with its current tier, whether it changed, and,
for changed payers, an impact assessment and an action plan.

**The module's own description, as shown on screen ("Real-time payer
intelligence"):**

> AI tracks formulary changes, prior authorization requirements, and tier
> shifts across all major payers in your territory.

This is an accurate description of what the payload actually contains — a
contrast with the equivalent panels on HCP Awareness and Competitive Intel,
both of which claim capabilities their own payloads do not support. This
module's own PA-required *rendering*, however, has a serious accuracy defect
of a different kind — see §8.1.

**The platform detects and drafts; the representative decides and acts.**
Action-plan and PA-bridge text is decision support, not a verified script —
see §7.5.

---

## 2. MODULE DETAILS

### 2.1 Position in the platform

```
Veeva AI Insight 360 — 7 modules
│
├── My Insights (RepStream)
│   ├── Territory Prioritization      existing writers, ranked by opportunity
│   ├── New Writer ID                 non-writers, conversion candidates
│   └── Objection Handler             what to say when pushed back on
│
└── Action Center — launch and market defence
    ├── Active Alerts                 threat feed, three streams
    ├── HCP Awareness                 per-HCP awareness score and trend
    ├── Competitive Intel             one card per competitive signal
    └── Payer Access                ← THIS MODULE — every major payer, changed or not
```

### 2.2 Sibling modules — routing reference

| Destination | Location | Holds | Route when user asks |
|---|---|---|---|
| **Active Alerts** | Action Center tab | Only the payers with a detected tier change, re-framed as an alert with resources and buttons | the alert version of a payer change, resources, deploy this |
| **HCP Awareness** | Action Center tab | Whether a formulary change is coinciding with a given HCP's falling awareness | is this HCP's drop tied to coverage |
| **Competitive Intel** | Action Center tab | Whether a competitor's activity, not a payer's tier change, explains a share shift | what is the competitor doing |
| **Territory Prioritization** | RepStream tab | Whether the HCPs behind an affected payer are ranked by prescribing opportunity | who should I visit, priority tier |
| **Objection Handler** | RepStream tab | What to say if an HCP raises cost or coverage as an objection | what do I say when, pushback, objection |

**This module is the full picture; Active Alerts' payer stream is the
subset that changed.** A user asking about a payer that has *not* changed —
"what's my status with Tricast" — cannot be answered from Active Alerts at
all; it belongs here. A user asking "what changed this week" can be answered
from either, but this module's own alert-tier cards carry richer content
(a full action plan, projected patient impact) than the Active Alerts
version of the same event.

### 2.3 How the impact assessment is produced

| Technique | Contribution |
|---|---|
| Direct payer record read | Base fields — tier, PA requirement, covered lives, affected HCPs |
| Rule-based scoring | `ai_impact_score`, `ai_impact_level`, `ai_tier_change_direction` |
| Predictive model | `ai_abandonment_risk_pct`, `ai_projected_patient_impact` — only populated for payers with a detected change |
| NLP classification | `ai_nlp_action_category`, `ai_nlp_urgency`, `ai_nlp_keywords` |
| Generative narrative | `ai_impact_summary`, `ai_action_plan`, `ai_pa_bridge_note`, `view_action_plan` |

**Only changed payers get the full generative treatment.** Every field in
the last two rows is populated for the three `AI_ALERT` payers in the
captured sample; for the five `STABLE` payers, `ai_impact_summary` and
`ai_pa_bridge_note` are `null`, and `ai_abandonment_risk_pct` /
`ai_projected_patient_impact` are `null` for four of the five (the fifth,
the one stable-but-recently-upgraded payer, also carries nulls here — §2.6).
This is a clean, structural distinction, not a data gap — see §8.4 for a
related but separate observation about how the generated text itself differs
between the two groups.

### 2.4 Access scope

Same organisational hierarchy and session-derived scoping as the rest of the
platform.

### 2.5 One combined response, like HCP Awareness and Competitive Intel

This tab delivers the full payer list and the rollup counts together, in one
response — not split across a summary and a detail call.

### 2.6 The `STABLE` status label covers two genuinely different situations

`status_badge` has two observed values: `AI_ALERT` and `STABLE`. But
`STABLE` is not synonymous with "nothing changed":

```
STABLE + ai_tier_change_direction UNCHANGED   4 payers — genuinely static
STABLE + ai_tier_change_direction UPGRADE     1 payer  — Superior Health Plan TX,
                                                          tier improved Aug 10, 2026,
                                                          change_badge = CHANGE_DETECTED
```

A payer whose tier *improved* is still labelled `STABLE`, not `AI_ALERT` —
consistent with `AI_ALERT` meaning "risk requiring attention," not "any
change." But this produces a card that carries both a `STABLE` status and a
`CHANGE_DETECTED` change badge simultaneously, and the rendered card handles
that combination differently from every other record — §8.5.

### 2.7 Rollup counts, and what they include

| Field | Meaning | Captured value |
|---|---|---|
| `total` | All payers in scope, changed or not | 8 |
| `ai_alert_count` | Payers currently flagged | 3 |
| `ai_stable_count` | Payers not flagged, including the one upgrade | 5 |
| `ai_tier_downgrade_count` | Payers whose direction is `DOWNGRADE` specifically | 3 |
| `ai_high_impact_count` | Payers at `ai_impact_level: "High"` | 0 |
| `ai_total_covered_lives_at_risk` | Sum of `covered_lives` **for alerted payers only** | 530,000 |
| `ai_total_affected_hcps` | Sum of `affected_hcp_count` **for alerted payers only** | 27 |

**The last two are alert-scoped sums, not territory-wide totals.** Do not
answer "how many covered lives are in my territory" with
`ai_total_covered_lives_at_risk` — it excludes the five stable payers
entirely (a combined 1,024,000 more covered lives in the captured sample).
It answers specifically "how many lives are exposed to a currently-alerted
tier change."

---

## 3. FRONTEND — OVERVIEW AND KEYS

### 3.1 Application shell, data reference, KPI tiles, tab bar

Shared with the other three Action Center tabs — same shell, same
data-reference panel, same five KPI tiles, same banner, same four-tab bar
with **Payer Access** as the fourth and final tab.

### 3.2 "Real-time payer intelligence" panel

```
┌─ Real-time payer intelligence ─────────────────────── [REAL-TIME TRACKING]
│ AI tracks formulary changes, prior authorization requirements, and tier
│ shifts across all major payers in your territory.
└──────────────────────────────────────────────────────────────────────────
```

Same tinted-callout convention as the other three tabs. Unlike HCP Awareness
§8.2 and Competitive Intel §8.5, this copy is accurate to what the payload
actually contains.

### 3.3 Payer card grid — two card variants, plus one hybrid

Two-column grid, ordered `AI_ALERT` payers first (impact score descending),
then `STABLE` payers (impact score descending) — this ordering reconciles
exactly with the payload on every record checked (§8.8).

#### Variant A — alert / changed payer

```
┌────────────────────────────────────────────────────┐
│ MM INDUSTRIES                            [AI ALERT] │
│ Covered lives: 156,000            [CHANGE DETECTED] │
│ ┌─ RECENT CHANGE ───────────────────────────────┐   │
│ │ Tier 2 → Tier 3                                │   │
│ │ Effective: Aug 6, 2026                          │   │
│ └─────────────────────────────────────────────────┘  │
│ Affected HCPs: 8                                     │
│ Impact: Medium –                                     │
│ [ View Action Plan ]                                 │
└────────────────────────────────────────────────────┘
```

#### Variant B — stable payer

```
┌────────────────────────────────────────────────────┐
│ MVP HEALTH CARE NY HIX                     [STABLE] │
│ Covered lives: 67,000                                │
│ ┌─ CURRENT STATUS ──────────────────────────────┐   │
│ │ Tier 2 – Standard                               │   │
│ └─────────────────────────────────────────────────┘  │
│ PA required: Yes                                     │
└────────────────────────────────────────────────────┘
```

No button, no "Affected HCPs" line, no "Impact" line on this variant.

#### The hybrid — Superior Health Plan TX

```
┌────────────────────────────────────────────────────┐
│ SUPERIOR HEALTH PLAN TX             [CHANGE DETECTED]│  ← not [STABLE]
│ Covered lives: 124,000                                │
│ ┌─ RECENT CHANGE ───────────────────────────────┐    │  ← Variant A's box,
│ │ Tier 3 → Tier 2                                │    │    not "CURRENT STATUS"
│ │ Effective: Aug 10, 2026                         │    │
│ └─────────────────────────────────────────────────┘   │
│ PA required: Yes                                      │  ← Variant B's field,
│                                                        │    no Affected HCPs / Impact
└────────────────────────────────────────────────────┘
```

Distinct light-green tint (not Variant A's orange/pink, not Variant B's
plain white). This is the only record in the captured sample carrying
`status_badge: "STABLE"` alongside a non-null `change_badge`, and it is the
only `UPGRADE`-direction record. See §8.5 for the badge-source anomaly this
produces.

#### Card elements

| Element | Source | Notes |
|---|---|---|
| Payer name | `payer_name` | |
| Top-right badge | `status_badge` normally; **`change_badge` for the hybrid record** | §8.5 |
| Covered lives | `covered_lives` | Comma-formatted |
| Inline "CHANGE DETECTED" pill | `change_badge` | Only on records where it is non-null |
| "RECENT CHANGE" box | `tier_previous` → `tier_current`, `change_date` | Variant A and the hybrid only |
| "CURRENT STATUS" box | `tier_current` – `tier_label_current` | Variant B only |
| Affected HCPs | `affected_hcp_count` | **Variant A only** — present in the payload for every payer, rendered only on this variant |
| Impact | `ai_impact_level`, suffixed with a bare dash | Variant A only — §8.6 |
| PA required | `pa_required` | **Variant B and the hybrid only. Rendered incorrectly for 4 of 5 records — §8.1** |
| View Action Plan button | Opens `view_action_plan` (unconfirmed which field — §9) | Variant A only |

---

## 4. BACKEND — KEY DETAILS

### 4.1 Data delivery

Delivered as a single list response — payer items, `total`, and six rollup
counts (§2.7) together, consistent with the single-response pattern on HCP
Awareness and Competitive Intel.

### 4.2 Payer item — field inventory (25 keys observed; module guide documents 22, not identical)

| Field | Type | Rendered | Notes |
|---|---|---|---|
| `plan_id` | string | No | Join key |
| `payer_name` | string | Yes | |
| `mco_org_name` | string | No | Parent MCO — never shown as a distinct label, but see §8.2 for why its accuracy still matters |
| `channel_name` | string | No | `"Commercial"` on every record observed; not rendered, but see §8.3 |
| `tier_current` | string | Yes | Inside the change/status box |
| `tier_previous` | string | Yes | Change box only |
| `tier_label_current` | string | Yes | Status box only ("Tier 2 – Standard") |
| `change_date` | string or null | Yes | Change box only; `null` for unchanged payers |
| `pa_required` | string ("Yes"/"No") | Yes, incorrectly for most | §8.1 |
| `covered_lives` | integer | Yes | |
| `affected_hcp_count` | integer | Yes, alert cards only | Present for every payer, rendered only for the 3 alert cards |
| `status_badge` | string | Yes, except one record | §8.5 |
| `change_badge` | string or null | Yes, where non-null | |
| `ai_impact_score` | number | **No** | Never rendered as a number anywhere — §8.6 |
| `ai_impact_level` | string | Yes | Alert cards only |
| `ai_tier_change_direction` | string | **No, not as text** | DOWNGRADE / UPGRADE / UNCHANGED — implied only through the tier arrow in the change box |
| `ai_abandonment_risk_pct` | number or null | **No** | Not observed rendered anywhere |
| `ai_projected_patient_impact` | number or null | **No** | Not observed rendered anywhere |
| `ai_nlp_action_category` | string | **No** | Not observed rendered anywhere |
| `ai_nlp_urgency` | string | **No** | Not observed rendered anywhere |
| `ai_nlp_keywords` | array of strings | **No** | Not observed rendered anywhere |
| `ai_impact_summary` | string or null | **No** | Not observed rendered anywhere; presumed candidate for the action-plan detail view — §9 |
| `ai_action_plan` | array (alert payers) or string (stable payers) | **No, not directly** | **Type differs by record; diverges in wording from `view_action_plan` on alert payers — §8.4** |
| `ai_pa_bridge_note` | string or null | **No** | Not observed rendered anywhere |
| `view_action_plan` | string | Presumed, via button | **Undocumented as "NEW key" in the module guide; diverges from `ai_action_plan` on alert payers — §8.4** |
| `analysis_badges` | array of strings | No | Not shown as chips; undercounts techniques actually applied on some records — §8.7 |
| `ai_is_flagged` | boolean | No | Redundant with `status_badge == "AI_ALERT"` on every record checked |

**Documented in the module guide (Table 10) but absent from the payload:**
`recommended_action` (singular) — no such key exists; the closest analogues
are the two diverging fields `ai_action_plan` and `view_action_plan`, neither
matching the documented description exactly.

---

## 5. FRONTEND ↔ BACKEND MAPPING

### 5.1 Card fields

| UI element | Payload field | Transform |
|---|---|---|
| Payer name | `payer_name` | Direct |
| Top-right badge (normal case) | `status_badge` | AI_ALERT / STABLE, direct |
| Top-right badge (hybrid record) | `change_badge`, not `status_badge` | §8.5 |
| Covered lives | `covered_lives` | Comma-formatted |
| Change box tier line | `tier_previous`, `tier_current` | "X → Y" |
| Change box date | `change_date` | "Effective: Mon D, YYYY" |
| Status box | `tier_current`, `tier_label_current` | "Tier N – Label" |
| Affected HCPs | `affected_hcp_count` | Alert cards only |
| Impact line | `ai_impact_level` | Suffixed with a bare dash, no number — §8.6 |
| PA required | `pa_required` | **Not reliably sourced — renders "Yes" on 4 of 5 stable/hybrid records regardless of the actual field value — §8.1** |

### 5.2 Mapping notes and traps

**`pa_required` cannot currently be trusted from the screen.** Check the
payload directly whenever a user asks whether prior authorization is
required for a specific payer — §8.1.

**`ai_action_plan` and `view_action_plan` are not interchangeable, and their
relationship depends on whether the payer is alerted.** For the 5 stable
payers they are byte-identical. For the 3 alert payers they diverge in
wording, framing, and even structure (numbered array vs single paragraph) —
§8.4. If the user asks "what's the action plan," prefer `view_action_plan`
since it is the one more plausibly tied to the button the user actually
sees, but note that a different, non-identical version exists in
`ai_action_plan` for alert payers.

**Never assert a payer's parent MCO or channel from generated text alone.**
Generated action-plan text has been observed naming a materially different
MCO than the record's own `mco_org_name` (§8.2) and referencing a government
payer population inconsistent with the record's own `channel_name` (§8.3).
The structured fields are correct; the generated text is not always
grounded in them.

---

## 6. GRAPHICAL FLOW

### 6.1 Page lifecycle

```
   Rep opens Payer Access (Action Center, fourth tab)
                │
                ▼
   Territory scope resolved from the authenticated session
                │
                ▼
   Single list response: items[] + total + 6 rollup counts
                │
                ▼
   Sorted: AI_ALERT payers first, then STABLE — both groups by
   impact score descending (reconciles exactly — §8.8)
                │
        ┌───────┴────────┐
        ▼                ▼
  Variant A cards    Variant B cards        (+ 1 hybrid card, §3.3)
  (alert/changed)    (stable)
        │
        ▼
   [View Action Plan] clicked
        │
        ▼
   Opens generated content — exact source field unconfirmed (§9)
       │
       ▼
   Rep changes USERS or TERRITORY NAME
        │
        ▼
   Presses Apply ──► response refetches with the new scope
```

### 6.2 Impact assessment pipeline

```
   SOURCE
   └── Payer formulary records — tier history, PA requirement, covered
       lives, affected HCPs
                │
                ▼
   ┌────────────────────────────────────────────┐
   │  PROCESSING                                │
   │                                            │
   │  Rule-based scoring   → ai_impact_score     │
   │                       → ai_impact_level     │
   │                       → ai_tier_change_direction │
   │  Predictive model     → ai_abandonment_risk_pct    (alerted only)
   │                       → ai_projected_patient_impact (alerted only)
   │  NLP classification   → ai_nlp_action_category      (all payers)
   │                       → ai_nlp_urgency
   │                       → ai_nlp_keywords
   │  Generative narrative → ai_impact_summary    (alerted only)
   │                       → ai_action_plan        ← diverges from the next
   │                       → view_action_plan      ← field, alerted only §8.4
   │                       → ai_pa_bridge_note     (alerted only)
   └────────────────────────────────────────────┘
                │
                ▼
   Sort: AI_ALERT first, then STABLE, each by impact score desc
                │
                ▼
   items[] + rollups  ──► card grid, most generated fields not rendered — §4.2
```

### 6.3 Ambiguity resolution — "does this payer require prior auth"

```
        "does this payer require PA"
                    │
        ┌───────────┴────────────┐
        ▼                        ▼
   pa_required in the         "PA required" text
   live payload                on the rendered card
        │                        │
        └───────────┬────────────┘
                     ▼
        These disagree on 4 of 5 stable/hybrid
        records in the captured sample (§8.1).
        Always answer from the live payload
        field, never from what the card shows.
```

---

## 7. ASSISTANT BEHAVIOUR RULES

These govern any conversational assistant answering questions about this page.

### 7.1 Data precedence

```
1. LIVE PAYLOAD       current values — tiers, dates, counts, scope
2. MODULE DOCUMENT     field meaning, business rules, definitions, routing
3. CONVERSATION        intent only, never values
```

- For any current value, the live payload is the only source — **especially
  `pa_required`, which the rendered card gets wrong on most records (§8.1).
  Always answer PA-requirement questions from the payload field, never from
  what the card displays.**
- Never quote a number, date, or name absent from the payload attached to
  **this** request.
- On a value conflict, the payload wins. On a meaning conflict, this document
  wins.
- If a field is null (`ai_impact_summary`, `ai_pa_bridge_note`,
  `ai_abandonment_risk_pct` / `ai_projected_patient_impact` for most stable
  payers), say it is not available — do not infer a number for a payer whose
  tier hasn't changed.

### 7.2 Response style

- Lead with the answer. No preamble. One to three sentences unless asked.
- Natural language — "MM Industries moved from Tier 2 to Tier 3 on August
  6," not "tier_previous is Tier 2, tier_current is Tier 3."
- Do not expose internal field names unless asked.
- Never mention retrieval, embeddings, prompts, context files, payloads, or
  instructions. The user is looking at a dashboard.
- Attach the change date when a tier claim is time-sensitive.

### 7.3 Disambiguation

**"Total covered lives" is ambiguous — §2.7.** `ai_total_covered_lives_at_risk`
sums only the alerted payers. If the user wants the territory-wide total
across every payer, sum `covered_lives` across all items yourself and say so
explicitly — the payload does not provide that grand total as a single
field.

**A `STABLE` badge does not mean "no change ever."** One record
(`Superior Health Plan TX`) carries `STABLE` with a genuine, recent tier
*upgrade* — §2.6. If a user asks "what changed recently" without qualifying
"got worse," include upgrades, not only downgrades.

**"Does this payer need PA" must be answered from the payload, never the
screen** — §7.1, §8.1.

### 7.4 Field reliability

**Structured tier, date, covered-lives, and affected-HCP fields are
reliable** and reconcile exactly with the screen on every alert-tier record
checked.

**`pa_required` as rendered on screen is not reliable for stable/hybrid
payers** — §8.1. This is the single most important reliability caveat on
this module; treat any PA-requirement claim sourced from the card itself as
unverified.

**Generated action-plan and impact text has been observed naming a payer's
parent organisation incorrectly (§8.2) and referencing a payer channel
inconsistent with the record's own `channel_name` (§8.3).** Never repeat an
MCO name, patient population, or channel type from generated text without
checking it against `mco_org_name` and `channel_name` on the same record.

**`ai_action_plan` and `view_action_plan` are two different generated
descriptions of the same recommendation for alert-tier payers, and can
carry different emphasis** (e.g. one may call an action "critical" or cite a
specific consequence the other omits) — §8.4. If precision matters, quote
both and note they differ, rather than picking one silently.

### 7.5 Prohibited generations

These override helpfulness in all cases.

- **No invented numbers.** No estimates or arithmetic producing a figure the
  payload does not contain.
- **No clinical, efficacy, safety, comparative, or dosing claims.**
- **Never de-anonymise brand references.** The generic "Product" label is a
  governance control shared across every module — reproduce it exactly.
  Payer and MCO names in this module, by contrast, are real entities, not
  generalised — but see §8.2 for a case where the generated text names the
  *wrong* real entity, which is a factual-accuracy problem, not a governance
  one.
- **No off-label content, under any framing.**
- **No medical advice.**
- **No asserting a PA requirement to a user without checking the live
  payload field first** — §7.1, §8.1.
- **No presenting `ai_action_plan`, `view_action_plan`, or `ai_pa_bridge_note`
  as ready-to-use, MLR-approved copy** unless independently confirmed —
  neither field carries an explicit MLR label anywhere in this module,
  consistent with the caution already documented for Competitive Intel §7.5.
- **No presenting model output as certainty.** Say "the model estimates,"
  never "45% of patients will abandon this prescription."

### 7.6 Behavioural protocols

| Situation | Response |
|---|---|
| User asks whether a payer requires PA | Always check the live payload field directly; do not trust the card's "PA required" text (§8.1) |
| User asks for "the" action plan for an alerted payer | Give `view_action_plan`; mention `ai_action_plan` exists with different wording if the user wants full detail (§8.4) |
| User names a payer's parent company or a patient population from generated text | Verify against `mco_org_name` / `channel_name` on that same record before repeating it (§8.2, §8.3) |
| Answer is on another tab | Name the tab and what it holds (§2.2). Do not attempt the answer from this payload |
| Uncertain | Say so. An unanswered question is recoverable; a confidently wrong figure in a regulated setting is not |

### 7.7 Output contract

Responses are validated before reaching the user and rejected if they contain
a numeric token absent from the live payload, a payer or MCO name absent from
the live payload, or a reference to internal system machinery.

### 7.8 Intent routing

| User intent | Source |
|---|---|
| what tier is this payer at | `tier_current`, with `tier_label_current` |
| did this payer's tier change | `ai_tier_change_direction`, `change_date` |
| does this payer require PA | `pa_required` — from the payload, never the card, §8.1 |
| how many covered lives / HCPs does this affect | `covered_lives`, `affected_hcp_count` |
| how many covered lives are at risk overall | `ai_total_covered_lives_at_risk` — alert-scoped only, §2.7 |
| what should I do about this payer | `view_action_plan`, noting `ai_action_plan` may differ — §8.4 |
| how likely is abandonment | `ai_abandonment_risk_pct` — alerted payers only, null otherwise |
| how many patients are affected | `ai_projected_patient_impact` — alerted payers only |
| how urgent is this | `ai_nlp_urgency` — present in payload, not shown on card |
| who is the parent company | `mco_org_name` — verify before repeating any parent-company name from generated text, §8.2 |
| is this Commercial, Medicare, or Medicaid | `channel_name` — verify before repeating a population reference from generated text, §8.3 |
| is this current | `last_refresh`, `period` — shared platform-wide |
| the alert version of this payer's change | Active Alerts — §2.2 |
| is a competitor behind this | Competitive Intel — §2.2 |

### 7.9 What this module can and cannot answer

**Available:** every payer's current tier and label, whether and when it
changed, covered lives, affected HCPs (alert-tier cards), the correct
PA-required value **from the payload** (not the card), impact score and
level, abandonment risk and projected patient impact for alerted payers, and
both generated action-plan variants.

**Not available:** a reliable PA-required answer from the screen itself for
most stable/hybrid payers (§8.1); a territory-wide covered-lives total in a
single field (§2.7); confirmation of which field the "View Action Plan"
button actually opens (§9); anything belonging to a sibling tab (§2.2); any
record change — the platform is read-only here.

---

## 8. DATA QUALITY REGISTER

> **Internal section.** Contains named records and concrete figures. The
> constraints these defects impose are stated qualitatively in §7.3–§7.5.
> If any part of this document is used as machine-readable context, exclude
> section 8 — it contains exactly the values §7.5 forbids repeating as fact.

Ordered by severity.

### 8.1 HIGH — "PA required" renders incorrectly for 4 of 5 stable/hybrid payer cards

```
                          payload pa_required   screen "PA required:"
MVP HEALTH CARE NY HIX          Yes                    Yes    match
TRICAST                         No                     Yes    MISMATCH
ADVANTAGE HEALTH PLAN           No                     Yes    MISMATCH
SCIONHEALTH                     No                     Yes    MISMATCH
SUPERIOR HEALTH PLAN TX         No                     Yes    MISMATCH
```

Every one of the five stable/hybrid cards that shows a "PA required" line
displays "Yes" — including four payers whose payload value is actually
"No." The one payer that happens to genuinely require PA (MVP) is the only
one that matches, which is consistent with the field being effectively
hardcoded to "Yes" on this card variant rather than read from
`pa_required` at all. The three alert-tier cards do not display this field,
so this defect is confined to Variant B and the hybrid card.

**Why this matters.** Prior-authorization requirement is directly
actionable information — a rep who believes PA is required for a payer that
doesn't need it may set inaccurate expectations with an HCP's office about
paperwork or delay; the reverse (believing no PA is needed when it is)
risks a surprised rejection at the pharmacy.

**Action.** Fix the "PA required" line on Variant B / the hybrid card to
read `pa_required` from the payload instead of whatever is currently
producing a constant "Yes." Audit whether the alert-tier cards have a
parallel defect once the field is added to that variant.

### 8.2 HIGH — generated action-plan text names the wrong parent organisation for one payer

Superior Health Plan TX's own structured field: `mco_org_name: "CENTENE
CORPORATION"` — Superior HealthPlan is in fact a Centene subsidiary, so this
structured field is itself correct.

Both `ai_action_plan` and `view_action_plan` for the same record read:

> "Positive tier improvement — highlight in detailing conversations as
> access win. Notify field force of improved **Humana** formulary status."

Humana is not this record's payer, not its MCO, and does not appear
anywhere else in this record. This confirms, with a concrete example, a
compliance concern already flagged in general terms in the Territory
Prioritization data-quality register ("generated prose naming the wrong
payer entity") — this is that defect, located and evidenced.

**Action.** Treat as a release blocker for this record class: a rep acting
on this text would tell colleagues the wrong payer improved. Add a
post-generation check that the payer/MCO name in generated text matches
`payer_name`/`mco_org_name` on the same record before it ships.

### 8.3 MEDIUM — generated action-plan text references a payer channel inconsistent with the record's own `channel_name`

Every payer in the captured sample carries `channel_name: "Commercial"`.
Two records' generated text names a different population entirely:

```
MVP HEALTH CARE NY HIX   channel_name: Commercial
                          ai_action_plan: "PA support resources available
                          for Medicare patients. Coordinate with hub
                          services on prior auth assistance program."

SCIONHEALTH               channel_name: Commercial
                          ai_action_plan: "...Leverage in state Medicaid
                          conversations."
```

A rep relying on this text could raise Medicare or Medicaid-specific
considerations with an HCP for a plan that is actually Commercial.

**Action.** Same remediation direction as §8.2 — constrain or check
generation against the record's own `channel_name`.

### 8.4 MEDIUM — `ai_action_plan` and `view_action_plan` diverge for alert-tier payers, but are identical for stable payers

```
                          ai_action_plan (array)              view_action_plan (string)         match?
MM INDUSTRIES             "1. Coordinate with market            "Critical: Coordinate with          No
                           access for Aetna tier appeal          market access on Aetna tier
                           submission." (+2 more steps)          appeal submission. Provide
                                                                  HCPs with PA approval
                                                                  scripts. Alert field force
                                                                  to potential Rx abandonment
                                                                  risk."

FAIRVIEW                  "1. Notify the market access           "Escalate to market access          No
                           team about the tier downgrade          team immediately. Non-formulary
                           immediately." (+2 more steps)          status will trigger Rx
                                                                   abandonment. PA support and
                                                                   samples critical for
                                                                   continuity of care patients."

CITY OF DETROIT           "1. Brief top prescribers on            "Immediate: Brief top               No
                           the tier change immediately."          prescribers on tier change.
                           (+2 more steps)                        Provide PA bridge scripts.
                                                                   Enroll patients in ZenConnect
                                                                   co-pay program to offset
                                                                   Tier 2 cost increase."

MVP / TRICAST / ADVANTAGE / SCIONHEALTH / SUPERIOR — all 5 stable payers:
  ai_action_plan and view_action_plan are byte-identical strings on every record.
```

**Reading.** Two independently-worded representations of the same
recommendation exist for every alert-tier payer, differing in urgency
framing ("Critical:" / "Escalate...immediately" / "Immediate:" — each field
adds its own severity language the other lacks) and in which supporting
detail is mentioned. For stable payers, the two fields are simply the same
string duplicated — consistent with §2.3's observation that only alerted
payers receive full generative treatment; the stable payers' "plan" appears
to be a single stored string rather than two independent generations.

**Also note the type inconsistency:** `ai_action_plan` is a 3-item array for
alert-tier payers and a single string for stable payers — the same field
name holds two different shapes depending on record type.

**Action.** Decide which of `ai_action_plan` / `view_action_plan` is
canonical for alert-tier payers and stop generating the other independently,
or reconcile them into one generation pass so they can't diverge. Normalise
`ai_action_plan`'s type across all records.

### 8.5 MEDIUM — the one STABLE+changed record's top badge shows `change_badge`, not its own `status_badge`

Superior Health Plan TX carries `status_badge: "STABLE"` — the same value as
the other four non-alerted payers, every one of which correctly displays a
green "STABLE" badge in the top-right slot. Superior's card instead displays
**"CHANGE DETECTED"** in that slot — the value of `change_badge`, not
`status_badge`. Nowhere on Superior's card does the text "STABLE" appear,
even though that is the record's actual status value.

This is the only record in the captured sample where `status_badge` is
non-null but not the field driving the top-right badge — every `AI_ALERT`
record correctly shows `status_badge`'s value there, and every other
`STABLE` record does too.

**Action.** Confirm whether the intended rule is "prefer `change_badge` over
`status_badge` whenever both are present" (in which case this is working as
designed and should be documented as such) or whether `status_badge` should
always take the top-right slot with `change_badge` shown as a secondary
inline pill, matching the alert-card pattern. Either way, document the rule
— it is not currently stated anywhere, and the one record it affects is easy
to miss in testing since it's the only upgrade in the sample.

### 8.6 LOW — "Impact: Medium –" renders with a trailing separator and no value

All three alert-tier cards show `Impact: Medium –` — the word matches
`ai_impact_level` exactly, but the trailing en-dash is followed by nothing.
`ai_impact_score` (61.9 / 59.5 / 49.5 — genuinely different across the three
records) is never rendered anywhere, so the dash may be a placeholder for a
value or trend indicator that was never wired up.

**Action.** Either populate the score/trend after the dash or remove the
dash from the template.

### 8.7 LOW — `analysis_badges` undercounts the techniques actually applied to a record

Tricast carries populated `ai_nlp_action_category` ("MONITORING"),
`ai_nlp_urgency` ("Routine"), and four `ai_nlp_keywords` — clear evidence NLP
classification ran on this record. Its `analysis_badges` array, however,
contains only `["AI_SCORING"]`, omitting `NLP_ANALYSIS` and
`PREDICTIVE_ANALYTICS`. The same pattern holds for Advantage Health Plan and
ScionHealth. Only MVP, among the stable payers, carries the fuller
3-badge list.

**Action.** Either compute `analysis_badges` from which fields are actually
populated on each record, or stop relying on it as an indicator of which
techniques ran — it currently understates them for most stable payers.

### 8.8 What reconciles correctly

Recorded so the failures above are not read as systemic.

- All six rollup counts (`ai_alert_count`, `ai_stable_count`,
  `ai_tier_downgrade_count`, `ai_high_impact_count`,
  `ai_total_covered_lives_at_risk`, `ai_total_affected_hcps`) reconcile
  exactly against the item list — a clean result, in contrast to the
  unreconciled KPI tile documented for Active Alerts §8.1.
- Card order matches the payload exactly: `AI_ALERT` payers first, then
  `STABLE`, both groups correctly sorted by `ai_impact_score` descending, on
  every one of the 8 records.
- `tier_current`, `tier_previous`, `tier_label_current`, `change_date`,
  `covered_lives`, and `affected_hcp_count` all reconcile exactly with the
  screen on every alert-tier record checked.
- `ai_is_flagged` is perfectly redundant with, and consistent with,
  `status_badge == "AI_ALERT"` on every record.
- The section-level "Real-time payer intelligence" description accurately
  reflects what this module's payload actually contains — unlike the
  equivalent panels on HCP Awareness and Competitive Intel.

The scoring, sorting, and rollup arithmetic are sound. The defects found are
concentrated in one incorrectly-rendered field (§8.1), generated text not
grounded in the record's own structured fields (§8.2, §8.3), a
field-duplication/divergence pattern (§8.4), one card's badge-source
exception (§8.5), and presentation polish (§8.6, §8.7) — not in the
underlying tier or impact data.

---

## 9. OPEN ITEMS

### 9.1 Unresolved questions

1. Which field does the "View Action Plan" button actually open —
   `view_action_plan`, `ai_action_plan`, or a combination including
   `ai_impact_summary` and `ai_pa_bridge_note`? Not confirmed from the
   captured screens (the button was not clicked in any capture).
2. Should the "PA required" line be fixed to read `pa_required` correctly,
   and should it also be added to the alert-tier card variant, which
   currently doesn't show it at all? (§8.1)
3. Is the Superior Health Plan TX badge behaviour (§8.5) an intentional rule
   for the STABLE+changed combination, or a bug? Confirm and document either
   way.
4. What does the "Monitoring frequency" section (heading visible at the
   bottom of the captured scroll, content not captured) actually contain?
5. Should `ai_action_plan` and `view_action_plan` be reconciled into a
   single generated field for alert-tier payers? (§8.4)
6. Is there a payer beyond this captured sample of 8 with
   `ai_impact_level: "High"`, given `ai_high_impact_count` is 0 here? Not
   observed, so the High-impact card treatment (if any exists) is
   undocumented.

---

## 10. VOCABULARY

| Term | Meaning |
|---|---|
| **Payer** | An insurance company or plan whose formulary determines coverage terms |
| **MCO** | Managed Care Organization — the parent entity that may own multiple payer plans (`mco_org_name`) |
| **Tier** | A payer's formulary placement for the product; lower tier numbers are generally more favourable |
| **PA** | Prior authorization — a payer requirement gating access before a prescription is covered |
| **Covered lives** | Number of patients whose insurance plan is administered under this payer record |
| **Abandonment risk** | `ai_abandonment_risk_pct` — estimated likelihood a patient does not fill a prescription after a tier change; populated for alerted payers only |
| **Impact score / level** | `ai_impact_score` (numeric, never shown) / `ai_impact_level` (Medium/Low observed, shown as text on alert cards) |
| **Tier change direction** | `ai_tier_change_direction` — DOWNGRADE / UPGRADE / UNCHANGED |
| **Channel** | `channel_name` — Commercial / Medicare / Medicaid; "Commercial" on every record observed |
| **Action plan** | Generated next-step guidance; exists in two diverging forms for alert-tier payers — §8.4 |
| **PA bridge note** | `ai_pa_bridge_note` — clinical-necessity rationale for a prior-authorization request; populated for alerted payers only |
| **PERT / EPI** | Pancreatic enzyme replacement therapy / exocrine pancreatic insufficiency |
| **Period** | The reporting quarter in the data-reference panel, shared platform-wide |
| **Last refresh** | When the pipeline last calculated, shared platform-wide |

**Brand references are generalised by design.** The generic "Product" label
is a governance control shared across every module on this platform, and
should always be reproduced exactly as given. Payer and MCO names in this
module are real, named entities, not generalised — which is why an incorrect
one (§8.2) is a factual-accuracy defect rather than a governance breach.
