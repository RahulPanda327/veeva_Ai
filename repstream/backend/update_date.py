"""One script for every demo-data date refresh, across all five modules.

The seeded warehouse data stops around April 2026, so as the calendar moves on
every date on screen drifts further into the past. Each part below pulls one
column back to a sensible distance from today.

Parts
-----
    call        Territory      Modified_Date        -> today - 10..15 days   (last_call_date)
    nrx         New Writer     Week_Ending_Date     -> today - 30..40 days   (last_nrx_date)
    rx-shift    Territory      Month_Ending_Date    -> constant offset       (last_rx_date)
    calls       Territory      Call_Date            -> constant offset       (engagement scoring)
    alerts      Active Alerts  Detection_Datetime   -> today - 10..15 days   (detected_at)
    signals     Competitive    Detection_Date       -> today - 13..18 days   (signal_date)
    payer       Payer Access   Change_Date          -> today -  8..14 days   (change_date)
    objections  Objections     Detection_Period     -> previous -> current month
    rx-perrow   Territory      Month_Ending_Date    -> today - 20..30 days   OPT-IN, see below

Everything except rx-perrow runs by default.

Why rx-shift and rx-perrow are mutually exclusive
-------------------------------------------------
Both write Month_Ending_Date, in opposite ways, and that column feeds TWO things
at once: last_rx_date (MAX per HCP) and the rx_q1 / rx_q4 quarter aggregates that
drive ai_priority_tier.

  rx-perrow  rewrites each HCP's newest row. The date looks recent, but that row
             leaves its quarter, the prior quarter empties, growth computes flat,
             and every HCP collapses to the LOW tier.

  rx-shift   moves EVERY row by one constant offset. Relative distances are
             preserved, so each quarter's contents travel together, the
             quarter-over-quarter comparison survives, and the tiers hold -- while
             the newest date still lands a few weeks back.

rx-shift is what you want. rx-perrow is kept only because it was asked for
explicitly; selecting both is refused.

Nothing here touches HCP Awareness -- its period labels are hardcoded in
services/action_center/hcp_awareness_svc.py (_PERIODS), not stored in a column.

Scope
-----
Territory-scoped parts resolve the rep's ORG TREE, the same set
/api/v1/territory/hcp-list reads when no filter is applied. Scoping to just the
territory in utils/auth.py is NOT enough -- those HCPs may never appear in the
response. The small insight360_* tables are updated whole; they hold a handful of
rows each.

Usage
-----
    python scripts/update_date.py                          # dry run, all default parts
    python scripts/update_date.py --apply                  # write them
    python scripts/update_date.py --only alerts,payer --apply
    python scripts/update_date.py --exclude calls --apply
    python scripts/update_date.py --only rx-shift --rx-offset-days -85 --apply   # undo a shift
    python scripts/update_date.py --list                   # show parts and exit

Dry run is the default. Nothing is written without --apply.
"""
from __future__ import annotations

import argparse
import random
import re
import sys
from collections import OrderedDict, defaultdict
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from app.config import settings  # noqa: E402
from app.database import SessionLocal, engine  # noqa: E402
from app.services.territory_prioritization.data_ingestion import (  # noqa: E402
    get_current_and_prior_quarter,
)

SCHEMA = settings.HUB_SCHEMA
SALES = f"{SCHEMA}.vw_tfact_prescribersales_zenpep_reporting_dul"
HCPDIM = f"{SCHEMA}.vw_tdim_healthcarepractitioner_zenpep_reporting_dul"
CALLS = f"{SCHEMA}.vw_tfact_callactivitydetails_zenpep_reporting_dul"
ALERTS = f"{SCHEMA}.insight360_active_alerts_dul"
SIGNALS = f"{SCHEMA}.insight360_competitive_intel_dul"
PAYER = f"{SCHEMA}.insight360_payer_access_dul"
OBJECTIONS = f"{SCHEMA}.insight360_objection_handler_dul"

