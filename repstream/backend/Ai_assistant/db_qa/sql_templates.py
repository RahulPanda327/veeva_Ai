# """
# SQL templates for the Ops chatbot — sourced from the
# "GUI Chatbot – Sample Questions & SQL Mapping" doc.

# Each template has:
#   id            — stable identifier
#   intent        — coarse category (file.status.today, qc.recent, …)
#   description   — human label (can use {param} placeholders)
#   category      — UI grouping
#   patterns      — regex list; groups become positional params
#   param_names   — names for the regex groups, in order
#   sql           — parameterized SQL with `?` placeholders
#   bind_template — list of strings; {param} gets substituted from extracted groups,
#                   then the resulting list is bound to the `?` placeholders
#   chart_hint    — None, or {"type", "x", "y"} to drive chart generation

# The SQL is verbatim from the doc, reformatted to single-line where appropriate
# and switched to `?` parameter binding for any user-supplied values.
# """

# # ────────────────────────────────────────────────────────────────────────────────
# # Shared SQL fragments
# # ────────────────────────────────────────────────────────────────────────────────

# FILE_LOG_JOIN = (
#     "SELECT hdfl.processed_date, hdfl.dds_record_count, hdfl.status, hdf.short_name "
#     "FROM hub_md.hub_data_file_log hdfl WITH (NOLOCK) "
#     "INNER JOIN hub_md.hub_data_feed hdf WITH (NOLOCK) "
#     "ON hdf.feed_id = hdfl.feed_id"
# )

# # ────────────────────────────────────────────────────────────────────────────────
# # Templates
# # ────────────────────────────────────────────────────────────────────────────────

# DB_TEMPLATES: list[dict] = [

#     # ── Schedule Monitoring ──────────────────────────────────────────────────
#     {
#         "id": "scheduled_today",
#         "intent": "schedule.today",
#         "category": "Schedule Monitoring",
#         "description": "Files scheduled to load today",
#         "patterns": [
#             r"\b(file|files)\b.*\bschedule(d)?\b.*\btoday\b",
#             r"\bwhat.*schedule(d)?.*today\b",
#             r"\btoday.*schedule(d)?\b",
#         ],
#         "param_names": [],
#         "sql": (
#             "SELECT * FROM hub_md.vw_ops_inventory WITH (NOLOCK) "
#             "WHERE schedule_automation LIKE '%' + LEFT(DATENAME(WEEKDAY, GETDATE()), 3) + '%'"
#         ),
#         "bind_template": [],
#         "chart_hint": None,
#     },
#     {
#         "id": "scheduled_tomorrow",
#         "intent": "schedule.tomorrow",
#         "category": "Schedule Monitoring",
#         "description": "Files scheduled to load tomorrow",
#         "patterns": [
#             r"\b(file|files)\b.*\bschedule(d)?\b.*\btomorrow\b",
#             r"\bwhat.*schedule(d)?.*tomorrow\b",
#         ],
#         "param_names": [],
#         "sql": (
#             "SELECT * FROM hub_md.vw_ops_inventory WITH (NOLOCK) "
#             "WHERE schedule_automation LIKE '%' + LEFT(DATENAME(WEEKDAY, DATEADD(DAY, 1, GETDATE())), 3) + '%'"
#         ),
#         "bind_template": [],
#         "chart_hint": None,
#     },

#     # ── Missed / Failed / Delayed ─────────────────────────────────────────────
#     {
#         "id": "missed_today",
#         "intent": "missed.today",
#         "category": "Missed File Monitoring",
#         "description": "Files missed today",
#         "patterns": [
#             r"\bmissed\b.*\b(file|files)\b.*\btoday\b",
#             r"\bany\s+missed\b.*\btoday\b",
#         ],
#         "param_names": [],
#         "sql": (
#             "SELECT TOP 100 * FROM hub_md.vw_runbook_history WITH (NOLOCK) "
#             "WHERE processed_date = CAST(GETDATE() AS DATE) "
#             "AND processing_status = 'MISSED'"
#         ),
#         "bind_template": [],
#         "chart_hint": None,
#     },
#     {
#         "id": "failed_today",
#         "intent": "failed.today",
#         "category": "Failure Monitoring",
#         "description": "Files that failed today",
#         "patterns": [
#             r"\b(file|files)\b.*\bfail(ed|ing)?\b.*\btoday\b",
#             r"\bfail(ed|ure)\b.*\btoday\b",
#         ],
#         "param_names": [],
#         "sql": (
#             "SELECT TOP 100 * FROM hub_md.vw_runbook_history WITH (NOLOCK) "
#             "WHERE processed_date = CAST(GETDATE() AS DATE) "
#             "AND processing_status = 'FAILED'"
#         ),
#         "bind_template": [],
#         "chart_hint": None,
#     },
#     {
#         "id": "delayed_today",
#         "intent": "delayed.today",
#         "category": "Delay Monitoring",
#         "description": "Files delayed today",
#         "patterns": [
#             r"\bdelay(ed)?\b.*\btoday\b",
#             r"\b(file|files)\b.*\bdelay(ed)?\b",
#         ],
#         "param_names": [],
#         "sql": (
#             "SELECT * FROM hub_md.vw_runbook_history WITH (NOLOCK) "
#             "WHERE CAST(processed_date AS DATE) = CAST(GETDATE() AS DATE) "
#             "AND processing_status = 'DELAYED' "
#             "ORDER BY processed_date DESC"
#         ),
#         "bind_template": [],
#         "chart_hint": None,
#     },

