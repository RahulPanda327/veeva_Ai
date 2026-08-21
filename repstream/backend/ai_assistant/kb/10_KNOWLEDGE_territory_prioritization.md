# KNOWLEDGE — Territory Prioritization

**Platform:** Veeva AI Insight 360 · **Application:** RepStream (My Insights)
**Module:** Territory Prioritization (Module 4.1 of 7)

> **Layer:** retrievable knowledge. Embedded, chunked at `##` boundaries.
> **Contains:** what things mean, where they live, how they relate.
> **Contains no:** values, counts, dates, names, instructions, or compliance
> rules. Current values arrive with the request. Nothing here is a value.

---

## 1. Module purpose

Territory Prioritization answers the representative's first question of the
week: **where should my time go?**

It reviews every HCP assigned to a territory and ranks them by current
commercial opportunity and risk — prescribing trend, recent activity,
engagement history, relative opportunity — rather than presenting a flat,
unordered list. Each ranked HCP carries a short generated explanation of why
they appear where they do, with the supporting figures alongside, so the
ranking can be understood and challenged rather than accepted blindly.

**The platform informs the decision; the representative makes it.** Generated
content is decision support for review by a qualified user, never an
autonomous decision and never a clinical recommendation.

**The platform is read-only and is not a system of record.** It interprets and
presents commercial data; it does not alter source systems. Nothing the
assistant does can change an HCP record, log a call, or update the CRM.

---

## 2. Where this module sits

```
Veeva AI Insight 360 — 7 modules
├── Territory Prioritization   ← this module
├── New Writer ID
├── Objection Handler
├── Active Alerts          ─┐
├── Competitive Intelligence │  Action Center
├── HCP Awareness            │
└── Payer Access            ─┘
```

The value chain the platform implements:

```
Data → Intelligence → Insight → Recommendation → Action
```

This module contributes the Insight and Recommendation stages for HCP
prioritization specifically.

---

## 3. Application shell

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

- **Left navigation:** Insights 360 V1 (previous version), My Insights (this
  application), Action Center, Logout.
- **Top-right:** app/grid launcher, code/developer view toggle.
- **Tabs:** Territory Prioritization (default, this document), New Writer ID,
  Objection Handler.

Users may refer to the platform, the application, or the page interchangeably.
If the question concerns KPI cards or the ranked HCP list, they mean this page.

---

## 4. Access scope

Visibility follows the organizational hierarchy. Users see only what their
authenticated identity and organizational position permit.

```
Manager  →  User (representative)  →  Territory  →  HCP
```

```
┌────────────────────┬──────────────────────────────────────────────────────┐
│ Level              │ What the user sees                                   │
├────────────────────┼──────────────────────────────────────────────────────┤
│ Manager-level      │ Consolidated view across their teams and territories, │
│                    │ able to focus on any one of them.                    │
│ User-level         │ The territories assigned to that representative.      │
│ Territory-level    │ All insights relating to a selected territory.        │
│ HCP-level          │ The detailed position for one professional.           │
└────────────────────┴──────────────────────────────────────────────────────┘
```

**Territory scope is derived from the authenticated session, not chosen
freely.** Every figure on the page corresponds to the filter currently in
force. When the filter changes, the KPI values change with it — a figure is
only ever true of the selection on screen.

---

## 5. Filter bar and data reference

```
┌───────────────┬───────────────────────┬────────────────────────────────────┐
│ Control       │ Payload path          │ Behaviour                          │
├───────────────┼───────────────────────┼────────────────────────────────────┤
│ USERS         │ filters.manager_id[]  │ Representatives the viewer may see. │
│               │ .employee_id[]        │ Defaults to All.                   │
│ TERRITORY     │ …employee_id[]        │ Territories in scope. Defaults to  │
│ NAME          │ .territory_id[]       │ All.                               │
│ Apply         │ —                     │ Refetches. Selecting a filter does │
│               │                       │ nothing until Apply is pressed.    │
└───────────────┴───────────────────────┴────────────────────────────────────┘

DATA REFERENCE panel, upper right — display only, not a filter:
    period        → the reporting quarter
    last_refresh  → shown as "Last updated: <date>"
```

**The filters hierarchy is built live from sales-force org data** and updates
automatically as managers, employees, or territories change. Every node
carries a paired identifier and label:

```
manager_id   / manager_name        ─┐
employee_id  / employee_name        │  *_id   is what the UI sends back
territory_id / territory_name      ─┘  *_name is what the UI displays
```

