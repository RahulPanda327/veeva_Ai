"""SQLAlchemy model for insight360_competitive_intel (read-only)."""
from sqlalchemy import Column, Date, DateTime, Float, Integer, String, Text, func
from app.database import Base
from app.config import settings


class CompetitiveIntel(Base):
    """Maps to insight360_competitive_intel (cooked/enriched table)."""

    __tablename__ = "insight360_competitive_intel"
    __table_args__ = {"schema": settings.HUB_SCHEMA, "extend_existing": True}

    intel_id = Column(String(80), primary_key=True)
    competitor_name = Column(String(100))
    territory_id = Column(String(50), index=True)
    period = Column(String(20))

    # Signal data
    message_theme = Column(String(200))         # e.g. "faster onset claims"
    detection_date = Column(Date)
    affected_hcp_count = Column(Integer, default=0)
    market_share_change_pct = Column(Float, default=0.0)
    icd10_focus = Column(Text)                  # JSON list of ICD-10 objects
    source_channel = Column(String(100))        # e.g. "Call transcripts", "Field reports"

    # AI output keys
    ai_threat_score = Column(Float, default=0.0)       # 0-100
    ai_threat_level = Column(String(20))               # High / Medium / Low
    ai_counter_strategy = Column(Text)
    ai_supporting_evidence = Column(Text)              # trial name, SKU, guide
    ai_detection_method = Column(String(50))           # NLP_CLUSTER, ANOMALY, MANUAL

    created_at = Column(DateTime(timezone=True), server_default=func.now())
