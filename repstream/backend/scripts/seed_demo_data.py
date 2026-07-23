"""
Seed a local PostgreSQL database with demo data for all 3 RepStream modules.

Creates the required tables (as regular tables, not views) under the hub_insight360
schema so the ORM models resolve correctly.

Usage:
    python scripts/seed_demo_data.py

Requires DATABASE_URL to be set in .env or as an env var.
"""
import os
import sys
from datetime import date, timedelta

# Make sure app/ is on the path when run from backend/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import text
from app.database import engine
from app.config import settings

SCHEMA = settings.HUB_SCHEMA


# ─── DDL ──────────────────────────────────────────────────────────────────────

DDL = f"""
CREATE SCHEMA IF NOT EXISTS {SCHEMA};

-- HCP Dimension
CREATE TABLE IF NOT EXISTS {SCHEMA}.vw_tdim_healthcarepractitioner_zenpep_reporting_dul (
    hcp_id              VARCHAR(50) PRIMARY KEY,
    npi_number          VARCHAR(20),
    hcp_first_name      VARCHAR(100),
    hcp_last_name       VARCHAR(100),
    hcp_full_name       VARCHAR(200),
    specialty           VARCHAR(100),
    sub_specialty       VARCHAR(100),
    address_line1       VARCHAR(200),
    address_line2       VARCHAR(200),
    city                VARCHAR(100),
    state               VARCHAR(50),
    zip_code            VARCHAR(20),
    territory_id        VARCHAR(50),
    hcp_segment         VARCHAR(50),
    decile_rank         INTEGER,
    icd10_codes         VARCHAR(500),
    is_active           BOOLEAN DEFAULT TRUE,
    affiliated_hospital VARCHAR(200),
    affiliated_group    VARCHAR(200)
);

-- Prescriber Sales Fact
CREATE TABLE IF NOT EXISTS {SCHEMA}.vw_tfact_prescribersales_zenpep_reporting_dul (
    record_id        VARCHAR(80) PRIMARY KEY,
    hcp_id           VARCHAR(50),
    territory_id     VARCHAR(50),
    product_name     VARCHAR(100),
    brand_name       VARCHAR(100),
    market_name      VARCHAR(100),
    year             INTEGER,
    quarter          INTEGER,
    month            INTEGER,
    period_date      DATE,
    total_rx         FLOAT,
    new_rx           FLOAT,
    refill_rx        FLOAT,
    market_total_rx  FLOAT,
    competitor_rx    FLOAT,
    market_share     FLOAT,
    competitor_brand VARCHAR(100),
    is_brand         INTEGER DEFAULT 0
);

-- Call Activity Fact
CREATE TABLE IF NOT EXISTS {SCHEMA}.vw_tfact_callactivitydetails_zenpep_reporting_dul (
    call_id                VARCHAR(80) PRIMARY KEY,
    hcp_id                 VARCHAR(50),
    rep_id                 VARCHAR(50),
    territory_id           VARCHAR(50),
    call_date              DATE,
    call_type              VARCHAR(50),
    call_outcome           VARCHAR(50),
    products_discussed     TEXT,
    call_notes             TEXT,
    is_reached             BOOLEAN DEFAULT TRUE,
    call_duration_minutes  INTEGER,
    rx_written_at_call     BOOLEAN DEFAULT FALSE,
    next_call_planned      DATE
);

-- Territory Hierarchy
CREATE TABLE IF NOT EXISTS {SCHEMA}.vw_tdim_terr_hierarchy_zenpep_reporting_dul (
    territory_id   VARCHAR(50) PRIMARY KEY,
    territory_name VARCHAR(100),
    territory_code VARCHAR(50),
    district_id    VARCHAR(50),
    district_name  VARCHAR(100),
    region_id      VARCHAR(50),
    region_name    VARCHAR(100),
    area_id        VARCHAR(50),
    area_name      VARCHAR(100),
    zone_id        VARCHAR(50),
    zone_name      VARCHAR(100),
    is_active      BOOLEAN DEFAULT TRUE
);

-- Peer Match (enriched)
CREATE TABLE IF NOT EXISTS {SCHEMA}.insight360_peer_match_dul (
    match_id           VARCHAR(80) PRIMARY KEY,
    hcp_id             VARCHAR(50),
    peer_hcp_id        VARCHAR(50),
    peer_hcp_name      VARCHAR(200),
    match_score        FLOAT,
    match_rationale    TEXT,
    shared_specialty   VARCHAR(100),
    shared_institution VARCHAR(200),
    peer_brand_rx_q1   FLOAT DEFAULT 0,
    territory_id       VARCHAR(50),
    created_at         TIMESTAMP DEFAULT NOW(),
    updated_at         TIMESTAMP DEFAULT NOW()
);

-- New Writer ID (enriched card — 11 keys rendered on the module UI)
CREATE TABLE IF NOT EXISTS {SCHEMA}.insight360_new_writer_id (
    hcp_id                 VARCHAR(50) PRIMARY KEY,
    name                   VARCHAR(200),
    specialty              VARCHAR(100),
    affiliated_hospital    VARCHAR(200),
    last_nrx_date          VARCHAR(50),
    ai_warm_approach_text  TEXT,
    ai_icd10_matched_codes VARCHAR(500),
    top_5_in_class_rx      TEXT,
    total_in_class_rx      FLOAT DEFAULT 0,
    ai_peer_match_score    FLOAT DEFAULT 0,
    analysis_badges        VARCHAR(200)
);

-- Objection Handler (enriched)
CREATE TABLE IF NOT EXISTS {SCHEMA}.insight360_objection_handler_dul (
    objection_id         VARCHAR(80) PRIMARY KEY,
    objection_type       VARCHAR(100),
    objection_text       TEXT,
    hcp_segment          VARCHAR(50),
    recommended_response TEXT,
    response_source      VARCHAR(100),
    sku                  VARCHAR(100),
    success_rate         FLOAT,
    call_count           INTEGER,
    territory_id         VARCHAR(50),
    period               VARCHAR(20),
    created_at           TIMESTAMP DEFAULT NOW(),
    updated_at           TIMESTAMP DEFAULT NOW()
);

-- Call Transcripts (enriched)
CREATE TABLE IF NOT EXISTS {SCHEMA}.insight360_call_transcripts_dul (
    transcript_id      VARCHAR(80) PRIMARY KEY,
    call_id            VARCHAR(80),
    hcp_id             VARCHAR(50),
    rep_id             VARCHAR(50),
    territory_id       VARCHAR(50),
    call_date          DATE,
    transcript_text    TEXT,
    has_objection      BOOLEAN DEFAULT FALSE,
    objection_types    TEXT,
    objection_resolved BOOLEAN DEFAULT FALSE,
    rx_within_30_days  BOOLEAN DEFAULT FALSE,
    sentiment_score    FLOAT,
    created_at         TIMESTAMP DEFAULT NOW()
);

-- Action Center: Active Alerts
CREATE TABLE IF NOT EXISTS {SCHEMA}.insight360_active_alerts_dul (
    alert_id                  VARCHAR(80) PRIMARY KEY,
    alert_type                VARCHAR(50),
    severity                  VARCHAR(20),
    detection_method          VARCHAR(50),
    title                     VARCHAR(200),
    description               TEXT,
    detected_at               TIMESTAMP,
    territory_id              VARCHAR(50),
    period                    VARCHAR(20),
    ai_affected_hcp_count     INTEGER DEFAULT 0,
    ai_territory_reach        VARCHAR(20),
    ai_rx_risk                VARCHAR(20),
    ai_icd10_codes_affected   TEXT,
    ai_prescribing_drift_note TEXT,
    ai_detection_lead_weeks   FLOAT,
    ai_counter_script         TEXT,
    ai_supporting_materials   TEXT,
    is_acknowledged           BOOLEAN DEFAULT FALSE,
    is_dismissed              BOOLEAN DEFAULT FALSE,
    is_deployed               BOOLEAN DEFAULT FALSE,
    created_at                TIMESTAMP DEFAULT NOW(),
    updated_at                TIMESTAMP DEFAULT NOW()
);

-- Action Center: HCP Awareness
CREATE TABLE IF NOT EXISTS {SCHEMA}.insight360_hcp_awareness_dul (
    awareness_id                VARCHAR(80) PRIMARY KEY,
    hcp_id                      VARCHAR(50),
    hcp_full_name               VARCHAR(200),
    specialty                   VARCHAR(100),
    territory_id                VARCHAR(50),
    period                      VARCHAR(20),
    product_awareness_score     FLOAT DEFAULT 0,
    competitor_awareness_score  FLOAT DEFAULT 0,
    clinical_evidence_score     FLOAT DEFAULT 0,
    total_interactions          INTEGER DEFAULT 0,
    last_interaction_date       DATE,
    ai_awareness_score          FLOAT DEFAULT 0,
    ai_awareness_level          VARCHAR(20),
    ai_key_messages_delivered   TEXT,
    ai_knowledge_gaps           TEXT,
    ai_recommended_action       TEXT,
    created_at                  TIMESTAMP DEFAULT NOW()
);

-- Action Center: Competitive Intel
CREATE TABLE IF NOT EXISTS {SCHEMA}.insight360_competitive_intel_dul (
    intel_id                VARCHAR(80) PRIMARY KEY,
    competitor_name         VARCHAR(100),
    territory_id            VARCHAR(50),
    period                  VARCHAR(20),
    message_theme           VARCHAR(200),
    detection_date          DATE,
    affected_hcp_count      INTEGER DEFAULT 0,
    market_share_change_pct FLOAT DEFAULT 0,
    icd10_focus             TEXT,
    source_channel          VARCHAR(100),
    ai_threat_score         FLOAT DEFAULT 0,
    ai_threat_level         VARCHAR(20),
    ai_counter_strategy     TEXT,
    ai_supporting_evidence  TEXT,
    ai_detection_method     VARCHAR(50),
    created_at              TIMESTAMP DEFAULT NOW()
);

-- Action Center: Payer Access
CREATE TABLE IF NOT EXISTS {SCHEMA}.insight360_payer_access_dul (
    access_id                    VARCHAR(80) PRIMARY KEY,
    payer_name                   VARCHAR(200),
    territory_id                 VARCHAR(50),
    period                       VARCHAR(20),
    product_tier_current         INTEGER,
    product_tier_previous        INTEGER,
    tier_change_date             DATE,
    formulary_status             VARCHAR(50),
    covered_lives                INTEGER DEFAULT 0,
    affected_hcp_count           INTEGER DEFAULT 0,
    patient_assistance_available BOOLEAN DEFAULT FALSE,
    ai_impact_score              FLOAT DEFAULT 0,
    ai_access_impact             VARCHAR(20),
    ai_action_required           TEXT,
    ai_patient_assistance_note   TEXT,
    ai_tier_change_direction     VARCHAR(20),
    created_at                   TIMESTAMP DEFAULT NOW()
);

-- Employee Dimension (needed for Celery batch territory lookup)
CREATE TABLE IF NOT EXISTS {SCHEMA}.vw_tdim_employee_zenpep_reporting_dul (
    rep_id      VARCHAR(50) PRIMARY KEY,
    employee_id VARCHAR(50),
    first_name  VARCHAR(100),
    last_name   VARCHAR(100),
    full_name   VARCHAR(200),
    email       VARCHAR(200),
    title       VARCHAR(100),
    role        VARCHAR(100),
    manager_id  VARCHAR(50),
    is_active   BOOLEAN DEFAULT TRUE,
    hire_date   DATE
);

CREATE TABLE IF NOT EXISTS {SCHEMA}.vw_tdim_employee_territory_zenpep_reporting (
    record_id            VARCHAR(80) PRIMARY KEY,
    rep_id               VARCHAR(50),
    territory_id         VARCHAR(50),
    effective_start_date DATE,
    effective_end_date   DATE,
    is_current           BOOLEAN DEFAULT TRUE
);
"""