#     # ── File Load Status (by feed name) ───────────────────────────────────────
#     {
#         "id": "file_status_named_today",
#         "intent": "file.status.today",
#         "category": "File Load Status",
#         "description": "Status of '{name}' file load today",
#         "patterns": [
#             r"\bstatus of (?:today.?s )?(?P<name>[\w\-]+) file load",
#             r"\bwhen did (?:the )?(?P<name>[\w\-]+) file load today",
#             r"\bload status.*\b(?P<name>[\w\-]+)\b.*\btoday\b",
#         ],
#         "param_names": ["name"],
#         "sql": (
#             FILE_LOG_JOIN +
#             " WHERE (hdf.subject_area LIKE ? OR hdf.src_name LIKE ? OR hdf.file_body LIKE ?)"
#             " AND CAST(hdfl.processed_date AS DATE) = CAST(GETDATE() AS DATE)"
#         ),
#         "bind_template": ["%{name}%", "%{name}%", "%{name}%"],
#         "chart_hint": None,
#     },

#     # ── Historical Loads ──────────────────────────────────────────────────────
#     {
#         "id": "loaded_yesterday",
#         "intent": "loaded.yesterday",
#         "category": "Historical File Loads",
#         "description": "Files loaded yesterday",
#         "patterns": [
#             r"\b(file|files)\b.*\bload(ed)?\b.*\byesterday\b",
#             r"\byesterday.*load(ed)?\b",
#         ],
#         "param_names": [],
#         "sql": (
#             FILE_LOG_JOIN +
#             " WHERE CAST(hdfl.processed_date AS DATE) = CAST(DATEADD(DAY, -1, GETDATE()) AS DATE)"
#         ),
#         "bind_template": [],
#         "chart_hint": None,
#     },
#     {
#         "id": "loaded_last_24h",
#         "intent": "loaded.last_24h",
#         "category": "Historical File Loads",
#         "description": "Files loaded in the last 24 hours",
#         "patterns": [
#             r"\bload(ed)?\b.*\blast\s*24\s*hours?\b",
#             r"\blast\s*24\s*hours?\b.*\bload(ed)?\b",
#             r"\bload(ed)?\b.*\bpast\s*day\b",
#         ],
#         "param_names": [],
#         "sql": (
#             FILE_LOG_JOIN +
#             " WHERE hdfl.processed_date >= DATEADD(HOUR, -24, GETDATE())"
#         ),
#         "bind_template": [],
#         "chart_hint": None,
#     },

#     # ── Record-count metric (by feed name) ────────────────────────────────────
#     {
#         "id": "dds_count_named_today",
#         "intent": "metric.dds_count.today",
#         "category": "Record Count / Metrics",
#         "description": "DDS count for '{name}' loaded today",
#         "patterns": [
#             # Anchored: capture the word right after "of"/"for", not the first noise word
#             r"\b(?:dds|record)\s*count\s+(?:of|for)\s+(?P<name>[\w\-]+)\b",
#             r"\bhow\s+many\s+records?\s+(?:did|were|for|of|in)\s+(?P<name>[\w\-]+)\b",
#             # Fallback: explicit "<name> file" before "today"
#             r"\b(?:dds|record)\s*count.*?\b(?P<name>[\w\-]+)\s+file\b.*?\btoday\b",
#         ],
#         "param_names": ["name"],
#         "sql": (
#             FILE_LOG_JOIN +
#             " WHERE (hdf.subject_area LIKE ? OR hdf.src_name LIKE ? OR hdf.file_body LIKE ?)"
#             " AND CAST(hdfl.processed_date AS DATE) = CAST(GETDATE() AS DATE)"
#         ),
#         "bind_template": ["%{name}%", "%{name}%", "%{name}%"],
#         "chart_hint": None,
#     },

#     # ── QC monitoring (last N days) ───────────────────────────────────────────
#     {
#         "id": "qc_triggered_last_n",
#         "intent": "qc.recent",
#         "category": "QC Monitoring",
#         "description": "QC triggered in the last {days} days",
#         "patterns": [
#             r"\bqc\b.*?\blast\s*(?P<days>\d+)\s*days?\b",
#             r"\bqc\b.*?\b(?P<days>\d+)\s*days?\b",
#             r"\bany\s+qc\b.*\b(triggered|fired|run|recent|today|last)\b",
#             r"\bqc\s+(triggered|result|check|issue|alert)\b",
#         ],
#         "param_names": ["days"],
#         "default_params": {"days": 3},
#         "sql": (
#             "SELECT df.subject_area AS [Subject Area], df.short_name AS [Feed Short Name], "
#             "dfl.processed_date AS [Processed Date], qcr.qc_message AS [QC Message], "
#             "dfl.dds_table AS [Table], df.feed_id AS [Feed id], dfl.file_id AS [File id], "
#             "qcr.record_id AS [Record id] "
#             "FROM hub_md.hub_data_file_log dfl WITH (NOLOCK) "
#             "INNER JOIN hub_md.hub_data_feed df WITH (NOLOCK) ON dfl.feed_id = df.feed_id "
#             "JOIN ("
#             "  SELECT file_id, feed_id, NULL AS record_id, qc_message "
#             "  FROM hub_md.hub_qc_sql_result WITH (NOLOCK) "
#             "  WHERE record_cnt > 0 AND cre_dt >= CAST(DATEADD(DAY, -?, GETDATE()) AS DATE) "
#             "  AND cre_dt <= GETDATE() "
#             "  UNION "
#             "  SELECT DISTINCT file_id, feed_id, NULL AS record_id, qc_message "
#             "  FROM hub_md.hub_feed_qc_results WITH (NOLOCK) "
#             "  WHERE cre_dt >= CAST(DATEADD(DAY, -?, GETDATE()) AS DATE) AND cre_dt <= GETDATE()"
#             ") qcr ON dfl.file_id = qcr.file_id AND dfl.feed_id = qcr.feed_id "
#             "WHERE processed_date >= CAST(DATEADD(DAY, -?, GETDATE()) AS DATE) "
#             "AND processed_date <= GETDATE() "
#             "ORDER BY dfl.file_id DESC"
#         ),
#         "bind_template": ["{days}", "{days}", "{days}"],
#         "chart_hint": None,
#     },
#     {
#         "id": "qc_failed_recent",
#         "intent": "qc.failed.recent",
#         "category": "QC / Validation Monitoring",
#         "description": "Tables that failed QC in the most recent run",
#         "patterns": [
#             r"\b(tables?|feeds?)\b.*\bfail(ed)?\s*qc\b.*\b(recent|latest)\b",
#             r"\bfail(ed)?\s*qc\b.*\bmost\s*recent\b",
#         ],
#         "param_names": [],
#         "sql": (
#             "SELECT qc.feed_id, qc.File_id, hdf.short_name, qc.qc_message, qc.cre_dt "
#             "FROM hub_md.hub_qc_sql_result qc WITH (NOLOCK) "
#             "INNER JOIN hub_md.hub_data_feed hdf WITH (NOLOCK) ON qc.feed_id = hdf.feed_id "
#             "WHERE qc.cre_dt = (SELECT MAX(cre_dt) FROM hub_md.hub_qc_sql_result WITH (NOLOCK)) "
#             "ORDER BY hdf.short_name"
#         ),
#         "bind_template": [],
#         "chart_hint": None,
#     },