# today - N days, inclusive, drawn per row
CALL_DAYS_BACK = (10, 15)     # Modified_Date      -> last_call_date
NRX_DAYS_BACK = (30, 40)      # Week_Ending_Date   -> last_nrx_date
RX_PERROW_DAYS_BACK = (20, 30)  # Month_Ending_Date -> last_rx_date (opt-in)
ALERT_DAYS_BACK = (10, 15)    # Detection_Datetime -> detected_at
SIGNAL_DAYS_BACK = (13, 18)   # Detection_Date     -> signal_date
PAYER_DAYS_BACK = (8, 14)     # Change_Date        -> change_date

# Where the newest row should land for the constant-offset shifts
RX_TARGET_DAYS_BACK = 25
CALL_TARGET_DAYS_BACK = 2

ID_CHUNK = 400   # SQL Server caps a statement at 2100 parameters
BATCH = 200


# ─────────────────────────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────────────────────────

def stamp(d: date) -> str:
    """Columns are varchar holding '2026-04-30 00:00:00.0000000'. Match it."""
    return f"{d:%Y-%m-%d} 00:00:00.0000000"


def in_clause(prefix: str, values):
    keys = {f"{prefix}{i}": v for i, v in enumerate(values)}
    return ", ".join(f":{k}" for k in keys), keys


def org_tree_territories() -> list[str]:
    """The territory set the hcp-list endpoint actually reads."""
    from app.services.filters_service import salesforce_of
    from app.routers.territory_prioritization import _all_territory_ids
    from app.utils.auth import _DEV_IDENTITY

    db = SessionLocal()
    try:
        t = _all_territory_ids(db, salesforce_of(_DEV_IDENTITY.territory_id)) or []
    finally:
        db.close()
    return t or [_DEV_IDENTITY.territory_id]


def grouped_update(conn, sql_template: str, plan: dict, label: str,
                   extra: dict | None = None, key: str = "hcp") -> int:
    """Rewrite rows in groups instead of one at a time.

    Rows sharing the same (current value, new value) pair go in a single
    statement. Row-at-a-time updates against Synapse ran at roughly 30 rows per
    minute, which meant hours; this brings the same work down to a couple of
    hundred statements.

    The current value is matched in the WHERE clause because these fact tables
    have no primary key -- it is the only way to pin the update to the intended
    row.
    """
    groups = defaultdict(list)
    for ident, v in plan.items():
        groups[(v["cur"], v["new"])].append(ident)

    stmts = rows = 0
    total = len(groups)
    for gi, ((cur_value, new_value), idents) in enumerate(groups.items(), 1):
        for i in range(0, len(idents), ID_CHUNK):
            ph, keys = in_clause("i", idents[i:i + ID_CHUNK])
            params = {**keys, **(extra or {}), "cur_value": cur_value, "new_value": new_value}
            res = conn.execute(text(sql_template.replace("__IDS__", ph)), params)
            stmts += 1
            rows += res.rowcount or 0
        print(f"    {label}: group {gi}/{total}", end="\r", flush=True)
    print(f"    {label}: {stmts} statements, {rows} rows" + " " * 16)
    return rows


def simple_update(conn, table: str, column: str, id_col: str, plan: dict, label: str) -> int:
    """One statement per distinct target value, for tables with a unique id."""
    groups = defaultdict(list)
    for ident, v in plan.items():
        groups[v["new"]].append(ident)

    stmts = rows = 0
    for new_value, idents in groups.items():
        for i in range(0, len(idents), ID_CHUNK):
            ph, keys = in_clause("i", idents[i:i + ID_CHUNK])
            res = conn.execute(text(f"""
                UPDATE {table} SET {column} = :new_value WHERE {id_col} IN ({ph})
            """), {**keys, "new_value": new_value})
            stmts += 1
            rows += res.rowcount or 0
    print(f"    {label}: {stmts} statements, {rows} rows")
    return rows


def show(plan: dict, label: str, n: int = 6, fmt=lambda v: v) -> None:
    if not plan:
        print(f"    {label}: nothing in scope")
        return
    print(f"    {label}: {len(plan)} rows")
    for ident in list(plan)[:n]:
        v = plan[ident]
        print(f"      {str(ident)[:12]:<13} {str(v['cur'])[:19]:<21} -> {fmt(v['new'])}")
    if len(plan) > n:
        print(f"      ... and {len(plan) - n} more")


