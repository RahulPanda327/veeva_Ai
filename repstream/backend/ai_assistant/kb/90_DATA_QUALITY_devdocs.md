# DATA QUALITY & SPEC DRIFT — Territory Prioritization

> **Layer:** developer and governance documentation. Human audience only.
> **Never embedded. Never injected. Never reaches the model.**
>
> The knowledge file states these constraints qualitatively. Evidence lives
> here so concrete figures cannot be latched onto and emitted as current
> values. Ordered by severity.

---

## 1. CRITICAL — PDRP-restricted prescribers have Rx data exposed

Two records in the captured HCP list carry `view_profile.pdrp_output = "Y"`
and also carry populated `rx_q1` / `rx_q4` values, which the card renders.

```
Nadeem Ansari    pdrp_output = Y    rx_q1 = 300    rx_q4 = 200
Jemini Ignacio   pdrp_output = Y    rx_q1 = 100    rx_q4 = 100
```

PDRP is the AMA Prescriber Data Restriction Program. An enrolled prescriber
has opted out of having prescribing data disclosed to pharmaceutical sales
representatives. Rendering their Rx volumes to a rep is the precise disclosure
the programme exists to prevent.

Both records also receive an `ai_score`, an `ai_priority_tier`, and a
narrative that restates the prescription counts in prose — so the restricted
figure appears three times per row.

**Actions**
- Suppress `rx_q1`, `rx_q4`, `last_rx_date`, `ai_score` and the narrative for
  any record where `pdrp_output = "Y"`, at the API layer, not the frontend.
- Audit whether PDRP is honoured anywhere in the pipeline today.
- Raise with compliance before the next release. This is not a display bug.

Assistant is instructed to refuse these values even when rendered
(`00_SYSTEM_INSTRUCTIONS.md` §4).

---

## 2. CRITICAL — generated content recommending off-label discussion

A New Writer ID narrative recommends discussing "potential off-label uses"
during an HCP visit. Promotion of unapproved uses is a regulatory violation
regardless of intent, and this reached a rendered screen.

**Actions**
- Add an off-label term filter to the generation post-check, blocking the
  output rather than flagging it.
- Review the generation prompt for anything inviting discussion of uses
  outside the approved indication.
- Report the instance through the MLR process.

Assistant is instructed to refuse to engage with off-label substance even when
quoting displayed content (`00_SYSTEM_INSTRUCTIONS.md` §4).

---

## 3. HIGH — `low_priority_count` computed from a hard-coded base

Reconciling the KPI payload against the HCP list it accompanies:

```
                      KPI payload      actual list
total_hcps                    68               68   match
high_priority_count            7                7   match
medium_priority_count         11               11   match
low_priority_count           982               50   MISMATCH
```

`1000 - 7 - 11 = 982`. The low tier is derived as `1000 - high - medium`
rather than counted. An earlier capture fits the same formula:
`1000 - 0 - 0 = 1000` against `total_hcps` of 50.

**High and medium reconcile exactly.** Only the low tier is wrong, and only
via this one formula.

**This contradicts the module spec.** `MyInsights_GUIDE` gives a worked
example of 127 total against 34 high, 58 medium, 35 low — which sums to 127.
The tiers are specified to partition the territory.

**A second code path already behaves correctly.** A later payload for a
single territory returns `2 + 9 + 4 = 15` against `total_hcps` 15, which
reconciles and does not fit the 1000-base formula. Two implementations
coexist.

**Actions**
- Replace the constant with `total_hcps - high - medium`, or count directly.
- Identify which service produces which payload shape and consolidate.
- Add a pipeline assertion `high + medium + low = total_hcps` that fails the
  build.
- Consider surfacing a Low Priority card so the defect is visible on screen.

---

## 4. HIGH — narrative template contradicts its own row

The fallback string

> "Stable prescriber with consistent Rx activity this quarter (X Rx, prior
> quarter Y). No significant competitor pressure detected... No recent call
> activity on file. Consider a routine maintenance call this month."

fires on at least 12 records where it is factually wrong in two ways.

**"No recent call activity on file"** while `last_call_date` falls within the
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
  fall back to a purely structural summary.

---

## 5. MEDIUM — narrative addresses the wrong reader

Many insights are written in second person to the **HCP** though the reader is
the **rep**:

> "Arthur Magun, your Rx volume has surged by 300.0% this quarter..."

Others mix within one paragraph — third person about the HCP, then second
person to the rep:

> "Sunil Joseph has seen a notable Rx increase... in his practice. Given that
> **your** last call on August 4, 2026, had an unknown outcome..."

**Action.** Fix the prompt to fix the reader as the representative and the HCP
as third person throughout.

---

## 6. MEDIUM — internal contradictions within single narratives

```
Arthur Magun   "surged by 300.0% ... indicating strong stability"
Lisa Siby      "remains stable at 500, a notable increase from 0"
```

Growth and stability fragments are concatenated without a consistency check.

---

## 7. MEDIUM — competitor share values have no structured source

Nearly every narrative states the competitor holds 0% share. Two diverge:

```
Richard Weirich   "holds a 100% share in the market"
Jack-Ky Wang      "holding only 1% of the competitor share"
```