# ─── Seed data ─────────────────────────────────────────────────────────────────

def seed_territory():
    return [
        ("TERR-001", "Boston North", "BOS-N", "DIST-01", "New England East",
         "REG-01", "Northeast", "AREA-01", "Northeast Area", "ZONE-01", "Zone North"),
        ("TERR-002", "Boston South", "BOS-S", "DIST-01", "New England East",
         "REG-01", "Northeast", "AREA-01", "Northeast Area", "ZONE-01", "Zone North"),
    ]


def seed_hcps():
    return [
        # Territory TERR-001 — Boston North
        ("HCP001", "1234567890", "Jane", "Smith", "Dr. Jane Smith",
         "Gastroenterology", "Pancreatic Disease",
         "100 Main St", "", "Boston", "MA", "02101",
         "TERR-001", "A", 1, "K86.1,K86.81,K86.89", True,
         "Boston Medical Center", "Boston GI Group"),
        ("HCP002", "2345678901", "Robert", "Chen", "Dr. Robert Chen",
         "Internal Medicine", "General IM",
         "200 Park Ave", "", "Cambridge", "MA", "02139",
         "TERR-001", "B", 4, "K86.0,K86.1,E84.19", True,
         "Cambridge Health Alliance", ""),
        ("HCP003", "3456789012", "Alice", "Patel", "Dr. Alice Patel",
         "Gastroenterology", "IBD & Malabsorption",
         "300 Beacon St", "", "Brookline", "MA", "02445",
         "TERR-001", "A", 2, "K86.81,K90.3,C25.0", True,
         "Brigham and Women's", "BWH GI Associates"),
        ("HCP004", "4567890123", "Michael", "Torres", "Dr. Michael Torres",
         "Oncology", "Pancreatic Oncology",
         "400 Commonwealth Ave", "", "Boston", "MA", "02115",
         "TERR-001", "B", 5, "C25.0,C25.9,K86.89", True,
         "Dana-Farber Cancer Institute", ""),
        ("HCP005", "5678901234", "Sarah", "Kim", "Dr. Sarah Kim",
         "Gastroenterology", None,
         "500 Huntington Ave", "", "Jamaica Plain", "MA", "02130",
         "TERR-001", "C", 8, "K31.1,K86.0", True, "", ""),
        ("HCP006", "6789012345", "David", "Nguyen", "Dr. David Nguyen",
         "Internal Medicine", "Hospitalist",
         "600 Washington St", "", "Somerville", "MA", "02143",
         "TERR-001", "C", 9, "E84.19", True, "Somerville Hospital", ""),
        ("HCP007", "7890123456", "Emily", "Walsh", "Dr. Emily Walsh",
         "Gastroenterology", "Motility",
         "700 Mass Ave", "", "Arlington", "MA", "02474",
         "TERR-001", "A", 3, "K86.81,K86.89,K90.3", True,
         "Mass General Hospital", "MGH GI Group"),
        ("HCP008", "8901234567", "James", "Brown", "Dr. James Brown",
         "Pediatric GI", None,
         "800 Harvard St", "", "Medford", "MA", "02155",
         "TERR-001", "B", 6, "K86.1,E84.19", True,
         "Boston Children's Hospital", ""),
    ]


