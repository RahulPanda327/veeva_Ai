"""SQLAlchemy models for the Objection Handler module (all read-only)."""
from sqlalchemy import Boolean, Column, Date, DateTime, Float, Integer, String, Text, func
from app.database import Base
from app.config import settings


class ObjectionHandler(Base):
    """Maps to insight360_objection_handler (enriched table)."""

    __tablename__ = "insight360_objection_handler"
    __table_args__ = {"schema": settings.HUB_SCHEMA, "extend_existing": True}

    objection_id = Column(String(80), primary_key=True)
    objection_type = Column(String(100), index=True)
    objection_text = Column(Text)
    hcp_segment = Column(String(50))
    recommended_response = Column(Text)
    response_source = Column(String(100))
    sku = Column(String(100))
    success_rate = Column(Float, default=0.0)
    call_count = Column(Integer, default=0)
    territory_id = Column(String(50), index=True)
    period = Column(String(20))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class CallTranscript(Base):
    """Maps to insight360_call_transcripts (enriched table)."""

    __tablename__ = "insight360_call_transcripts"
    __table_args__ = {"schema": settings.HUB_SCHEMA, "extend_existing": True}

    transcript_id = Column(String(80), primary_key=True)
    call_id = Column(String(80), index=True)
    hcp_id = Column(String(50), index=True)
    rep_id = Column(String(50), index=True)
    territory_id = Column(String(50), index=True)
    call_date = Column(Date)
    transcript_text = Column(Text)
    has_objection = Column(Boolean, default=False)
    objection_types = Column(Text)
    objection_resolved = Column(Boolean, default=False)
    rx_within_30_days = Column(Boolean, default=False)
    sentiment_score = Column(Float)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