#     # ── Feed search ──────────────────────────────────────────────────────────
#     {
#         "id": "feed_search_named",
#         "intent": "feed.search",
#         "category": "Feed Search",
#         "description": "Feeds related to '{name}'",
#         "patterns": [
#             r"\b(search|find)\b.*\bfeeds?\b.*\b(?:related to|for|about)\s+(?P<name>[\w\-]+)",
#             r"\bshow\s+details?\s+(?:for|of)\s+(?P<name>[\w\-]+)\s+feed",
#             r"\bfeeds?\s+related\s+to\s+(?P<name>[\w\-]+)",
#             r"\bsearch\s+feeds?.*\b(?P<name>[\w\-]+)",
#             r"\bshow.*\b(?P<name>[\w\-]+)\s+feed\b",
#         ],
#         "param_names": ["name"],
#         "sql": (
#             "SELECT * FROM hub_md.hub_data_feed WITH (NOLOCK) "
#             "WHERE subject_area LIKE ? OR src_name LIKE ? OR file_body LIKE ?"
#         ),
#         "bind_template": ["%{name}%", "%{name}%", "%{name}%"],
#         "chart_hint": None,
#     },
#     {
#         "id": "table_for_named",
#         "intent": "feed.table_lookup",
#         "category": "Feed Search",
#         "description": "Tables that load '{name}' data",
#         "patterns": [
#             # Anchor immediately after "loads" so we grab the feed name, not "data"
#             r"\bwhich\s+tables?\s+loads?\s+(?P<name>[\w\-]+)",
#             r"\btables?\s+(?:that\s+)?loads?\s+(?P<name>[\w\-]+)",
#             r"\b(?P<name>[\w\-]+)\s+(?:data|file)?\s*load(?:ed|s)?\s+into\s+which\s+tables?\b",
#         ],
#         "param_names": ["name"],
#         "sql": (
#             "SELECT DISTINCT hdfl.dds_table, hdf.short_name, hdf.subject_area "
#             "FROM hub_md.hub_data_file_log hdfl WITH (NOLOCK) "
#             "INNER JOIN hub_md.hub_data_feed hdf WITH (NOLOCK) ON hdfl.feed_id = hdf.feed_id "
#             "WHERE hdf.subject_area LIKE ? OR hdf.src_name LIKE ? OR hdf.file_body LIKE ?"
#         ),
#         "bind_template": ["%{name}%", "%{name}%", "%{name}%"],
#         "chart_hint": None,
#     },

#     # ── Trend analysis (chart-worthy) ────────────────────────────────────────
#     {
#         "id": "history_last_n_named",
#         "intent": "trend.history",
#         "category": "Trend Analysis",
#         "description": "Last {days} days load history for '{name}'",
#         "patterns": [
#             # Anchor on "for <name>" so we grab the feed name, not the word "for"
#             r"\blast\s+(?P<days>\d+)\s+days?\s+load\s+history\s+for\s+(?P<name>[\w\-]+)",
#             r"\b(?P<days>\d+)\s+days?\s+(?:load\s+)?history\s+for\s+(?P<name>[\w\-]+)",
#             r"\bload\s+history\s+for\s+(?P<name>[\w\-]+)\s+(?:last|past)\s+(?P<days>\d+)\s+days?",
#             r"\btrend\s+for\s+(?P<name>[\w\-]+)\s+last\s+(?P<days>\d+)\s+days?",
#         ],
#         "param_names": ["days", "name"],
#         "sql": (
#             "SELECT CAST(hdfl.processed_date AS DATE) AS processed_day, hdf.short_name, "
#             "hdfl.status, hdfl.dds_record_count "
#             "FROM hub_md.hub_data_file_log hdfl WITH (NOLOCK) "
#             "INNER JOIN hub_md.hub_data_feed hdf WITH (NOLOCK) ON hdfl.feed_id = hdf.feed_id "
#             "WHERE (hdf.subject_area LIKE ? OR hdf.src_name LIKE ? OR hdf.file_body LIKE ?) "
#             "AND hdfl.processed_date >= DATEADD(DAY, -?, GETDATE()) "
#             "ORDER BY hdfl.processed_date DESC"
#         ),
#         "bind_template": ["%{name}%", "%{name}%", "%{name}%", "{days}"],
#         "chart_hint": {"type": "line", "x": "processed_day", "y": "dds_record_count"},
#     },