def seed_prescriber_sales():
    """Rx data for Q4 2024 and Q1 2025."""
    today = date.today()
    q1_date = date(today.year, 1, 15)
    q4_date = date(today.year - 1, 10, 15)

    rows = []
    # HCP001 — High: big Q1 jump
    rows += [
        ("RX-HCP001-Q4-B", "HCP001", "TERR-001", "ZENPEP", "ZENPEP", "PERT Market",
         today.year - 1, 4, 10, q4_date, 28.0, 10.0, 18.0, 60.0, 20.0, 0.47,
         "Creon", 1),
        ("RX-HCP001-Q1-B", "HCP001", "TERR-001", "ZENPEP", "ZENPEP", "PERT Market",
         today.year, 1, 1, q1_date, 45.0, 18.0, 27.0, 75.0, 18.0, 0.60,
         "Creon", 1),
    ]
    # HCP002 — Non-writer: in-class only (competitor), no brand
    rows += [
        ("RX-HCP002-Q4-IC", "HCP002", "TERR-001", "CREON", "Creon", "PERT Market",
         today.year - 1, 4, 10, q4_date, 14.0, 5.0, 9.0, 14.0, 0.0, 0.0,
         "Creon", 0),
        ("RX-HCP002-Q1-IC", "HCP002", "TERR-001", "CREON", "Creon", "PERT Market",
         today.year, 1, 1, q1_date, 12.0, 4.0, 8.0, 12.0, 0.0, 0.0,
         "Creon", 0),
    ]
    # HCP003 — High: above 75th percentile
    rows += [
        ("RX-HCP003-Q4-B", "HCP003", "TERR-001", "ZENPEP", "ZENPEP", "PERT Market",
         today.year - 1, 4, 10, q4_date, 38.0, 12.0, 26.0, 70.0, 22.0, 0.54,
         "Pancreaze", 1),
        ("RX-HCP003-Q1-B", "HCP003", "TERR-001", "ZENPEP", "ZENPEP", "PERT Market",
         today.year, 1, 1, q1_date, 42.0, 14.0, 28.0, 78.0, 25.0, 0.54,
         "Pancreaze", 1),
    ]
    # HCP004 — Medium: modest trend
    rows += [
        ("RX-HCP004-Q4-B", "HCP004", "TERR-001", "ZENPEP", "ZENPEP", "PERT Market",
         today.year - 1, 4, 10, q4_date, 15.0, 5.0, 10.0, 35.0, 12.0, 0.43,
         "Creon", 1),
        ("RX-HCP004-Q1-B", "HCP004", "TERR-001", "ZENPEP", "ZENPEP", "PERT Market",
         today.year, 1, 1, q1_date, 17.0, 6.0, 11.0, 38.0, 13.0, 0.45,
         "Creon", 1),
    ]
    # HCP005 — Non-writer: in-class competitor only
    rows += [
        ("RX-HCP005-Q4-IC", "HCP005", "TERR-001", "PANCREAZE", "Pancreaze", "PERT Market",
         today.year - 1, 4, 10, q4_date, 8.0, 3.0, 5.0, 8.0, 0.0, 0.0,
         "Pancreaze", 0),
        ("RX-HCP005-Q1-IC", "HCP005", "TERR-001", "PANCREAZE", "Pancreaze", "PERT Market",
         today.year, 1, 1, q1_date, 9.0, 3.0, 6.0, 9.0, 0.0, 0.0,
         "Pancreaze", 0),
    ]
    # HCP006 — Low: declining brand Rx
    rows += [
        ("RX-HCP006-Q4-B", "HCP006", "TERR-001", "ZENPEP", "ZENPEP", "PERT Market",
         today.year - 1, 4, 10, q4_date, 22.0, 8.0, 14.0, 45.0, 15.0, 0.49,
         "Creon", 1),
        ("RX-HCP006-Q1-B", "HCP006", "TERR-001", "ZENPEP", "ZENPEP", "PERT Market",
         today.year, 1, 1, q1_date, 14.0, 4.0, 10.0, 40.0, 18.0, 0.35,
         "Creon", 1),
    ]
    # HCP007 — High: strong trend
    rows += [
        ("RX-HCP007-Q4-B", "HCP007", "TERR-001", "ZENPEP", "ZENPEP", "PERT Market",
         today.year - 1, 4, 10, q4_date, 20.0, 7.0, 13.0, 50.0, 20.0, 0.40,
         "Creon", 1),
        ("RX-HCP007-Q1-B", "HCP007", "TERR-001", "ZENPEP", "ZENPEP", "PERT Market",
         today.year, 1, 1, q1_date, 26.0, 9.0, 17.0, 55.0, 19.0, 0.47,
         "Creon", 1),
    ]
    # HCP008 — Non-writer: pediatric in-class only
    rows += [
        ("RX-HCP008-Q1-IC", "HCP008", "TERR-001", "CREON", "Creon", "PERT Market",
         today.year, 1, 1, q1_date, 6.0, 2.0, 4.0, 6.0, 0.0, 0.0,
         "Creon", 0),
    ]
    return rows


def seed_call_activity():
    today = date.today()
    return [
        ("CALL-001", "HCP001", "REP001", "TERR-001", today - timedelta(days=15),
         "Detail", "Positive", "ZENPEP 40MG", "Discussed EPI starter pack", True, 20, False, None),
        ("CALL-002", "HCP002", "REP001", "TERR-001", today - timedelta(days=30),
         "Detail", "Neutral", "ZENPEP", "First contact — in-class prescriber", True, 15, False, None),
        ("CALL-003", "HCP003", "REP001", "TERR-001", today - timedelta(days=8),
         "Sample", "Positive", "ZENPEP 40MG,ZENPEP 20MG", "Sample drop only", True, 10, True, None),
        ("CALL-004", "HCP004", "REP001", "TERR-001", today - timedelta(days=45),
         "Detail", "Neutral", "ZENPEP", "Patient population discussion", True, 25, False, None),
        ("CALL-005", "HCP007", "REP001", "TERR-001", today - timedelta(days=5),
         "Detail", "Very Positive", "ZENPEP 40MG", "Committed to try in next EPI patient", True, 30, True, None),
        ("CALL-006", "HCP006", "REP001", "TERR-001", today - timedelta(days=90),
         "Detail", "Negative", "ZENPEP", "Coverage objection raised", True, 15, False, None),
    ]


