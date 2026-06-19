"""SQLAlchemy models for the New Writer ID module (all read-only)."""
from sqlalchemy import Column, DateTime, Float, String, Text, func
from app.database import Base
from app.config import settings


class PeerMatch(Base):
    """Maps to insight360_peer_match (enriched table)."""

    __tablename__ = "insight360_peer_match"
    __table_args__ = {"schema": settings.HUB_SCHEMA, "extend_existing": True}

    match_id = Column(String(80), primary_key=True)
    hcp_id = Column(String(50), index=True)
    peer_hcp_id = Column(String(50))
    peer_hcp_name = Column(String(200))
    match_score = Column(Float)
    match_rationale = Column(Text)
    shared_specialty = Column(String(100))
    shared_institution = Column(String(200))
    peer_brand_rx_q1 = Column(Float, default=0.0)
    territory_id = Column(String(50), index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