# ─────────────────────────────────────────────────────────────────────────────
# Parts
# ─────────────────────────────────────────────────────────────────────────────

def part_call(conn, ctx) -> None:
    """Modified_Date on the HCP dimension -> last_call_date.

    HCP_Durable_Id is unique here, so it is one row per HCP and a plain update.
    Nothing else reads this column, so it has no knock-on effects.
    """
    ph, tkeys = in_clause("t", ctx.territories)
    rows = conn.execute(text(f"""
        SELECT HCP_Durable_Id AS ident, Modified_Date AS cur
        FROM {HCPDIM}
        WHERE HCP_Durable_Id IN (
            SELECT DISTINCT s.HCP_Durable_Id FROM {SALES} s WHERE s.sf_terr_pk_gi IN ({ph}))
    """), tkeys).fetchall()

    plan = OrderedDict()
    for r in rows:
        d = ctx.today - timedelta(days=ctx.rnd.randint(*CALL_DAYS_BACK))
        plan[r.ident] = {"cur": r.cur, "new": stamp(d), "date": d}

    show(plan, "last_call_date", fmt=lambda v: v[:10])
    if ctx.apply and plan:
        simple_update(conn, HCPDIM, "Modified_Date", "HCP_Durable_Id", plan, "last_call_date")


def part_nrx(conn, ctx) -> None:
    """Week_Ending_Date -> last_nrx_date, the newest COMPETITOR new-Rx week.

    Source is services/new_writer_id/non_writer_detection.py:
        MAX(Week_Ending_Date) WHERE Brand_Name <> 'ZENPEP' AND New_Rx_Count > 0

    Both filters matter -- without the brand filter it would include our own
    product, without New_Rx_Count it would count refills.

    Deliberately not scoped by territory in the WHERE: the source query groups by
    HCP across all of that HCP's rows, so filtering here would move a different
    row than the endpoint reads. Scope comes from the HCP id set instead.
    """
    ph, tkeys = in_clause("t", ctx.territories)
    rows = conn.execute(text(f"""
        WITH scoped AS (
            SELECT DISTINCT s.HCP_Durable_Id FROM {SALES} s WHERE s.sf_terr_pk_gi IN ({ph})
            UNION
            SELECT DISTINCT HCP_Durable_Id FROM {SCHEMA}.insight360_peer_match_dul
        )
        SELECT s.HCP_Durable_Id AS ident, MAX(s.Week_Ending_Date) AS cur
        FROM {SALES} s
        WHERE s.HCP_Durable_Id IN (SELECT HCP_Durable_Id FROM scoped)
          AND s.Brand_Name <> 'ZENPEP'
          AND ISNULL(TRY_CAST(s.New_Rx_Count AS FLOAT), 0) > 0
        GROUP BY s.HCP_Durable_Id
    """), tkeys).fetchall()

    plan = OrderedDict()
    for r in rows:
        d = ctx.today - timedelta(days=ctx.rnd.randint(*NRX_DAYS_BACK))
        plan[r.ident] = {"cur": r.cur, "new": stamp(d), "date": d}

    show(plan, "last_nrx_date", fmt=lambda v: v[:10])
    if ctx.apply and plan:
        grouped_update(conn, f"""
            UPDATE {SALES}
            SET Week_Ending_Date = :new_value
            WHERE HCP_Durable_Id IN (__IDS__)
              AND Week_Ending_Date = :cur_value
              AND Brand_Name <> 'ZENPEP'
              AND ISNULL(TRY_CAST(New_Rx_Count AS FLOAT), 0) > 0
        """, plan, "last_nrx_date")