def seed_peer_matches():
    return [
        # HCP002 (non-writer) matched with HCP001 (brand writer) — high affinity
        ("PM-001", "HCP002", "HCP001", "Dr. Jane Smith", 82.5,
         "Same specialty, shared institution, similar patient mix",
         "Gastroenterology", "Boston Medical Center", 45.0, "TERR-001"),
        # HCP005 (non-writer) matched with HCP003
        ("PM-002", "HCP005", "HCP003", "Dr. Alice Patel", 67.0,
         "Same specialty, overlapping ICD-10 profile",
         "Gastroenterology", "Brigham and Women's", 42.0, "TERR-001"),
        # HCP008 (non-writer pediatric) — moderate match
        ("PM-003", "HCP008", "HCP001", "Dr. Jane Smith", 45.0,
         "EPI patient population overlap despite different specialty",
         "Gastroenterology", "", 45.0, "TERR-001"),
    ]


def seed_new_writer_cards():
    """New Writer ID card data — matches the UI screenshot exactly (11 keys only)."""
    import json
    return [
        (
            "NW001", "Dr. Jennifer Lee", "Endocrinology", "Summit Medical", "Feb 12, 2026",
            "Connected to Dr. Davidson. Prescribing competitor in same class at 8-12% conversion rate.",
            "E11.9|E78.5",
            json.dumps([
                {"brand": "Competitor Brand A", "rx": 14},
                {"brand": "Competitor Brand B", "rx": 9},
                {"brand": "Generic Option C", "rx": 6},
                {"brand": "Competitor Brand D", "rx": 4},
                {"brand": "Competitor Brand E", "rx": 2},
            ]),
            35.0, 87.0, "ML_PATTERN_MATCHING|AI_MATCHED|AI_GENERATED",
        ),
        (
            "NW002", "Dr. Robert Kim", "Cardiology", "Riverside Heart", "Mar 8, 2026",
            "Peer network indicates 25-35% conversion opportunity. Recently joined practice on Feb 15, 2026.",
            "I50.9|I25.10",
            json.dumps([
                {"brand": "Competitor Brand B", "rx": 11},
                {"brand": "Generic Option C", "rx": 8},
                {"brand": "Competitor Brand A", "rx": 5},
                {"brand": "Competitor Brand F", "rx": 3},
                {"brand": "Competitor Brand D", "rx": 1},
            ]),
            28.0, 72.0, "ML_PATTERN_MATCHING|AI_MATCHED|AI_GENERATED",
        ),
    ]


def seed_objections():
    today = date.today()
    q = (today.month - 1) // 3 + 1
    period = f"Q{q} {today.year}"
    return [
        ("OBJ-001", "COVERAGE", "Patient's insurance doesn't cover Zenpep — prior auth required",
         "B",
         "Share our Patient Access Card: most commercial plans cover Zenpep at Tier 2 after prior auth. "
         "Our reimbursement support line (1-800-XXX-XXXX) handles PA in under 48 hours.",
         "MLR-approved v3.1", "ZPP-40MG-40CAP", 0.58, 12, "TERR-001", period),
        ("OBJ-002", "COST", "Zenpep is too expensive — my patients can't afford the copay",
         "B",
         "The Zenpep Savings Card reduces eligible patient out-of-pocket to $0/month for most commercial patients. "
         "Present the card at the counter. No income limit.",
         "MLR-approved v2.4", "ZPP-SAVINGS-CARD", 0.72, 9, "TERR-001", period),
        ("OBJ-003", "COMPETITOR", "I'm comfortable with Creon — my patients are stable on it",
         "A",
         "I completely understand — patient stability is the priority. "
         "When you do see a new EPI patient or a patient still symptomatic on their current therapy, "
         "Zenpep's non-enteric-coated microspheres may provide faster enzyme release. "
         "Would you be open to trying it in your next new-start?",
         "MLR-approved v2.1", "ZPP-40MG-40CAP", 0.41, 7, "TERR-001", period),
        ("OBJ-004", "EFFICACY", "I haven't seen evidence that it works better than existing options",
         "A",
         "Here's the ADVENT trial summary (MLR-approved reprint) showing non-inferiority in CFA "
         "and statistically significant improvement in stool frequency at week 4. "
         "I'd love to leave a copy for your review.",
         "MLR-approved v1.8", "ZPP-40MG-40CAP", 0.49, 4, "TERR-001", period),
        ("OBJ-005", "AWARENESS", "I've never tried Zenpep — tell me more about the dosing",
         "C",
         "Zenpep is dosed based on fat intake: start at 500 lipase units/kg/meal for adults, "
         "max 2500 units/kg/meal. Available in 5 strengths (3K–40K units) for flexible titration. "
         "I can walk through the dosing guide with you — it takes about 5 minutes.",
         "MLR-approved v3.0", "ZPP-DOSING-GUIDE", 0.65, 3, "TERR-001", period),
    ]


def seed_call_transcripts():
    today = date.today()
    return [
        ("TR-001", "CALL-006", "HCP006", "REP001", "TERR-001",
         today - timedelta(days=90),
         "Rep: Good morning Dr. Nguyen. HCP: Good morning. "
         "HCP: Actually I wanted to bring up — my patient's insurance doesn't cover Zenpep, prior auth required. "
         "It's been holding up the prescription. Rep: I understand, our reimbursement team can help. "
         "HCP: Also the copay is too high for my patient population.",
         True, '["COVERAGE", "COST"]', False, False, -0.2),
        ("TR-002", "CALL-001", "HCP001", "REP001", "TERR-001",
         today - timedelta(days=15),
         "Rep: Dr. Smith, wanted to check in on the last few EPI patients. "
         "HCP: Yes, the 40MG caps have been working really well — patients appreciate the flexibility. "
         "Rep: Glad to hear it. Are there patients still on competitors you might convert? "
         "HCP: A few, but some have coverage issues. Rep: We have patient assistance. HCP: Send me the details.",
         True, '["COVERAGE"]', True, True, 0.6),
        ("TR-003", "CALL-004", "HCP004", "REP001", "TERR-001",
         today - timedelta(days=45),
         "HCP: I've been using Creon for years. I'm comfortable with it and my patients are stable. "
         "Rep: Absolutely — for new-start pancreatic cancer patients post-surgery, "
         "Zenpep's microsphere technology may be worth considering. "
         "HCP: Maybe, but I haven't seen data comparing them directly. "
         "Rep: I have the ADVENT trial reprint — can I leave it? HCP: Sure.",
         True, '["COMPETITOR", "EFFICACY"]', False, False, 0.1),
        ("TR-004", "CALL-005", "HCP007", "REP001", "TERR-001",
         today - timedelta(days=5),
         "Rep: Great to see you Dr. Walsh. HCP: Likewise — the samples you left were perfect. "
         "Next new EPI patient I see I'm going to start on Zenpep. "
         "The dosing chart you left made it very clear. "
         "Rep: Wonderful. Let me know how the first patient goes.",
         False, '[]', False, True, 0.85),
    ]