**Two behaviours to know.** The top-level `territory_id` and `territory_name`
are identical delimiter-joined strings; the `_name` field holds no display
names. Real names exist only inside the filters hierarchy. And
`filters.manager_id` can arrive empty — when it does, no representative or
territory names exist anywhere in the payload and both dropdowns have nothing
to populate. In that state, do not name a territory or a rep; say the scope
detail is not available in the current view.

**Scope may be singular or plural.** Never assume one territory.

---

## 6. KPI summary cards

Source: `GET /api/v1/territory/summary`

```
┌────────────────────┬───────────────────────┬───────────────────────────────┐
│ Card label         │ Payload field         │ Meaning                       │
├────────────────────┼───────────────────────┼───────────────────────────────┤
│ Total HCPs         │ total_hcps            │ HCPs in the current filter    │
│                    │                       │ scope for the period.         │
│ High Priority      │ high_priority_count   │ HCPs in the top tier.         │
│                    │                       │ AI RANKED badge.              │
│ Medium Priority    │ medium_priority_count │ Middle tier. AI RANKED badge. │
│ Last Refresh       │ last_refresh          │ When the data was last        │
│                    │                       │ calculated. Not current time. │
│ This Week Target   │ weekly_target         │ Recommended visits this week. │
└────────────────────┴───────────────────────┴───────────────────────────────┘

Also in the payload, not displayed:  low_priority_count, period,
territory_id, territory_name, filters
```

**By design the three tier counts sum to `total_hcps`** — every HCP in scope
falls into exactly one tier. See §11 for when this does not hold in practice.

**`low_priority_count` has no card.** Present in the payload, never rendered.
Treat as unavailable — §11.

**AI RANKED badge** appears on High and Medium Priority only. It marks the
tier as model output rather than a CRM segment. If asked who decided: the
model produced the ranking, the representative decides what to act on.

---

## 7. Ranked HCP list

Source: `GET /api/v1/territory/hcp-list`
Heading: **"DATAstream AI-ranked HCP priority list"**
Attribution: **"Powered by DATAstream™ Rx + DATAstream AI"**

Sorted by priority tier, HIGH → MEDIUM → LOW, and by score within tier.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ ┃ (AM)  <name>                                          [View Profile]   │
│ ┃       <specialty>                                                      │
│ ┃       [HIGH PRIORITY]                              Score: <percentage> │
│ ┃  ┌────────────────────────────────────────────────────────┐            │
│ ┃  │  <generated narrative>                     [AI INSIGHT] │            │
│ ┃  └────────────────────────────────────────────────────────┘            │
│ ┃  LAST RX      RX Q1     RX Q4     SEGMENT      LAST CALL               │
│ ┃  <date>       <count>   <count>   <label>      <n> days ago            │
└──────────────────────────────────────────────────────────────────────────┘
  ↑ coloured left stripe and avatar, keyed to tier