def part_rx_perrow(conn, ctx) -> None:
    """Month_Ending_Date per HCP -> last_rx_date. OPT-IN; flattens the tiers.

    Only the row holding each HCP's current maximum is rewritten, since that is
    what MAX() returns. See the module docstring for why this collapses
    ai_priority_tier and why rx-shift is the better tool.
    """
    ph, tkeys = in_clause("t", ctx.territories)
    rows = conn.execute(text(f"""
        SELECT s.HCP_Durable_Id AS ident, MAX(s.Month_Ending_Date) AS cur
        FROM {SALES} s
        WHERE ISNULL(TRY_CAST(s.Total_Rx_Quantity AS FLOAT), 0) > 0
          AND s.sf_terr_pk_gi IN ({ph})
        GROUP BY s.HCP_Durable_Id
    """), tkeys).fetchall()

    plan = OrderedDict()
    for r in rows:
        d = ctx.today - timedelta(days=ctx.rnd.randint(*RX_PERROW_DAYS_BACK))
        plan[r.ident] = {"cur": r.cur, "new": stamp(d), "date": d}

    show(plan, "last_rx_date (per-row)", fmt=lambda v: v[:10])
    if ctx.apply and plan:
        grouped_update(conn, f"""
            UPDATE {SALES}
            SET Month_Ending_Date = :new_value
            WHERE HCP_Durable_Id IN (__IDS__)
              AND Month_Ending_Date = :cur_value
              AND ISNULL(TRY_CAST(Total_Rx_Quantity AS FLOAT), 0) > 0
              AND sf_terr_pk_gi IN ({ph})
        """, plan, "last_rx_date", extra=tkeys)


def part_rx_shift(conn, ctx) -> None:
    """Move the whole Rx history by one offset, preserving the quarter structure.

    Runs a restore first: any Month_Ending_Date inside the last 60 days is a
    leftover from a per-row rewrite -- genuine data has nothing that recent.
    Those rows go back to a real month-end, recovered from Week_Ending_Date where
    that column is still original, otherwise to the pre-change maximum.
    """
    ph, tkeys = in_clause("t", ctx.territories)
    recent = "TRY_CAST(Month_Ending_Date AS DATE) >= DATEADD(day, -60, CAST(GETDATE() AS DATE))"
    week_ok = "TRY_CAST(Week_Ending_Date AS DATE) < DATEADD(day, -60, CAST(GETDATE() AS DATE))"

    stale = conn.execute(text(f"SELECT COUNT(*) FROM {SALES} WHERE {recent}")).scalar()
    if stale:
        baseline = conn.execute(text(f"""
            SELECT MAX(TRY_CAST(Month_Ending_Date AS DATE)) FROM {SALES} WHERE NOT ({recent})
        """)).scalar()
        print(f"    restore: {stale} rows sit inside the last 60 days (baseline {baseline})")
        if ctx.apply:
            conn.execute(text(f"""
                UPDATE {SALES}
                SET Month_Ending_Date =
                    CONVERT(varchar(10), EOMONTH(TRY_CAST(Week_Ending_Date AS DATE)), 120)
                    + ' 00:00:00.0000000'
                WHERE {recent} AND {week_ok}
            """))
            conn.execute(text(f"UPDATE {SALES} SET Month_Ending_Date = :b WHERE {recent}"),
                         {"b": stamp(baseline)})

    base_max = conn.execute(text(f"""
        SELECT MAX(TRY_CAST(s.Month_Ending_Date AS DATE))
        FROM {SALES} s
        WHERE ISNULL(TRY_CAST(s.Total_Rx_Quantity AS FLOAT), 0) > 0
          AND s.sf_terr_pk_gi IN ({ph}){'' if ctx.apply else f' AND NOT ({recent})'}
    """), tkeys).scalar()
    if base_max is None:
        print("    last_rx_date: no rows in scope")
        return

    offset = (ctx.rx_offset if ctx.rx_offset is not None
              else (ctx.today - base_max).days - RX_TARGET_DAYS_BACK)
    n = conn.execute(text(f"SELECT COUNT(*) FROM {SALES} WHERE sf_terr_pk_gi IN ({ph})"),
                     tkeys).scalar()
    print(f"    last_rx_date: newest {base_max}, offset {offset:+d} days,"
          f" {n} rows -> {base_max + timedelta(days=offset)}")

    if ctx.apply:
        res = conn.execute(text(f"""
            UPDATE {SALES}
            SET Month_Ending_Date =
                CONVERT(varchar(10), DATEADD(day, :off, TRY_CAST(Month_Ending_Date AS DATE)), 120)
                + ' 00:00:00.0000000'
            WHERE sf_terr_pk_gi IN ({ph})
        """), {**tkeys, "off": offset})
        print(f"    last_rx_date: shifted {res.rowcount} rows  (undo: --rx-offset-days {-offset})")