def seed_active_alerts():
    """Real alert data from user-provided KPI spec for TERR-001."""
    import json
    rows = [
        (
            "AL-001", "COMPETITIVE", "CRITICAL", "ANOMALY_DETECTION",
            "Competitive script shift in cardiology segment",
            "Competitor Creon launched new messaging around faster onset claims. "
            "Detected in 8 HCP interactions across 3 territories between Apr 26-28, 2026. "
            "Territory: JOLIET, IL.",
            "2026-04-28 08:15:00", "TERR-001", "Q1 2026",
            8, "3/12", "High",
            json.dumps([
                {"code": "I50.9", "label": "Heart Failure", "hcp_count": 12},
                {"code": "I25.10", "label": "CAD", "hcp_count": 8},
                {"code": "I11.0", "label": "Hypertensive HD", "hcp_count": 13},
            ]),
            "4 HCPs showing 15-20% reduction in Rx volume Apr 14-28, 2026.",
            2.8,
            "Deploy targeted Zenpep efficacy messaging to cardiologists with EPI comorbidity. "
            "Focus on flexible dosing and ZenConnect patient support to address access barriers driving the shift.",
            json.dumps([
                {"title": "APEX Trial Summary", "sku": "APEX-2024-01"},
                {"title": "Competitive Positioning Guide", "sku": None},
            ]),
            False, False, False,
        ),
        (
            "AL-005", "COMPETITIVE", "HIGH", "ANOMALY_DETECTION",
            "New HCP entrants prescribing generic PERT at high volume",
            "New prescribers detected in LOUISVILLE, KY territory writing generic PERT at high volume. "
            "5 HCPs identified across 1 territory. Potential early market share loss.",
            "2026-04-24 16:20:00", "TERR-001", "Q1 2026",
            5, "1/12", "Medium",
            json.dumps([
                {"code": "K86.81", "label": "EPI - Exocrine Pancreatic Insufficiency", "hcp_count": 5},
            ]),
            "New writers not yet detailed — no previous Zenpep interaction recorded.",
            3.1,
            "Identify new prescribers through New Writer Detection module. "
            "Schedule introductory detailing visits. Provide samples and patient education materials.",
            json.dumps([
                {"title": "Zenpep New Writer Kit", "sku": "ZPP-STARTER-KIT"},
                {"title": "EPI Patient Identification Guide", "sku": "ZPP-EPI-GUIDE"},
            ]),
            False, False, False,
        ),
        (
            "AL-003", "HCP_DRIFT", "CRITICAL", "ML_MODEL",
            "HCP detailing frequency decline correlated with Rx drop",
            "ML trend model detected detailing frequency decline correlated with Rx drop in GARDEN GROVE, CA. "
            "6 HCPs showing consistent reduction over 60-day rolling window.",
            "2026-04-26 09:45:00", "TERR-001", "Q1 2026",
            6, "1/12", "High",
            json.dumps([
                {"code": "K86.81", "label": "EPI", "hcp_count": 6},
                {"code": "K86.89", "label": "Other Pancreatic Disease", "hcp_count": 4},
            ]),
            "6 HCPs with 20-35% Rx volume reduction correlated with rep call gap > 45 days.",
            2.8,
            "Increase rep call frequency for High priority HCPs in this territory. "
            "Add Home Office Meal engagement to re-establish relationships. "
            "Target HCPs with decile 8-10.",
            json.dumps([
                {"title": "Rep Call Optimization Playbook", "sku": "REP-CALL-001"},
            ]),
            False, False, False,
        ),
        (
            "AL-007", "HCP_DRIFT", "MEDIUM", "ML_MODEL",
            "Gradual awareness score decline in key HCP segment",
            "ML model detected gradual awareness score decline in key HCP segment in SACRAMENTO, CA. "
            "4 HCPs showing downward trend over 90 days.",
            "2026-04-22 13:45:00", "TERR-001", "Q1 2026",
            4, "1/12", "Low",
            json.dumps([
                {"code": "K86.81", "label": "EPI", "hcp_count": 4},
            ]),
            "4 HCPs showing reduced engagement scores vs. prior quarter average.",
            4.2,
            "Re-engage declining HCPs with updated clinical data. "
            "Schedule speaker program in affected district. "
            "Increase digital engagement through Rep Triggered Emails.",
            json.dumps([
                {"title": "Digital Engagement Guide", "sku": "ZPP-DIGITAL-001"},
            ]),
            False, False, False,
        ),
        (
            "AL-006", "PAYER", "HIGH", "ANOMALY_DETECTION",
            "Post-formulary change Rx erosion — Aetna plans",
            "BlueCross Northeast moved Zenpep from Tier 2 to Tier 3 effective Apr 23, 2026. "
            "Aetna formulary change affecting approximately 340 covered lives in TACOMA, WA territory. "
            "14 HCPs impacted across 4 territories.",
            "2026-04-23 10:10:00", "TERR-001", "Q1 2026",
            14, "4/12", "High",
            json.dumps([
                {"code": "K86.81", "label": "EPI", "hcp_count": 14},
                {"code": "K86.1", "label": "Chronic Pancreatitis", "hcp_count": 9},
            ]),
            "Rx erosion detected in 14 HCPs following tier change — avg 22% volume drop.",
            2.5,
            "Immediate payer access outreach required. "
            "Coordinate with market access team on Aetna tier appeal. "
            "Provide HCPs with PA assistance scripts for affected patients.",
            json.dumps([
                {"title": "Patient Assistance Program Guide", "sku": "ZPP-PA-GUIDE"},
                {"title": "Prior Auth Support Script", "sku": "ZPP-PA-SCRIPT"},
            ]),
            False, False, False,
        ),
        (
            "AL-008", "COMPETITIVE", "MEDIUM", "ANOMALY_DETECTION",
            "Unusual prescription timing pattern — potential competitor promotion",
            "Unusual prescription timing pattern detected in MORGANTOWN, WV. "
            "3 HCPs showing atypical Rx spikes mid-week consistent with competitor lunch promotion activity.",
            "2026-04-21 09:30:00", "TERR-001", "Q1 2026",
            3, "1/12", "Low",
            json.dumps([
                {"code": "K86.81", "label": "EPI", "hcp_count": 3},
            ]),
            "Pattern consistent with competitor promotional event — monitoring required.",
            3.8,
            "Monitor for 2 additional weeks. If pattern persists, escalate to district manager "
            "and deploy competitive counter-messaging.",
            json.dumps([]),
            False, False, False,
        ),
        (
            "AL-004", "COMPETITIVE", "HIGH", "ML_MODEL",
            "Pancreaze rep activity spike detected in Southwest",
            "Pancreaze rep activity spike detected in E. PHILADELPHIA, PA territory. "
            "9 HCPs impacted. ML model detected unusual call frequency increase correlated with Rx share shifts.",
            "2026-04-25 11:00:00", "TERR-001", "Q1 2026",
            9, "2/12", "Medium",
            json.dumps([
                {"code": "K86.81", "label": "EPI", "hcp_count": 9},
                {"code": "K86.89", "label": "Other Pancreatic Disease", "hcp_count": 6},
            ]),
            "9 HCPs showing Pancreaze Rx uptick of 8-15% over prior 30-day baseline.",
            2.8,
            "Counter with Zenpep microsphere differentiation messaging. "
            "Leverage ZenConnect co-pay advantage for newly switching patients. "
            "Alert district manager.",
            json.dumps([
                {"title": "Competitive Differentiation Deck", "sku": "ZPP-COMP-DIFF"},
                {"title": "ZenConnect Enrollment Form", "sku": "ZPP-ZENCONNECT"},
            ]),
            False, False, False,
        ),
        (
            "AL-002", "COMPETITIVE", "CRITICAL", "ANOMALY_DETECTION",
            "Rapid Creon market share gain in Midwest district",
            "Rapid Creon market share gain detected in ROCKFORD, IL. "
            "11 HCPs impacted across 2 territories. "
            "Creon gained 3.2% market share in 14-day window Apr 13-27, 2026.",
            "2026-04-27 14:30:00", "TERR-001", "Q1 2026",
            11, "2/12", "High",
            json.dumps([
                {"code": "K86.81", "label": "EPI", "hcp_count": 11},
                {"code": "K86.1", "label": "Chronic Pancreatitis", "hcp_count": 7},
                {"code": "C25.0", "label": "Pancreatic Cancer", "hcp_count": 3},
            ]),
            "11 HCPs showing Creon uptake +3.2% in 14-day window. Zenpep share down 2.1%.",
            2.8,
            "Schedule emergency MSL visits with top 5 HCPs in affected territory. "
            "Provide updated head-to-head tolerability data. "
            "Accelerate ZenConnect enrollment for at-risk patients.",
            json.dumps([
                {"title": "Head-to-Head Tolerability Data", "sku": "ZPP-H2H-2024"},
                {"title": "ZenConnect Enrollment Form", "sku": "ZPP-ZENCONNECT"},
            ]),
            False, False, False,
        ),
    ]
    return rows