```

### Row element mapping

```
┌──────────────────┬────────────────────────┬────────────────────────────────┐
│ Element          │ Payload field          │ Notes                          │
├──────────────────┼────────────────────────┼────────────────────────────────┤
│ Avatar initials  │ derived from name      │ Colour keyed to tier.          │
│ Name             │ name                   │ Trailing whitespace stripped.  │
│ Specialty        │ specialty              │                                │
│ Priority chip    │ ai_priority_tier       │ HIGH / MEDIUM / LOW.           │
│ Score            │ ai_score               │ Percentage string.             │
│ AI INSIGHT text  │ ai_generated_insight   │ Generated narrative.           │
│ (not displayed)  │ ai_score_reason        │ Why this HCP scored as it did. │
│ LAST RX          │ last_rx_date           │ Most recent script.            │
│ RX Q1            │ rx_q1                  │ Current-quarter volume.        │
│ RX Q4            │ rx_q4                  │ Prior-quarter volume.          │
│ SEGMENT          │ segment                │ CRM classification, not tier.  │
│ LAST CALL        │ last_call_date         │ Rendered as elapsed days.      │
│ View Profile     │ view_profile{}         │ Opens the detail record.       │
└──────────────────┴────────────────────────┴────────────────────────────────┘
```

**`ai_score_reason` is the most useful field for "why is this HCP here".** It
is in the payload but not on the card, and it names the drivers directly —
Rx growth, decile rank, engagement recency. Prefer it over the narrative when
explaining a ranking.

### Tier colour coding

```
HIGH PRIORITY     orange avatar, orange stripe, filled orange chip
MEDIUM PRIORITY   blue avatar, blue stripe, outlined blue chip
LOW PRIORITY      green avatar, green stripe, plain text label, no chip fill
```

---

## 8. View Profile record

`view_profile` holds registry detail not shown on the list card:

```
formatted_name          specialist_description     medical_degree
email                   website                    npi
address / city / state  hcp_status                 hcp_type
target                  pdrp_output                is_ama_do_not_contact
```

**Four of these gate what may be said about the HCP.**

```
┌────────────────────────┬─────────────────────────────────────────────────┐
│ Field                  │ What it constrains                              │
├────────────────────────┼─────────────────────────────────────────────────┤
│ pdrp_output            │ AMA Prescriber Data Restriction Program. An      │
│                        │ enrolled prescriber has opted out of Rx data     │
│                        │ disclosure to sales representatives.             │
│ hcp_type               │ Prescriber vs non-prescribing professional.      │
│ hcp_status             │ Active vs Inactive.                              │
│ is_ama_do_not_contact  │ Contact restriction flag.                        │
└────────────────────────┴─────────────────────────────────────────────────┘
```

`target` indicates whether the HCP is on the official call plan. It is a
separate concept from both segment and AI priority.

---

## 9. How the ranking is produced

Four techniques combine to produce the tier and score:

```
┌────────────────────────┬──────────────────────────────────────────────────┐
│ Technique              │ Contribution                                     │
├────────────────────────┼──────────────────────────────────────────────────┤
│ Composite scoring      │ Combines the weighted signals into one score.    │
│ Linear regression      │ Establishes the prescribing trend direction.     │
│ NLP classification     │ Categorises engagement.                          │
│ Generative narrative   │ Writes the visit-preparation insight.            │
└────────────────────────┴──────────────────────────────────────────────────┘
```

Inputs: HCP list, twelve months of prescribing history, call activity, and
decile rank.

**Scores tie heavily.** Many HCPs share an identical score, so a score-ordered
list contains large blocks at the same value and ordering within a block is
arbitrary. Never describe one HCP as ranked above another when their scores
are equal, and never infer a rank position from list position alone.

**Tier is a band, not a rank.** Two HCPs in the same tier are not ordered
relative to each other by the tier.

---

## 10. Segment vs AI Priority vs Target

Three separate classifications, routinely confused.

```
SEGMENT      CRM-assigned. High, Medium, Low, Non-Target, CF HCP.
             Set by commercial operations. Not model output.
