"""SQLAlchemy model for insight360_hcp_awareness (read-only)."""
from sqlalchemy import Column, Date, DateTime, Float, Integer, String, Text, func
from app.database import Base
from app.config import settings


class HCPAwareness(Base):
    """Maps to insight360_hcp_awareness (cooked/enriched table)."""

    __tablename__ = "insight360_hcp_awareness"
    __table_args__ = {"schema": settings.HUB_SCHEMA, "extend_existing": True}

    awareness_id = Column(String(80), primary_key=True)
    hcp_id = Column(String(50), index=True)
    hcp_full_name = Column(String(200))
    specialty = Column(String(100))
    territory_id = Column(String(50), index=True)
    period = Column(String(20))

    # Awareness metrics
    product_awareness_score = Column(Float, default=0.0)    # 0-100
    competitor_awareness_score = Column(Float, default=0.0)
    clinical_evidence_score = Column(Float, default=0.0)
    total_interactions = Column(Integer, default=0)
    last_interaction_date = Column(Date)

    # AI output keys
    ai_awareness_score = Column(Float, default=0.0)         # composite 0-100
    ai_awareness_level = Column(String(20))                 # High / Medium / Low
    ai_key_messages_delivered = Column(Text)                # JSON list
    ai_knowledge_gaps = Column(Text)                        # JSON list of gap strings
    ai_recommended_action = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