#     # ── Active feeds ─────────────────────────────────────────────────────────
#     # NOTE: the named-subject variant MUST be listed before the generic
#     # subject-areas template — otherwise "for subject area accredo … active"
#     # would match the generic template first and the name is lost.
#     {
#         "id": "active_feeds_for_subject",
#         "intent": "feeds.active.for_subject",
#         "category": "Active Feeds",
#         "description": "Active feeds for subject area '{name}'",
#         "patterns": [
#             r"\bsubject[\s_]area\s+(?P<name>[\w\-]+)\b.*\bactive\b",
#             r"\bfor\s+subject[\s_]area\s+(?P<name>[\w\-]+)\b",
#             r"\bactive\s+feeds?\b.*\bfor\s+(?P<name>[\w\-]+)\b",
#         ],
#         "param_names": ["name"],
#         "sql": (
#             "SELECT hdf.subject_area, hdf.short_name, hdf.file_body, "
#             "hdfv.stg_table_name, hdfv.dds_table_name, hdf.entity_master_order "
#             "FROM hub_md.hub_data_feed hdf WITH (NOLOCK) "
#             "INNER JOIN hub_md.hub_data_feed_version hdfv WITH (NOLOCK) ON hdf.feed_id = hdfv.feed_id "
#             "WHERE hdf.subject_area = ? AND hdf.actv_ind = 1 "
#             "ORDER BY hdf.entity_master_order"
#         ),
#         "bind_template": ["{name}"],
#         "chart_hint": None,
#     },
#     {
#         "id": "active_subject_areas",
#         "intent": "feeds.active.subject_areas",
#         "category": "Active Feeds",
#         "description": "Subject areas with active feeds",
#         "patterns": [
#             r"\bwhich\s+subject\s+areas?\b.*\bactive\b",
#             r"\bwhat\s+subject\s+areas?\b.*\bactive\b",
#             r"\bsubject\s+areas?\b.*\bactive\s+feeds?\b",
#             r"\bactive\b.*\bsubject\s+areas?\b",
#         ],
#         "param_names": [],
#         "sql": (
#             "SELECT DISTINCT subject_area, short_name, actv_ind "
#             "FROM hub_md.hub_data_feed WITH (NOLOCK) "
#             "WHERE actv_ind = 1 "
#             "ORDER BY subject_area, short_name"
#         ),
#         "bind_template": [],
#         "chart_hint": {"type": "count_bar", "x": "subject_area", "y": None},
#     },

#     # ── Latest successful load (subject) ─────────────────────────────────────
#     {
#         "id": "latest_success_for_subject",
#         "intent": "load.latest_success",
#         "category": "Load Monitoring",
#         "description": "Latest successful load for each feed in subject area '{name}'",
#         "patterns": [
#             # Canonical: "...subject_area 'accredo'..." (single/double quotes optional, "_" or space)
#             r"\blatest\s+(?:successful\s+)?load\b.*?\bsubject[\s_]area[\s'\"]+(?P<name>[\w\-]+)",
#             # "latest successful load for accredo" (no subject_area keyword)
#             r"\blatest\s+(?:successful\s+)?load\s+for\s+(?P<name>[\w\-]+)\b",
#             # "latest load in subject area accredo"
#             r"\blatest\s+load\b.*?\bin\s+subject[\s_]area\s+(?P<name>[\w\-]+)\b",
#         ],
#         "param_names": ["name"],
#         "sql": (
#             "SELECT hdf.subject_area, hdf.short_name, hdfl.file_id, hdfl.processed_date, "
#             "hdfl.stg_record_count, hdfl.archive_loc "
#             "FROM hub_md.hub_data_file_log hdfl WITH (NOLOCK) "
#             "INNER JOIN hub_md.hub_data_feed hdf WITH (NOLOCK) ON hdfl.feed_id = hdf.feed_id "
#             "WHERE hdf.subject_area = ? AND hdfl.status = 5 "
#             "AND hdfl.processed_date = ("
#             "  SELECT MAX(processed_date) FROM hub_md.hub_data_file_log hdfl2 WITH (NOLOCK) "
#             "  WHERE hdfl2.feed_id = hdfl.feed_id AND hdfl2.status = 5"
#             ") ORDER BY hdfl.processed_date DESC"
#         ),
#         "bind_template": ["{name}"],
#         "chart_hint": None,
#     },
# ]





"""
SQL templates for the Ops chatbot — sourced from the
"GUI Chatbot – Sample Questions & SQL Mapping" doc.

Each template has:
  id            — stable identifier
  intent        — coarse category (file.status.today, qc.recent, …)
  description   — human label (can use {param} placeholders)
  category      — UI grouping
  patterns      — regex list; groups become positional params
  param_names   — names for the regex groups, in order
  sql           — parameterized SQL with `?` placeholders
  bind_template — list of strings; {param} gets substituted from extracted groups,
                  then the resulting list is bound to the `?` placeholders
  chart_hint    — None, or {"type", "x", "y"} to drive chart generation

The SQL is verbatim from the doc, reformatted to single-line where appropriate
and switched to `?` parameter binding for any user-supplied values.
"""

# ────────────────────────────────────────────────────────────────────────────────
# Shared SQL fragments
# ────────────────────────────────────────────────────────────────────────────────

FILE_LOG_JOIN = (
    "SELECT hdfl.processed_date, hdfl.dds_record_count, hdfl.status, hdf.short_name "
    "FROM hub_md.hub_data_file_log hdfl WITH (NOLOCK) "
    "INNER JOIN hub_md.hub_data_feed hdf WITH (NOLOCK) "
    "ON hdf.feed_id = hdfl.feed_id"
)

# ────────────────────────────────────────────────────────────────────────────────
# Templates
# ────────────────────────────────────────────────────────────────────────────────