AI PRIORITY  Model-assigned band: HIGH, MEDIUM, LOW. Derived from the score.
TARGET       Whether the HCP is on the official call plan. A flag, not a band.
```

Segment and AI Priority diverge routinely **and by design** — a High-segment
HCP can rank MEDIUM priority, and a Non-Target HCP can rank HIGH. Neither is
an error; the model is measuring current opportunity, the CRM is recording a
planning classification.

When a user says "high", establish which they mean, or answer for AI Priority
and say which you answered for.

---

## 11. Field reliability

**Tier counts.** `high_priority_count` and `medium_priority_count` correspond
to the ranked list. `low_priority_count` does not do so reliably across
payload versions and is never displayed. Do not use it, do not quote it, and
do not reconstruct it by subtraction. The three tiers are specified to sum to
`total_hcps`; where they do not, the low tier is the field at fault.

**Proportions.** Give raw counts rather than percentages, and say the low-tier
figure is not available on the page.

**Date representation.** `last_rx_date` and `last_call_date` are absolute
dates in the payload while the card renders LAST CALL as elapsed days. These
are different representations and may not correspond in every build. Quote the
payload date rather than an elapsed-day figure.

**`ai_generated_insight` is generated prose, not a source of fact.** Where it
disagrees with the structured fields on its own row — direction of change,
call recency, competitor share, whether any activity exists — **the structured
fields are correct.** Never quote a figure or a factual claim from the
narrative; read it from the fields. If a user asks about something stated only
in the narrative, answer from the fields and say the narrative may not match.

**Documented fields that may be absent.** Module documentation describes
`affiliated_hospital`, `ai_rx_trend_direction`, `ai_predicted_next_q_rx`,
`ai_engagement_category`, `ai_engagement_urgency`, and `analysis_badges`.
These are not present in every payload. Never answer from a documented field
name — answer only from fields actually present in the payload attached to the
request. Documentation describes intent; the payload describes reality.

---

## 12. What this module can and cannot answer

**Available**
- Any KPI card value and what it represents.
- The reporting period and refresh date.
- For any HCP on the list: name, specialty, tier, score, both quarterly Rx
  figures, segment, last Rx date, last call date, and the score reason —
  subject to §8's gating fields.
- Representatives and territories in scope, when the hierarchy is populated.
- What any control, badge, chip, or colour means.
- How the ranking is produced, in the terms of §9.

**Not available**
- Registry detail behind View Profile until that record is opened.
- Content belonging to New Writer ID, Objection Handler, or Action Center.
- Trend beyond the two quarters on the row. The payload is a single snapshot.
- Predicted future prescribing, unless a prediction field is present.
- Any figure for the low-priority tier.
- Rankings or comparisons between HCPs sharing an identical score.
- Anything requiring a change to a record — the platform is read-only.

---

## 13. Intent routing

```
┌──────────────────────────────────────┬────────────────────────────────────┐
│ User intent                          │ Source                             │
├──────────────────────────────────────┼────────────────────────────────────┤
│ how many HCPs do I have              │ total_hcps, with scope             │
│ how many are high priority           │ high_priority_count                │
│ how many calls this week             │ weekly_target                      │
│ is this current / what quarter       │ last_refresh, period               │
│ where should I start / who first     │ list order, plus §9 tie caveat     │
│ why is this HCP ranked here          │ ai_score_reason — §7               │
│ what is this HCP's Rx trend          │ rx_q1 and rx_q4 fields, never the  │
│                                      │ narrative — §11                    │
│ when did I last see them             │ last_call_date — §11               │
│ how does the ranking work            │ §9                                 │
│ what does AI RANKED / a colour mean  │ §6, §7                             │
│ segment vs priority vs target        │ §10                                │
│ whose data am I seeing               │ filters hierarchy, §5              │
│ can I change / update this           │ read-only — §1                     │
│ what about low priority              │ not surfaced — §6, §11             │
│ what share are high priority         │ raw counts only — §11              │
│ non-writers / warm intro / email     │ New Writer ID tab — §14            │
│ what do I say when they push back    │ Objection Handler tab — §14        │
│ alerts / formulary / what changed    │ Action Center — §14                │
└──────────────────────────────────────┴────────────────────────────────────┘
```

---

## 14. Sibling destinations — routing only

- **New Writer ID** (tab). HCPs prescribing in-class but not this product,
  matched to an existing writer for a warm introduction, with a drafted
  outreach message and matched diagnosis codes. Route for: who should I start,
  non-writers, warm intro, draft an email, conversion targets.
- **Objection Handler** (tab). Objections identified in call transcripts,
  ranked by frequency, each with an approved response and supporting material
  reference. Route for: what do I say when, they told me, pushback, objection.
- **Action Center** (left nav). Active Alerts, HCP Awareness, Competitive
  Intelligence, Payer Access. Route for: alerts, what changed, formulary,
  competitor activity, awareness decline, deploy to field.
- **Insights 360 V1** (left nav). The previous platform version.

Content questions about these are answered there, not from this document.

---

## 15. Vocabulary

```
HCP              Healthcare professional — prescriber or clinical staff.
Rep              Field sales representative. The primary user.
Manager          Owns a set of representatives; sees their combined scope.
Territory        A geographic or account-based assignment owned by a rep.
Segment          CRM-assigned classification. Not model output.
AI Priority      Model-assigned tier. Not a CRM field.
Target           Whether the HCP is on the official call plan.
Score            The model's percentage ranking value.
Rx               Prescription.
Rx Q1 / Rx Q4    Current-quarter and prior-quarter prescription volume.
NRx              New prescription, as opposed to a refill.
Decile rank      A market-share ranking band used in score reasoning.
NPI              National Provider Identifier.
PDRP             AMA Prescriber Data Restriction Program. An enrolled
                 prescriber has opted out of Rx data disclosure to sales.
MLR              Medical, Legal and Regulatory review. Approved content only.
Period           The reporting quarter in the data reference panel.
Last refresh     When the pipeline last calculated. Not the current time.
Weekly target    Recommended visits for the current week.
PERT / EPI       Therapy-area terms appearing in narratives.
In-class         Products treating the same indication, including competitors.
```

**Brand references are generalised by design.** Payloads use generic labels
in place of confidential product and competitor names. That generalisation is
a governance control, not a data defect — reproduce the label exactly as the
payload gives it.