def part_calls(conn, ctx) -> None:
    """Call_Date -> engagement scoring, which is 30% of ai_score.

    load_call_stats only counts calls in the last 90 days. The call history stops
    well before that window, so every HCP scores days_since_last_call=None and
    call_count_90d=0, landing on an identical engagement floor -- which is why
    every LOW HCP reports the same ai_score.

    A CONSTANT offset matters here. The spread already exists in the data (one to
    a hundred-odd calls per HCP); shifting rows individually would flatten the
    very differences that make the scores differ.
    """
    ph, tkeys = in_clause("t", ctx.territories)
    newest = conn.execute(text(f"""
        SELECT MAX(TRY_CAST(Call_Date AS DATE)) FROM {CALLS} WHERE sf_terr_pk_gi IN ({ph})
    """), tkeys).scalar()
    if newest is None:
        print("    call history: no rows in scope")
        return

    offset = (ctx.call_offset if ctx.call_offset is not None
              else (ctx.today - newest).days - CALL_TARGET_DAYS_BACK)
    n = conn.execute(text(f"SELECT COUNT(*) FROM {CALLS} WHERE sf_terr_pk_gi IN ({ph})"),
                     tkeys).scalar()
    print(f"    call history: newest {newest}, offset {offset:+d} days,"
          f" {n} rows -> {newest + timedelta(days=offset)}")

    if ctx.apply:
        res = conn.execute(text(f"""
            UPDATE {CALLS}
            SET Call_Date =
                CONVERT(varchar(10), DATEADD(day, :off, TRY_CAST(Call_Date AS DATE)), 120)
                + ' 00:00:00.0000000'
            WHERE sf_terr_pk_gi IN ({ph})
        """), {**tkeys, "off": offset})
        print(f"    call history: shifted {res.rowcount} rows  (undo: --call-offset-days {-offset})")


_TIME_RE = re.compile(r"(\d{1,2}:\d{2})")


def part_alerts(conn, ctx) -> None:
    """Detection_Datetime -> detected_at, keeping each alert's time of day.

    Stored as 'YYYY-MM-DD HH:MM'. Only the date part moves, so timestamps still
    read as plausible working hours instead of all sitting at midnight.

    This column is what alert_engine sorts on (newest first within a severity
    band), so re-randomising reshuffles the order inside a band. Severity leads.
    """
    rows = conn.execute(text(f"SELECT Alert_Id AS ident, Detection_Datetime AS cur FROM {ALERTS}")).fetchall()
    plan = OrderedDict()
    for r in rows:
        d = ctx.today - timedelta(days=ctx.rnd.randint(*ALERT_DAYS_BACK))
        m = _TIME_RE.search(r.cur or "")
        hhmm = f"{int(m.group(1).split(':')[0]):02d}:{m.group(1).split(':')[1]}" if m else "09:00"
        plan[r.ident] = {"cur": r.cur, "new": f"{d:%Y-%m-%d} {hhmm}"}

    show(plan, "detected_at")
    if ctx.apply and plan:
        simple_update(conn, ALERTS, "Detection_Datetime", "Alert_Id", plan, "detected_at")


def part_signals(conn, ctx) -> None:
    """Detection_Date -> signal_date. Date only, no time component.

    Note the rename across layers: the column and model attribute say
    "detection", the API key says "signal".
    """
    rows = conn.execute(text(f"SELECT Signal_Id AS ident, Detection_Date AS cur FROM {SIGNALS}")).fetchall()
    plan = OrderedDict()
    for r in rows:
        d = ctx.today - timedelta(days=ctx.rnd.randint(*SIGNAL_DAYS_BACK))
        plan[r.ident] = {"cur": r.cur, "new": f"{d:%Y-%m-%d}"}

    show(plan, "signal_date")
    if ctx.apply and plan:
        simple_update(conn, SIGNALS, "Detection_Date", "Signal_Id", plan, "signal_date")


