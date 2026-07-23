"""SQLAlchemy models for the New Writer ID module (all read-only).

Column names verified against live Azure Synapse DB via sql_query_kpi_7to19.sql (KPI 7).
"""
from sqlalchemy import Column, Float, String, Text
from app.database import Base
from app.config import settings


class PeerMatch(Base):
    """Maps to insight360_peer_match_dul (KPI 7).

    Peer_Match_Pct is stored as a percentage string e.g. "87%".
    Parse to float with: float(row.peer_match_pct.replace('%', ''))
    """

    __tablename__ = "insight360_peer_match_dul"
    __table_args__ = {"schema": settings.HUB_SCHEMA, "extend_existing": True}

    hcp_id              = Column("HCP_Durable_Id",        String(50),  primary_key=True)
    hcp_full_name       = Column("HCP_Full_Name",         String(200))
    specialty           = Column("Specialty",             String(100))
    city_state          = Column("City_State",            String(200))
    peer_match_pct      = Column("Peer_Match_Pct",        String(20))   # "87%"
    peer_connector_id   = Column("Peer_Connector_HCP_Id", String(50))
    peer_connector_name = Column("Peer_Connector_Name",   String(200))
    warm_approach_text  = Column("Warm_Approach_Text",    Text)


class NewWriterCard(Base):
    """Maps to insight360_new_writer_id — the 11 keys rendered on the New Writer ID card.

    One flat enriched table (same pattern as insight360_active_alerts_dul /
    insight360_hcp_awareness_dul) instead of assembling the card from 3 sources
    (Rx views + insight360_peer_match_dul + Python-computed ICD-10/badges).

    Top_5_In_Class_Rx is a JSON-encoded list of {"brand": str, "rx": int}.
    Analysis_Badges and ICD10_Matched_Codes are pipe-separated strings.
    """

    __tablename__ = "insight360_new_writer_id"
    __table_args__ = {"schema": settings.HUB_SCHEMA, "extend_existing": True}

    hcp_id                 = Column("HCP_Durable_Id",     String(50),  primary_key=True)
    name                   = Column("HCP_Full_Name",      String(200))
    specialty              = Column("Specialty",          String(100))
    affiliated_hospital    = Column("Affiliated_Hospital", String(200))
    last_nrx_date          = Column("NBRx_Date",          String(50))   # "Feb 12, 2026"
    ai_warm_approach_text  = Column("Warm_Approach_Text", Text)
    ai_icd10_matched_codes = Column("ICD10_Matched_Codes", String(500))  # "E11.9|E78.5"
    top_5_in_class_rx      = Column("Top_5_In_Class_Rx",  Text)          # JSON list
    total_in_class_rx      = Column("Total_In_Class_Rx",  Float)
    ai_peer_match_score    = Column("Peer_Match_Score",   Float)         # 0-100
    analysis_badges        = Column("Analysis_Badges",    String(200))  # "ML_PATTERN_MATCHING|AI_MATCHED|AI_GENERATED"