def seed_hcp_awareness():
    """HCP awareness scores for TERR-001 HCPs."""
    import json
    return [
        (
            "AWR-001", "HCP001", "Dr. Jane Smith", "Gastroenterology", "TERR-001", "Q1 2026",
            88.0, 45.0, 92.0, 14, "2026-04-28",
            87.5, "High",
            json.dumps(["Flexible dosing", "ZenConnect program", "EPI patient ID"]),
            json.dumps(["Head-to-head vs Creon not discussed"]),
            "Schedule MSL visit to present ADVENT trial data",
        ),
        (
            "AWR-002", "HCP002", "Dr. Robert Chen", "Internal Medicine", "TERR-001", "Q1 2026",
            32.0, 15.0, 28.0, 3, "2026-04-15",
            31.0, "Low",
            json.dumps(["Basic product introduction"]),
            json.dumps(["Dosing guide not reviewed", "Patient support not discussed", "No samples given"]),
            "Schedule detail visit with full EPI starter kit and samples",
        ),
        (
            "AWR-003", "HCP003", "Dr. Alice Patel", "Gastroenterology", "TERR-001", "Q1 2026",
            78.0, 60.0, 85.0, 11, "2026-04-25",
            78.5, "High",
            json.dumps(["ADVENT trial", "Flexible dosing", "Patient assistance"]),
            json.dumps(["Pancreatic cancer indication not detailed"]),
            "Reinforce IBD comorbidity messaging in next call",
        ),
        (
            "AWR-004", "HCP005", "Dr. Sarah Kim", "Gastroenterology", "TERR-001", "Q1 2026",
            45.0, 70.0, 42.0, 5, "2026-04-10",
            44.0, "Medium",
            json.dumps(["Basic EPI messaging"]),
            json.dumps(["Zenpep vs generic PERT not discussed", "ZenConnect not presented"]),
            "Present generic-to-brand switch data and ZenConnect co-pay card",
        ),
        (
            "AWR-005", "HCP007", "Dr. Emily Walsh", "Gastroenterology", "TERR-001", "Q1 2026",
            72.0, 35.0, 88.0, 9, "2026-04-28",
            74.0, "High",
            json.dumps(["Dosing chart", "Samples left", "EPI patient commitment"]),
            json.dumps(["Speaker program opportunity not discussed"]),
            "Follow up on new EPI patient started — request speaker program nomination",
        ),
        (
            "AWR-006", "HCP006", "Dr. David Nguyen", "Internal Medicine", "TERR-001", "Q1 2026",
            38.0, 55.0, 30.0, 2, "2026-01-15",
            36.0, "Low",
            json.dumps(["Initial product mention"]),
            json.dumps(["Coverage objection not resolved", "ZenConnect not presented", "No follow-up scheduled"]),
            "Immediate re-engagement required — address coverage objection with PA support",
        ),
        (
            "AWR-007", "HCP004", "Dr. Michael Torres", "Oncology", "TERR-001", "Q1 2026",
            55.0, 40.0, 65.0, 6, "2026-04-12",
            55.5, "Medium",
            json.dumps(["Pancreatic oncology indication", "ADVENT trial reprint left"]),
            json.dumps(["Post-surgery EPI dosing protocol not covered"]),
            "Detail on post-pancreatectomy EPI management in next visit",
        ),
        (
            "AWR-008", "HCP008", "Dr. James Brown", "Pediatric GI", "TERR-001", "Q1 2026",
            42.0, 50.0, 38.0, 4, "2026-03-28",
            41.0, "Medium",
            json.dumps(["Pediatric dosing", "CF indication discussed"]),
            json.dumps(["ZenConnect pediatric program not presented", "Samples not provided"]),
            "Provide pediatric patient starter pack and ZenConnect enrollment info",
        ),
    ]