def part_payer(conn, ctx) -> None:
    """Change_Date -> change_date, skipping plans that never had one.

    Change_Date is only populated where Recent_Tier_Change = 'Yes'; the rest hold
    an empty string and the service turns that into null. Writing a date into
    those rows would have a plan claiming a tier-change date while also reporting
    no tier change, so they are left alone.
    """
    rows = conn.execute(text(f"""
        SELECT Plan_Durable_Id AS ident, Change_Date AS cur, Recent_Tier_Change AS changed
        FROM {PAYER}
    """)).fetchall()

    plan, skipped = OrderedDict(), 0
    for r in rows:
        if r.cur and str(r.cur).strip():
            d = ctx.today - timedelta(days=ctx.rnd.randint(*PAYER_DAYS_BACK))
            plan[r.ident] = {"cur": r.cur, "new": f"{d:%Y-%m-%d}"}
        else:
            skipped += 1

    show(plan, "change_date")
    if skipped:
        print(f"      ({skipped} plans left unchanged - no tier change on file)")
    if ctx.apply and plan:
        simple_update(conn, PAYER, "Change_Date", "Plan_Durable_Id", plan, "change_date")


# 'Mar 15 - Apr 22' -> month, day, separator run, month, day
_PERIOD_RE = re.compile(r"^\s*([A-Za-z]{3,9})\s+(\d{1,2})(\s*\S\s*)([A-Za-z]{3,9})\s+(\d{1,2})\s*$")
_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def part_objections(conn, ctx) -> None:
    """Detection_Period -> BOTH the period and ai_date_range keys.

    mlr_response_engine maps detection_period to both, so one column update moves
    both. Only the two month names change: start -> previous month, end ->
    current month. Day numbers, spacing and the separator are preserved -- the
    separator in the warehouse is an en dash (U+2013), not a hyphen, and is
    carried through rather than rewritten.

    Anything not matching 'Mon D <sep> Mon D' is reported and left alone, so an
    unexpected format is never silently mangled.
    """
    prev_m = _MONTHS[(ctx.today.month - 2) % 12]
    cur_m = _MONTHS[ctx.today.month - 1]

    rows = conn.execute(text(f"""
        SELECT {'Detection_Period'} AS cur, COUNT(*) AS n
        FROM {OBJECTIONS} WHERE Detection_Period IS NOT NULL GROUP BY Detection_Period
    """)).fetchall()

    plan, bad = OrderedDict(), 0
    for r in rows:
        m = _PERIOD_RE.match(r.cur or "")
        if not m:
            bad += 1
            continue
        _, d1, sep, _, d2 = m.groups()
        new = f"{prev_m} {d1}{sep}{cur_m} {d2}"
        if new != r.cur:
            plan[r.cur] = {"cur": r.cur, "new": new, "n": r.n}

    if not plan:
        print("    period / ai_date_range: nothing to change")
    else:
        print(f"    period / ai_date_range: {len(plan)} distinct values")
        for old, v in plan.items():
            print(f"      {old:<22} -> {v['new']:<22} ({v['n']} rows)")
    if bad:
        print(f"      ({bad} skipped - unrecognised format)")

    if ctx.apply and plan:
        total = 0
        for old, v in plan.items():
            res = conn.execute(text(f"""
                UPDATE {OBJECTIONS} SET Detection_Period = :new WHERE Detection_Period = :old
            """), {"new": v["new"], "old": old})
            total += res.rowcount or 0
        print(f"    period / ai_date_range: {total} rows")