No competitor-share field exists in the record, so all three values are
produced without a source. **Action:** add the field or remove competitor
share from the narrative entirely.

---

## 8. MEDIUM — warm-introduction referrals ignore geography

Four Illinois HCPs are told to seek a warm introduction via a prescriber in
the Bronx, New York:

```
Terry Miller             Freeport, IL     → referrer in Bronx, NY
Carmen Fotso-Kouatchou   West Dundee, IL  → referrer in Bronx, NY
Hugo Dulce               Addison, IL      → referrer in Bronx, NY
Myrna Patricio           Elgin, IL        → referrer in Bronx, NY
```

The peer-match step has no locality constraint. One referral also carries a
stray space before its full stop, indicating raw template concatenation.

---

## 9. MEDIUM — documented contract does not match the implementation

`MyInsights_GUIDE` §Module 1 documents fields the payload does not return, and
omits fields it does.

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

Different field name, different type, different representation. Any consumer
built from the document alone will fail.

**Actions**
- Reconcile the guide against the implementation and decide which is correct.
- Version the API contract and generate the doc from a schema.
- The knowledge file instructs the assistant to answer only from fields
  actually present in the payload, never from a documented field name (§11).

---

## 10. LOW — score quantisation

Across 68 HCPs there are 11 distinct scores.

```
22.40% ×48    26.62% ×1    32.40% ×1    37.40% ×2    52.40% ×5    67.40% ×6
26.01% ×1     30.73% ×1    35.73% ×1    48.51% ×1    62.40% ×1
```

48 of 68 share one score; 6 share the top score. The scorer behaves as a
coarse rule-based additive model rather than a ranking function, so ordering
within the low tier carries no information and the top of the list is a
six-way tie.

**Action.** Add a continuous tie-breaking component, or stop presenting the
list as strictly ordered. Knowledge file §9 instructs the assistant not to
infer rank from list position.

---

## 11. LOW — records that should probably be filtered out

```
Ekow Pinkrah     hcp_status = Inactive,  hcp_type = Non-Prescribing,  rx_q1 = 100
Angela Conklin   hcp_status = Inactive                                rx_q1 = 500
Madison Hester   hcp_type   = Non-Prescribing                         rx_q1 = 100
```

Inactive HCPs are still scored and ranked. Non-prescribing professionals carry
prescription counts, which is contradictory on its face. Decide whether these
belong in the priority list at all.

---

## 12. LOW — screen versus payload divergence

A captured screen showed Total HCPs 60, High 6, Medium 4, Target 4 against a
payload carrying 68, 7, 11, 5. The same capture showed LAST RX "Apr 30, 2026"
where the payload carries "Jul 24, 2026", and LAST CALL "142 days ago" where
the payload carries early-August dates roughly two weeks before refresh.

Possible causes: capture predates the payload, different filter state, or the
frontend deriving these fields from a separate source. **Needs resolving** —
it determines whether the payload can be treated as authoritative. The system
prompt currently assumes it can, and instructs the assistant to ask whether
Apply was pressed rather than contradict the user.

---

## 13. Open items — branding and platform naming

Three names are in play across the artifacts:

```
client overview doc   "Veeva AI Insight 360"
application header    "Insights 360™ V2"  +  "SLIPSTREAM"
attribution badge     "POWERED BY DATAstream AI"  /  "DATAstream™ Rx"
```

The knowledge file uses the on-screen names, since that is what users will
say. Confirm which is externally correct before this reaches customers, and
whether the client overview needs updating to match the shipped UI.

---

## 14. Compliance register

| # | Issue | Severity | Blocks release |
|---|---|---|---|
| 1 | PDRP-restricted Rx data rendered to reps (§1) | Critical | Yes |
| 2 | Generated content recommending off-label discussion (§2) | Critical | Yes |
| 3 | Generated prose naming the wrong payer entity (Action Center) | High | Review |
| 4 | Rep name paired with non-matching email in deploy target | High | Review |
| 5 | Narrative asserting no call activity against a logged call (§4) | Medium | No |
| 6 | Competitor share figures with no structured source (§7) | Medium | No |
| 7 | Inactive and non-prescribing HCPs ranked and scored (§11) | Low | No |

Per the client overview's own governance section, the following remain open
for the delivery team and the client compliance function, and are relevant
to this module:

- Validation and sign-off procedure for generated content used in HCP-facing
  conversations.
- Audit logging and retention expectations.
- Data residency and retention requirements.

---

## 15. What reconciles correctly

Recorded so the failures above are not read as systemic.

- `total_hcps`, `high_priority_count`, and `medium_priority_count` match the
  ranked list exactly.
- Percentage growth figures quoted in narratives match `rx_q1` and `rx_q4`
  wherever an explicit percentage is given — the errors are in qualitative
  wording, not arithmetic.
- The newer single-territory KPI payload reconciles fully.
- The filters hierarchy structure matches the documented contract exactly.

The counting and arithmetic logic is sound. The defects are missing data, one
hard-coded constant, unguarded narrative templates, unenforced compliance
flags, and documentation drift.