def seed_competitive_intel():
    """Competitive intelligence for TERR-001."""
    import json
    return [
        (
            "CI-001", "Creon (AbbVie)", "TERR-001", "Q1 2026",
            "Faster onset claims in cardiology messaging",
            "2026-04-26", 8, -2.1,
            json.dumps([
                {"code": "I50.9", "label": "Heart Failure", "hcp_count": 12},
                {"code": "I25.10", "label": "CAD", "hcp_count": 8},
            ]),
            "Call transcripts + field reports",
            88.0, "High",
            "Immediately counter with Zenpep non-enteric-coated microsphere data showing consistent enzyme "
            "delivery across gastric pH levels. Highlight ZenConnect co-pay advantage.",
            "APEX Trial 2024 (SKU: APEX-2024-01); Competitive Positioning Guide (MLR v2.1)",
            "NLP_CLUSTER",
        ),
        (
            "CI-002", "Pancreaze (Janssen)", "TERR-001", "Q1 2026",
            "Rep activity spike targeting high-decile GI specialists",
            "2026-04-25", 9, -1.5,
            json.dumps([
                {"code": "K86.81", "label": "EPI", "hcp_count": 9},
                {"code": "K86.89", "label": "Other Pancreatic Disease", "hcp_count": 6},
            ]),
            "Veeva CRM call frequency data",
            72.0, "High",
            "Deploy microsphere differentiation messaging. Emphasize Zenpep's 5-strength range vs Pancreaze "
            "for flexible titration. Leverage ZenConnect co-pay card for new starters.",
            "Zenpep Microsphere Differentiation Deck (SKU: ZPP-COMP-DIFF)",
            "ANOMALY",
        ),
        (
            "CI-003", "Generic PERT", "TERR-001", "Q1 2026",
            "New HCP writers switching to generic PERT for cost reasons",
            "2026-04-24", 5, -0.8,
            json.dumps([
                {"code": "K86.81", "label": "EPI", "hcp_count": 5},
            ]),
            "Prescribing data + new writer detection",
            55.0, "Medium",
            "Present clinical data showing branded PERT superiority in fat absorption coefficient. "
            "Provide ZenConnect card to eliminate cost barrier for patients.",
            "Generic vs Brand EPI Outcomes Study; ZenConnect Savings Card",
            "NLP_CLUSTER",
        ),
    ]


def seed_payer_access():
    """Payer access changes for TERR-001."""
    return [
        (
            "PA-001", "BlueCross Northeast", "TERR-001", "Q1 2026",
            3, 2, "2026-04-25", "NON-PREFERRED",
            340, 47, True,
            82.0, "High",
            "Immediate payer access outreach required. Coordinate with market access team on Aetna tier appeal. "
            "Provide HCPs with prior authorization assistance scripts for affected patients. "
            "Enroll eligible patients in ZenConnect Savings Program to offset tier change.",
            "ZenConnect Savings Card eliminates copay for most commercially insured patients. "
            "Free trial available for tier-3 patients while appeal is pending.",
            "DOWNGRADE",
        ),
        (
            "PA-002", "Aetna Commercial", "TERR-001", "Q1 2026",
            2, 2, "2026-01-01", "PREFERRED",
            1250, 0, False,
            18.0, "Low",
            "No immediate action required. Monitor formulary status quarterly.",
            "Currently Tier 2 Preferred — no patient access barriers.",
            "UNCHANGED",
        ),
        (
            "PA-003", "United HealthCare", "TERR-001", "Q1 2026",
            2, 3, "2026-03-01", "PREFERRED",
            890, 12, True,
            68.0, "High",
            "UHC upgraded Zenpep from Tier 3 to Tier 2 effective Mar 1, 2026. "
            "Communicate formulary improvement to all affected HCPs. "
            "Discontinue unnecessary prior authorization submissions.",
            "Tier upgrade — patients previously on PA may no longer need it.",
            "UPGRADE",
        ),
        (
            "PA-004", "Medicaid - Illinois", "TERR-001", "Q1 2026",
            3, 3, "2026-04-01", "PA_REQUIRED",
            520, 8, True,
            55.0, "Medium",
            "Prior authorization required for all Medicaid Illinois patients. "
            "Use PA support line (1-800-XXX-XXXX) for expedited processing. "
            "Ensure HCPs have PA completion guide.",
            "ZenConnect not applicable to Medicaid. Patient Assistance Program available for qualifying patients.",
            "UNCHANGED",
        ),
    ]


def seed_employees():
    return [
        ("REP001", "EMP-001", "Rahul", "Pandarp", "Rahul Pandarp",
         "rahulpandarp1998@gmail.com", "Senior Sales Rep", "rep", None, True, date(2022, 3, 1)),
    ]


def seed_employee_territories():
    return [
        ("ET-001", "REP001", "TERR-001", date(2022, 3, 1), None, True),
    ]


# ─── Main ─────────────────────────────────────────────────────────────────────