PARTS = OrderedDict([
    ("call",       (part_call,       "last_call_date   Modified_Date        10-15 days back")),
    ("nrx",        (part_nrx,        "last_nrx_date    Week_Ending_Date     30-40 days back")),
    ("rx-shift",   (part_rx_shift,   "last_rx_date     Month_Ending_Date    constant offset, keeps tiers")),
    ("calls",      (part_calls,      "engagement       Call_Date            constant offset, varies ai_score")),
    ("alerts",     (part_alerts,     "detected_at      Detection_Datetime   10-15 days back")),
    ("signals",    (part_signals,    "signal_date      Detection_Date       13-18 days back")),
    ("payer",      (part_payer,      "change_date      Change_Date          8-14 days back")),
    ("objections", (part_objections, "period+range     Detection_Period     previous -> current month")),
    ("rx-perrow",  (part_rx_perrow,  "last_rx_date     Month_Ending_Date    20-30 days back  [OPT-IN, breaks tiers]")),
])

DEFAULT_PARTS = [p for p in PARTS if p != "rx-perrow"]


class Ctx:
    def __init__(self, args, territories):
        self.today = date.today()
        self.rnd = random.Random(args.seed)
        self.apply = args.apply
        self.territories = territories
        self.rx_offset = args.rx_offset_days
        self.call_offset = args.call_offset_days


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Refresh every demo-data date across all modules.",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="Write the changes (default is a dry run).")
    ap.add_argument("--only", help="Comma-separated parts to run instead of the default set.")
    ap.add_argument("--exclude", help="Comma-separated parts to skip.")
    ap.add_argument("--seed", type=int, default=None, help="Fix the random seed.")
    ap.add_argument("--rx-offset-days", type=int, default=None,
                    help="Exact offset for rx-shift. Negative undoes a previous shift.")
    ap.add_argument("--call-offset-days", type=int, default=None,
                    help="Exact offset for calls. Negative undoes a previous shift.")
    ap.add_argument("--list", action="store_true", help="List the parts and exit.")
    args = ap.parse_args()

    if args.list:
        print("\n  parts (default set runs everything except rx-perrow):\n")
        for name, (_, desc) in PARTS.items():
            mark = " " if name in DEFAULT_PARTS else "*"
            print(f"   {mark} {name:<11} {desc}")
        print("\n   * opt-in only\n")
        return 0

    selected = ([p.strip() for p in args.only.split(",") if p.strip()]
                if args.only else list(DEFAULT_PARTS))
    if args.exclude:
        drop = {p.strip() for p in args.exclude.split(",") if p.strip()}
        selected = [p for p in selected if p not in drop]

    unknown = [p for p in selected if p not in PARTS]
    if unknown:
        ap.error(f"unknown part(s): {', '.join(unknown)}. Try --list.")
    if "rx-shift" in selected and "rx-perrow" in selected:
        ap.error("rx-shift and rx-perrow both write Month_Ending_Date in opposite "
                 "ways -- pick one. rx-shift is the one that keeps the tiers.")
    if not selected:
        ap.error("no parts selected")

    territories = org_tree_territories()

    print("=" * 78)
    print("  update_date.py")
    print("=" * 78)
    print(f"  today       : {date.today()}")
    print(f"  territories : {len(territories)}")
    for t in territories:
        print(f"                - {t}")
    print(f"  parts       : {', '.join(selected)}")
    print(f"  mode        : {'APPLY (writes)' if args.apply else 'DRY RUN (no writes)'}")
    if "rx-perrow" in selected:
        print("  WARNING     : rx-perrow flattens every ai_priority_tier to LOW.")

    ctx = Ctx(args, territories)
    with engine.connect() as conn:
        for name in selected:
            print(f"\n  [{name}]")
            try:
                PARTS[name][0](conn, ctx)
            except Exception as exc:  # noqa: BLE001
                # One failing module must not abandon the rest of the refresh.
                print(f"    FAILED: {type(exc).__name__}: {str(exc).splitlines()[0][:120]}")

    if not args.apply:
        print("\n  DRY RUN - nothing was written. Re-run with --apply.")
        return 0

    print("\n  Clear caches and restart the server:")
    print("      python scripts/clear_cache.py")
    print("      (the ranked HCP list is cached in-process - only a restart drops it)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
