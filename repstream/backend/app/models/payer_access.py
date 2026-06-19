"""SQLAlchemy model for insight360_payer_access (read-only)."""
from sqlalchemy import Boolean, Column, Date, DateTime, Float, Integer, String, Text, func
from app.database import Base
from app.config import settings


class PayerAccess(Base):
    """Maps to insight360_payer_access (cooked/enriched table)."""

    __tablename__ = "insight360_payer_access"
    __table_args__ = {"schema": settings.HUB_SCHEMA, "extend_existing": True}

    access_id = Column(String(80), primary_key=True)
    payer_name = Column(String(200))
    territory_id = Column(String(50), index=True)
    period = Column(String(20))

    # Formulary data
    product_tier_current = Column(Integer)
    product_tier_previous = Column(Integer)
    tier_change_date = Column(Date)
    formulary_status = Column(String(50))       # PREFERRED, NON-PREFERRED, EXCLUDED, PA_REQUIRED
    covered_lives = Column(Integer, default=0)
    affected_hcp_count = Column(Integer, default=0)
    patient_assistance_available = Column(Boolean, default=False)

    # AI output keys
    ai_impact_score = Column(Float, default=0.0)       # 0-100
    ai_access_impact = Column(String(20))              # High / Medium / Low
    ai_action_required = Column(Text)
    ai_patient_assistance_note = Column(Text)
    ai_tier_change_direction = Column(String(20))      # UPGRADE / DOWNGRADE / UNCHANGED

    created_at = Column(DateTime(timezone=True), server_default=func.now())