def run():
    with engine.begin() as conn:
        print("Creating schema and tables…")
        for stmt in DDL.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                conn.execute(text(stmt))

        print("Truncating existing demo data…")
        for tbl in [
            "insight360_payer_access_dul",
            "insight360_competitive_intel_dul",
            "insight360_hcp_awareness_dul",
            "insight360_active_alerts_dul",
            "insight360_call_transcripts_dul",
            "insight360_objection_handler_dul",
            "insight360_new_writer_id",
            "insight360_peer_match_dul",
            "vw_tfact_callactivitydetails_zenpep_reporting_dul",
            "vw_tfact_prescribersales_zenpep_reporting_dul",
            "vw_tdim_healthcarepractitioner_zenpep_reporting_dul",
            "vw_tdim_terr_hierarchy_zenpep_reporting_dul",
            "vw_tdim_employee_territory_zenpep_reporting",
            "vw_tdim_employee_zenpep_reporting_dul",
        ]:
            conn.execute(text(f"TRUNCATE TABLE {SCHEMA}.{tbl} CASCADE"))

        print("Seeding territory hierarchy…")
        for r in seed_territory():
            conn.execute(text(f"""
                INSERT INTO {SCHEMA}.vw_tdim_terr_hierarchy_zenpep_reporting_dul
                (territory_id,territory_name,territory_code,district_id,district_name,
                 region_id,region_name,area_id,area_name,zone_id,zone_name)
                VALUES (:tid,:tn,:tc,:did,:dn,:rid,:rn,:aid,:an,:zid,:zn)
            """), dict(zip(
                ["tid","tn","tc","did","dn","rid","rn","aid","an","zid","zn"], r
            )))

        print("Seeding HCPs…")
        for r in seed_hcps():
            conn.execute(text(f"""
                INSERT INTO {SCHEMA}.vw_tdim_healthcarepractitioner_zenpep_reporting_dul
                (hcp_id,npi_number,hcp_first_name,hcp_last_name,hcp_full_name,
                 specialty,sub_specialty,address_line1,address_line2,city,state,zip_code,
                 territory_id,hcp_segment,decile_rank,icd10_codes,is_active,
                 affiliated_hospital,affiliated_group)
                VALUES (:a,:b,:c,:d,:e,:f,:g,:h,:i,:j,:k,:l,:m,:n,:o,:p,:q,:r,:s)
            """), dict(zip("abcdefghijklmnopqrs", r)))

        print("Seeding prescriber sales…")
        for r in seed_prescriber_sales():
            conn.execute(text(f"""
                INSERT INTO {SCHEMA}.vw_tfact_prescribersales_zenpep_reporting_dul
                (record_id,hcp_id,territory_id,product_name,brand_name,market_name,
                 year,quarter,month,period_date,total_rx,new_rx,refill_rx,
                 market_total_rx,competitor_rx,market_share,competitor_brand,is_brand)
                VALUES (:a,:b,:c,:d,:e,:f,:g,:h,:i,:j,:k,:l,:m,:n,:o,:p,:q,:r)
            """), dict(zip("abcdefghijklmnopqr", r)))

        print("Seeding call activity…")
        for r in seed_call_activity():
            conn.execute(text(f"""
                INSERT INTO {SCHEMA}.vw_tfact_callactivitydetails_zenpep_reporting_dul
                (call_id,hcp_id,rep_id,territory_id,call_date,call_type,call_outcome,
                 products_discussed,call_notes,is_reached,call_duration_minutes,
                 rx_written_at_call,next_call_planned)
                VALUES (:a,:b,:c,:d,:e,:f,:g,:h,:i,:j,:k,:l,:m)
            """), dict(zip("abcdefghijklm", r)))

        print("Seeding peer matches…")
        for r in seed_peer_matches():
            conn.execute(text(f"""
                INSERT INTO {SCHEMA}.insight360_peer_match_dul
                (match_id,hcp_id,peer_hcp_id,peer_hcp_name,match_score,
                 match_rationale,shared_specialty,shared_institution,peer_brand_rx_q1,territory_id)
                VALUES (:a,:b,:c,:d,:e,:f,:g,:h,:i,:j)
            """), dict(zip("abcdefghij", r)))

        print("Seeding new writer ID cards…")
        for r in seed_new_writer_cards():
            conn.execute(text(f"""
                INSERT INTO {SCHEMA}.insight360_new_writer_id
                (hcp_id, name, specialty, affiliated_hospital, last_nrx_date,
                 ai_warm_approach_text, ai_icd10_matched_codes, top_5_in_class_rx,
                 total_in_class_rx, ai_peer_match_score, analysis_badges)
                VALUES (:a,:b,:c,:d,:e,:f,:g,:h,:i,:j,:k)
            """), dict(zip("abcdefghijk", r)))

        print("Seeding objection handler…")
        for r in seed_objections():
            conn.execute(text(f"""
                INSERT INTO {SCHEMA}.insight360_objection_handler_dul
                (objection_id,objection_type,objection_text,hcp_segment,
                 recommended_response,response_source,sku,success_rate,call_count,
                 territory_id,period)
                VALUES (:a,:b,:c,:d,:e,:f,:g,:h,:i,:j,:k)
            """), dict(zip("abcdefghijk", r)))

        print("Seeding call transcripts…")
        for r in seed_call_transcripts():
            conn.execute(text(f"""
                INSERT INTO {SCHEMA}.insight360_call_transcripts_dul
                (transcript_id,call_id,hcp_id,rep_id,territory_id,call_date,
                 transcript_text,has_objection,objection_types,objection_resolved,
                 rx_within_30_days,sentiment_score)
                VALUES (:a,:b,:c,:d,:e,:f,:g,:h,:i,:j,:k,:l)
            """), dict(zip("abcdefghijkl", r)))

        print("Seeding employees…")
        for r in seed_employees():
            conn.execute(text(f"""
                INSERT INTO {SCHEMA}.vw_tdim_employee_zenpep_reporting_dul
                (rep_id,employee_id,first_name,last_name,full_name,email,title,role,
                 manager_id,is_active,hire_date)
                VALUES (:a,:b,:c,:d,:e,:f,:g,:h,:i,:j,:k)
            """), dict(zip("abcdefghijk", r)))

        for r in seed_employee_territories():
            conn.execute(text(f"""
                INSERT INTO {SCHEMA}.vw_tdim_employee_territory_zenpep_reporting
                (record_id,rep_id,territory_id,effective_start_date,effective_end_date,is_current)
                VALUES (:a,:b,:c,:d,:e,:f)
            """), dict(zip("abcdef", r)))

        print("Seeding active alerts…")
        for r in seed_active_alerts():
            conn.execute(text(f"""
                INSERT INTO {SCHEMA}.insight360_active_alerts_dul
                (alert_id, alert_type, severity, detection_method, title, description,
                 detected_at, territory_id, period,
                 ai_affected_hcp_count, ai_territory_reach, ai_rx_risk,
                 ai_icd10_codes_affected, ai_prescribing_drift_note, ai_detection_lead_weeks,
                 ai_counter_script, ai_supporting_materials,
                 is_acknowledged, is_dismissed, is_deployed)
                VALUES (:a,:b,:c,:d,:e,:f,:g,:h,:i,:j,:k,:l,:m,:n,:o,:p,:q,:r,:s,:t)
            """), dict(zip("abcdefghijklmnopqrst", r)))

        print("Seeding HCP awareness…")
        for r in seed_hcp_awareness():
            conn.execute(text(f"""
                INSERT INTO {SCHEMA}.insight360_hcp_awareness_dul
                (awareness_id, hcp_id, hcp_full_name, specialty, territory_id, period,
                 product_awareness_score, competitor_awareness_score, clinical_evidence_score,
                 total_interactions, last_interaction_date,
                 ai_awareness_score, ai_awareness_level,
                 ai_key_messages_delivered, ai_knowledge_gaps, ai_recommended_action)
                VALUES (:a,:b,:c,:d,:e,:f,:g,:h,:i,:j,:k,:l,:m,:n,:o,:p)
            """), dict(zip("abcdefghijklmnop", r)))

        print("Seeding competitive intel…")
        for r in seed_competitive_intel():
            conn.execute(text(f"""
                INSERT INTO {SCHEMA}.insight360_competitive_intel_dul
                (intel_id, competitor_name, territory_id, period,
                 message_theme, detection_date, affected_hcp_count, market_share_change_pct,
                 icd10_focus, source_channel,
                 ai_threat_score, ai_threat_level,
                 ai_counter_strategy, ai_supporting_evidence, ai_detection_method)
                VALUES (:a,:b,:c,:d,:e,:f,:g,:h,:i,:j,:k,:l,:m,:n,:o)
            """), dict(zip("abcdefghijklmno", r)))

        print("Seeding payer access…")
        for r in seed_payer_access():
            conn.execute(text(f"""
                INSERT INTO {SCHEMA}.insight360_payer_access_dul
                (access_id, payer_name, territory_id, period,
                 product_tier_current, product_tier_previous, tier_change_date, formulary_status,
                 covered_lives, affected_hcp_count, patient_assistance_available,
                 ai_impact_score, ai_access_impact,
                 ai_action_required, ai_patient_assistance_note, ai_tier_change_direction)
                VALUES (:a,:b,:c,:d,:e,:f,:g,:h,:i,:j,:k,:l,:m,:n,:o,:p)
            """), dict(zip("abcdefghijklmnop", r)))

    print("\n✅ Demo data seeded successfully!")
    print("   Territory: TERR-001 (Boston North)")
    print("   HCPs: 8  (3 HIGH priority, 2 MEDIUM, 1 LOW, 3 non-writers)")
    print("   Objections: 5 (2 HIGH, 1 MEDIUM, 2 MEDIUM/LOW)")
    print("   Call transcripts: 4")
    print("   Active alerts: 8  (2 CRITICAL, 3 HIGH, 2 MEDIUM)")
    print("   HCP awareness: 8")
    print("   Competitive intel: 3")
    print("   Payer access: 4")


if __name__ == "__main__":
    run()