DB_TEMPLATES: list[dict] = [

    # ── Schedule Monitoring ──────────────────────────────────────────────────
    {
        "id": "scheduled_today",
        "intent": "schedule.today",
        "category": "Schedule Monitoring",
        "description": "Files scheduled to load today",
        "patterns": [
            r"\b(file|files)\b.*\bschedule(d)?\b.*\btoday\b",
            r"\bwhat.*schedule(d)?.*today\b",
            r"\btoday.*schedule(d)?\b",
        ],
        "param_names": [],
        "sql": (
            "SELECT * FROM hub_md.vw_ops_inventory WITH (NOLOCK) "
            "WHERE schedule_automation LIKE '%' + LEFT(DATENAME(WEEKDAY, GETDATE()), 3) + '%'"
        ),
        "bind_template": [],
        "chart_hint": None,
    },
    {
        "id": "scheduled_tomorrow",
        "intent": "schedule.tomorrow",
        "category": "Schedule Monitoring",
        "description": "Files scheduled to load tomorrow",
        "patterns": [
            r"\b(file|files)\b.*\bschedule(d)?\b.*\btomorrow\b",
            r"\bwhat.*schedule(d)?.*tomorrow\b",
        ],
        "param_names": [],
        "sql": (
            "SELECT * FROM hub_md.vw_ops_inventory WITH (NOLOCK) "
            "WHERE schedule_automation LIKE '%' + LEFT(DATENAME(WEEKDAY, DATEADD(DAY, 1, GETDATE())), 3) + '%'"
        ),
        "bind_template": [],
        "chart_hint": None,
    },

    # ── Missed / Failed / Delayed ─────────────────────────────────────────────
    {
        "id": "missed_today",
        "intent": "missed.today",
        "category": "Missed File Monitoring",
        "description": "Files missed today",
        "patterns": [
            r"\bmissed\b.*\b(file|files)\b.*\btoday\b",
            r"\bany\s+missed\b.*\btoday\b",
        ],
        "param_names": [],
        "sql": (
            "SELECT TOP 100 * FROM hub_md.vw_runbook_history WITH (NOLOCK) "
            "WHERE processed_date = CAST(GETDATE() AS DATE) "
            "AND processing_status = 'MISSED'"
        ),
        "bind_template": [],
        "chart_hint": None,
    },
    {
        "id": "failed_today_with_reasons",
        "intent": "failed.today.reasons",
        "category": "Failure Monitoring",
        "description": "Today's failed imports with failure reasons",
        "patterns": [
            r"\bfail(ed|ure)?\b.*\breason(s)?\b",
            r"\breason(s)?\b.*\bfail(ed|ure)?\b",
        ],
        "param_names": [],
        "sql": (
            "SELECT rhd.subject_area AS [Subject Area], hdf.short_name AS [Feed Short Name], "
            "rhd.feed_id AS [Feed id], rhd.file_id AS [File id], "
            "rhd.processed_date AS [Processed Date], rhd.status AS [Status], "
            "qcr.qc_message AS [Failure Reason] "
            "FROM hub_md.vw_runbook_history_feed_details rhd WITH (NOLOCK) "
            "LEFT JOIN hub_md.hub_data_feed hdf WITH (NOLOCK) ON hdf.feed_id = rhd.feed_id "
            "LEFT JOIN ("
            "  SELECT file_id, feed_id, qc_message FROM hub_md.hub_qc_sql_result WITH (NOLOCK) "
            "  UNION "
            "  SELECT file_id, feed_id, qc_message FROM hub_md.hub_feed_qc_results WITH (NOLOCK)"
            ") qcr ON qcr.file_id = rhd.file_id AND qcr.feed_id = rhd.feed_id "
            "WHERE CAST(rhd.processed_date AS DATE) = CAST(GETDATE() AS DATE) "
            "AND rhd.status LIKE '%fail%' "
            "ORDER BY rhd.processed_date DESC"
        ),
        "bind_template": [],
        "chart_hint": None,
    },
    {
        "id": "failed_today",
        "intent": "failed.today",
        "category": "Failure Monitoring",
        "description": "Files that failed today",
        "patterns": [
            r"\b(file|files)\b.*\bfail(ed|ing)?\b.*\btoday\b",
            r"\bfail(ed|ure)\b.*\btoday\b",
            r"\btoday\b.*\bfail(ed|ure|ing)?\b",
        ],
        "param_names": [],
        "sql": (
            "SELECT TOP 100 * FROM hub_md.vw_runbook_history WITH (NOLOCK) "
            "WHERE processed_date = CAST(GETDATE() AS DATE) "
            "AND processing_status = 'FAILED'"
        ),
        "bind_template": [],
        "chart_hint": None,
    },
    {
        "id": "delayed_today",
        "intent": "delayed.today",
        "category": "Delay Monitoring",
        "description": "Files delayed today",
        "patterns": [
            r"\bdelay(ed)?\b.*\btoday\b",
            r"\b(file|files)\b.*\bdelay(ed)?\b",
        ],
        "param_names": [],
        "sql": (
            "SELECT * FROM hub_md.vw_runbook_history WITH (NOLOCK) "
            "WHERE CAST(processed_date AS DATE) = CAST(GETDATE() AS DATE) "
            "AND processing_status = 'DELAYED' "
            "ORDER BY processed_date DESC"
        ),
        "bind_template": [],
        "chart_hint": None,
    },

    # ── Load Performance ─────────────────────────────────────────────────────
    {
        "id": "longest_load_time",
        "intent": "load.time.longest",
        "category": "Load Performance",
        "description": "Feeds with the longest Staging/DDS load times",
        "patterns": [
            r"\blongest\b.*\b(stg|staging|dds)\b",
            r"\b(stg|staging|dds)\b.*\blongest\b",
            r"\bslowest\b.*\b(feed|feeds|load|loading)\b",
            r"\blongest\b.*\bload(ing)?\b",
        ],
        "param_names": [],
        "sql": (
            "SELECT TOP 50 hdf.short_name AS [Feed Short Name], hdf.subject_area AS [Subject Area], "
            "hdfl.processed_date AS [Processed Date], "
            "hdfl.load_stg_elapsed_time AS [Staging Load Time], "
            "hdfl.dds_elapsed_time AS [DDS Load Time], "
            "(ISNULL(hdfl.load_stg_elapsed_time, 0) + ISNULL(hdfl.dds_elapsed_time, 0)) AS [Total Load Time] "
            "FROM hub_md.hub_data_file_log hdfl WITH (NOLOCK) "
            "INNER JOIN hub_md.hub_data_feed hdf WITH (NOLOCK) ON hdf.feed_id = hdfl.feed_id "
            "ORDER BY (ISNULL(hdfl.load_stg_elapsed_time, 0) + ISNULL(hdfl.dds_elapsed_time, 0)) DESC"
        ),
        "bind_template": [],
        "chart_hint": None,
    },

    # ── Export Monitoring ────────────────────────────────────────────────────
    {
        "id": "export_frequency_by_source",
        "intent": "export.frequency",
        "category": "Export Dashboard",
        "description": "Export frequency by source",
        "patterns": [
            r"\bexport\b.*\bfrequen",
            r"\bfrequen\w*\b.*\bexport\b",
            r"\bexport\b.*\bcadence\b",
            r"\bdelivery\b.*\bfrequen",
        ],
        "param_names": [],
        "sql": (
            "SELECT subject_area AS [Source], frequency AS [Frequency] "
            "FROM hub_md.vw_ops_inventory WITH (NOLOCK) "
            "WHERE direction LIKE '%out%' "
            "ORDER BY subject_area"
        ),
        "bind_template": [],
        "chart_hint": None,
    },

    # ── File Load Status (by feed name) ───────────────────────────────────────
    {
        "id": "file_status_named_today",
        "intent": "file.status.today",
        "category": "File Load Status",
        "description": "Status of '{name}' file load today",
        "patterns": [
            r"\bstatus of (?:today.?s )?(?P<name>[\w\-]+) file load",
            r"\bwhen did (?:the )?(?P<name>[\w\-]+) file load today",
            r"\bload status.*\b(?P<name>[\w\-]+)\b.*\btoday\b",
        ],
        "param_names": ["name"],
        "sql": (
            FILE_LOG_JOIN +
            " WHERE (hdf.subject_area LIKE ? OR hdf.src_name LIKE ? OR hdf.file_body LIKE ?)"
            " AND CAST(hdfl.processed_date AS DATE) = CAST(GETDATE() AS DATE)"
        ),
        "bind_template": ["%{name}%", "%{name}%", "%{name}%"],
        "chart_hint": None,
    },

    # ── Historical Loads ──────────────────────────────────────────────────────
    {
        "id": "loaded_yesterday",
        "intent": "loaded.yesterday",
        "category": "Historical File Loads",
        "description": "Files loaded yesterday",
        "patterns": [
            r"\b(file|files)\b.*\bload(ed)?\b.*\byesterday\b",
            r"\byesterday.*load(ed)?\b",
        ],
        "param_names": [],
        "sql": (
            FILE_LOG_JOIN +
            " WHERE CAST(hdfl.processed_date AS DATE) = CAST(DATEADD(DAY, -1, GETDATE()) AS DATE)"
        ),
        "bind_template": [],
        "chart_hint": None,
    },
    {
        "id": "loaded_last_24h",
        "intent": "loaded.last_24h",
        "category": "Historical File Loads",
        "description": "Files loaded in the last 24 hours",
        "patterns": [
            r"\bload(ed)?\b.*\blast\s*24\s*hours?\b",
            r"\blast\s*24\s*hours?\b.*\bload(ed)?\b",
            r"\bload(ed)?\b.*\bpast\s*day\b",
        ],
        "param_names": [],
        "sql": (
            FILE_LOG_JOIN +
            " WHERE hdfl.processed_date >= DATEADD(HOUR, -24, GETDATE())"
        ),
        "bind_template": [],
        "chart_hint": None,
    },

    # ── Record-count metric (by feed name) ────────────────────────────────────
    {
        "id": "dds_count_named_today",
        "intent": "metric.dds_count.today",
        "category": "Record Count / Metrics",
        "description": "DDS count for '{name}' loaded today",
        "patterns": [
            # Anchored: capture the word right after "of"/"for", not the first noise word
            r"\b(?:dds|record)\s*count\s+(?:of|for)\s+(?P<name>[\w\-]+)\b",
            r"\bhow\s+many\s+records?\s+(?:did|were|for|of|in)\s+(?P<name>[\w\-]+)\b",
            # Fallback: explicit "<name> file" before "today"
            r"\b(?:dds|record)\s*count.*?\b(?P<name>[\w\-]+)\s+file\b.*?\btoday\b",
        ],
        "param_names": ["name"],
        "sql": (
            FILE_LOG_JOIN +
            " WHERE (hdf.subject_area LIKE ? OR hdf.src_name LIKE ? OR hdf.file_body LIKE ?)"
            " AND CAST(hdfl.processed_date AS DATE) = CAST(GETDATE() AS DATE)"
        ),
        "bind_template": ["%{name}%", "%{name}%", "%{name}%"],
        "chart_hint": None,
    },

    # ── QC monitoring (last N days) ───────────────────────────────────────────
    {
        "id": "qc_triggered_last_n",
        "intent": "qc.recent",
        "category": "QC Monitoring",
        "description": "QC triggered in the last {days} days",
        "patterns": [
            r"\bqc\b.*?\blast\s*(?P<days>\d+)\s*days?\b",
            r"\bqc\b.*?\b(?P<days>\d+)\s*days?\b",
            r"\bany\s+qc\b.*\b(triggered|fired|run|recent|today|last)\b",
            r"\bqc\s+(triggered|result|check|issue|alert)\b",
        ],
        "param_names": ["days"],
        "default_params": {"days": 3},
        "sql": (
            "SELECT df.subject_area AS [Subject Area], df.short_name AS [Feed Short Name], "
            "dfl.processed_date AS [Processed Date], qcr.qc_message AS [QC Message], "
            "dfl.dds_table AS [Table], df.feed_id AS [Feed id], dfl.file_id AS [File id], "
            "qcr.record_id AS [Record id] "
            "FROM hub_md.hub_data_file_log dfl WITH (NOLOCK) "
            "INNER JOIN hub_md.hub_data_feed df WITH (NOLOCK) ON dfl.feed_id = df.feed_id "
            "JOIN ("
            "  SELECT file_id, feed_id, NULL AS record_id, qc_message "
            "  FROM hub_md.hub_qc_sql_result WITH (NOLOCK) "
            "  WHERE record_cnt > 0 AND cre_dt >= CAST(DATEADD(DAY, -?, GETDATE()) AS DATE) "
            "  AND cre_dt <= GETDATE() "
            "  UNION "
            "  SELECT DISTINCT file_id, feed_id, NULL AS record_id, qc_message "
            "  FROM hub_md.hub_feed_qc_results WITH (NOLOCK) "
            "  WHERE cre_dt >= CAST(DATEADD(DAY, -?, GETDATE()) AS DATE) AND cre_dt <= GETDATE()"
            ") qcr ON dfl.file_id = qcr.file_id AND dfl.feed_id = qcr.feed_id "
            "WHERE processed_date >= CAST(DATEADD(DAY, -?, GETDATE()) AS DATE) "
            "AND processed_date <= GETDATE() "
            "ORDER BY dfl.file_id DESC"
        ),
        "bind_template": ["{days}", "{days}", "{days}"],
        "chart_hint": None,
    },
    {
        "id": "qc_failed_recent",
        "intent": "qc.failed.recent",
        "category": "QC / Validation Monitoring",
        "description": "Tables that failed QC in the most recent run",
        "patterns": [
            r"\b(tables?|feeds?)\b.*\bfail(ed)?\s*qc\b.*\b(recent|latest)\b",
            r"\bfail(ed)?\s*qc\b.*\bmost\s*recent\b",
        ],
        "param_names": [],
        "sql": (
            "SELECT qc.feed_id, qc.File_id, hdf.short_name, qc.qc_message, qc.cre_dt "
            "FROM hub_md.hub_qc_sql_result qc WITH (NOLOCK) "
            "INNER JOIN hub_md.hub_data_feed hdf WITH (NOLOCK) ON qc.feed_id = hdf.feed_id "
            "WHERE qc.cre_dt = (SELECT MAX(cre_dt) FROM hub_md.hub_qc_sql_result WITH (NOLOCK)) "
            "ORDER BY hdf.short_name"
        ),
        "bind_template": [],
        "chart_hint": None,
    },

    # ── Feed search ──────────────────────────────────────────────────────────
    {
        "id": "feed_search_named",
        "intent": "feed.search",
        "category": "Feed Search",
        "description": "Feeds related to '{name}'",
        "patterns": [
            r"\b(search|find)\b.*\bfeeds?\b.*\b(?:related to|for|about)\s+(?P<name>[\w\-]+)",
            r"\bshow\s+details?\s+(?:for|of)\s+(?P<name>[\w\-]+)\s+feed",
            r"\bfeeds?\s+related\s+to\s+(?P<name>[\w\-]+)",
            r"\bsearch\s+feeds?.*\b(?P<name>[\w\-]+)",
            r"\bshow.*\b(?P<name>[\w\-]+)\s+feed\b",
        ],
        "param_names": ["name"],
        "sql": (
            "SELECT * FROM hub_md.hub_data_feed WITH (NOLOCK) "
            "WHERE subject_area LIKE ? OR src_name LIKE ? OR file_body LIKE ?"
        ),
        "bind_template": ["%{name}%", "%{name}%", "%{name}%"],
        "chart_hint": None,
    },
    {
        "id": "table_for_named",
        "intent": "feed.table_lookup",
        "category": "Feed Search",
        "description": "Tables that load '{name}' data",
        "patterns": [
            # Anchor immediately after "loads" so we grab the feed name, not "data"
            r"\bwhich\s+tables?\s+loads?\s+(?P<name>[\w\-]+)",
            r"\btables?\s+(?:that\s+)?loads?\s+(?P<name>[\w\-]+)",
            r"\b(?P<name>[\w\-]+)\s+(?:data|file)?\s*load(?:ed|s)?\s+into\s+which\s+tables?\b",
        ],
        "param_names": ["name"],
        "sql": (
            "SELECT DISTINCT hdfl.dds_table, hdf.short_name, hdf.subject_area "
            "FROM hub_md.hub_data_file_log hdfl WITH (NOLOCK) "
            "INNER JOIN hub_md.hub_data_feed hdf WITH (NOLOCK) ON hdfl.feed_id = hdf.feed_id "
            "WHERE hdf.subject_area LIKE ? OR hdf.src_name LIKE ? OR hdf.file_body LIKE ?"
        ),
        "bind_template": ["%{name}%", "%{name}%", "%{name}%"],
        "chart_hint": None,
    },

    # ── Trend analysis (chart-worthy) ────────────────────────────────────────
    {
        "id": "history_last_n_named",
        "intent": "trend.history",
        "category": "Trend Analysis",
        "description": "Last {days} days load history for '{name}'",
        "patterns": [
            # Anchor on "for <name>" so we grab the feed name, not the word "for"
            r"\blast\s+(?P<days>\d+)\s+days?\s+load\s+history\s+for\s+(?P<name>[\w\-]+)",
            r"\b(?P<days>\d+)\s+days?\s+(?:load\s+)?history\s+for\s+(?P<name>[\w\-]+)",
            r"\bload\s+history\s+for\s+(?P<name>[\w\-]+)\s+(?:last|past)\s+(?P<days>\d+)\s+days?",
            r"\btrend\s+for\s+(?P<name>[\w\-]+)\s+last\s+(?P<days>\d+)\s+days?",
        ],
        "param_names": ["days", "name"],
        "sql": (
            "SELECT CAST(hdfl.processed_date AS DATE) AS processed_day, hdf.short_name, "
            "hdfl.status, hdfl.dds_record_count "
            "FROM hub_md.hub_data_file_log hdfl WITH (NOLOCK) "
            "INNER JOIN hub_md.hub_data_feed hdf WITH (NOLOCK) ON hdfl.feed_id = hdf.feed_id "
            "WHERE (hdf.subject_area LIKE ? OR hdf.src_name LIKE ? OR hdf.file_body LIKE ?) "
            "AND hdfl.processed_date >= DATEADD(DAY, -?, GETDATE()) "
            "ORDER BY hdfl.processed_date DESC"
        ),
        "bind_template": ["%{name}%", "%{name}%", "%{name}%", "{days}"],
        "chart_hint": {"type": "line", "x": "processed_day", "y": "dds_record_count"},
    },

    # ── Active feeds ─────────────────────────────────────────────────────────
    # NOTE: the named-subject variant MUST be listed before the generic
    # subject-areas template — otherwise "for subject area accredo … active"
    # would match the generic template first and the name is lost.
    {
        "id": "active_feeds_for_subject",
        "intent": "feeds.active.for_subject",
        "category": "Active Feeds",
        "description": "Active feeds for subject area '{name}'",
        "patterns": [
            r"\bsubject[\s_]area\s+(?P<name>[\w\-]+)\b.*\bactive\b",
            r"\bfor\s+subject[\s_]area\s+(?P<name>[\w\-]+)\b",
            r"\bactive\s+feeds?\b.*\bfor\s+(?P<name>[\w\-]+)\b",
        ],
        "param_names": ["name"],
        "sql": (
            "SELECT hdf.subject_area, hdf.short_name, hdf.file_body, "
            "hdfv.stg_table_name, hdfv.dds_table_name, hdf.entity_master_order "
            "FROM hub_md.hub_data_feed hdf WITH (NOLOCK) "
            "INNER JOIN hub_md.hub_data_feed_version hdfv WITH (NOLOCK) ON hdf.feed_id = hdfv.feed_id "
            "WHERE hdf.subject_area = ? AND hdf.actv_ind = 1 "
            "ORDER BY hdf.entity_master_order"
        ),
        "bind_template": ["{name}"],
        "chart_hint": None,
    },
    {
        "id": "active_subject_areas",
        "intent": "feeds.active.subject_areas",
        "category": "Active Feeds",
        "description": "Subject areas with active feeds",
        "patterns": [
            r"\bwhich\s+subject\s+areas?\b.*\bactive\b",
            r"\bwhat\s+subject\s+areas?\b.*\bactive\b",
            r"\bsubject\s+areas?\b.*\bactive\s+feeds?\b",
            r"\bactive\b.*\bsubject\s+areas?\b",
        ],
        "param_names": [],
        "sql": (
            "SELECT DISTINCT subject_area, short_name, actv_ind "
            "FROM hub_md.hub_data_feed WITH (NOLOCK) "
            "WHERE actv_ind = 1 "
            "ORDER BY subject_area, short_name"
        ),
        "bind_template": [],
        "chart_hint": {"type": "count_bar", "x": "subject_area", "y": None},
    },

    # ── Latest successful load (subject) ─────────────────────────────────────
    {
        "id": "latest_success_for_subject",
        "intent": "load.latest_success",
        "category": "Load Monitoring",
        "description": "Latest successful load for each feed in subject area '{name}'",
        "patterns": [
            # Canonical: "...subject_area 'accredo'..." (single/double quotes optional, "_" or space)
            r"\blatest\s+(?:successful\s+)?load\b.*?\bsubject[\s_]area[\s'\"]+(?P<name>[\w\-]+)",
            # "latest successful load for accredo" (no subject_area keyword)
            r"\blatest\s+(?:successful\s+)?load\s+for\s+(?P<name>[\w\-]+)\b",
            # "latest load in subject area accredo"
            r"\blatest\s+load\b.*?\bin\s+subject[\s_]area\s+(?P<name>[\w\-]+)\b",
        ],
        "param_names": ["name"],
        "sql": (
            "SELECT hdf.subject_area, hdf.short_name, hdfl.file_id, hdfl.processed_date, "
            "hdfl.stg_record_count, hdfl.archive_loc "
            "FROM hub_md.hub_data_file_log hdfl WITH (NOLOCK) "
            "INNER JOIN hub_md.hub_data_feed hdf WITH (NOLOCK) ON hdfl.feed_id = hdf.feed_id "
            "WHERE hdf.subject_area = ? AND hdfl.status = 5 "
            "AND hdfl.processed_date = ("
            "  SELECT MAX(processed_date) FROM hub_md.hub_data_file_log hdfl2 WITH (NOLOCK) "
            "  WHERE hdfl2.feed_id = hdfl.feed_id AND hdfl2.status = 5"
            ") ORDER BY hdfl.processed_date DESC"
        ),
        "bind_template": ["{name}"],
        "chart_hint": None,
    },
]
 