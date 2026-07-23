"""SQLAlchemy model for insight360_payer_access_dul (read-only)."""
from sqlalchemy import Column, String
from app.database import Base
from app.config import settings


class PayerAccess(Base):
    __tablename__ = "insight360_payer_access_dul"
    __table_args__ = {"schema": settings.HUB_SCHEMA, "extend_existing": True}

    plan_id             = Column("Plan_Durable_Id",       String(80),  primary_key=True)
    territory_id        = Column("Territory_Durable_Id",   String(50),  index=True)
    payer_name          = Column("Plan_Name",             String(200))
    mco_org_name        = Column("MCO_Organization_Name", String(200))
    channel_name        = Column("Channel_Name",          String(50))   # Commercial / Medicare / Medicaid
    tier_current        = Column("Formulary_Tier",        String(30))   # "Tier 1" / "Tier 2" / "Non-Formulary"
    pa_required         = Column("PA_Required",           String(10))   # "Yes" / "No"
    recent_tier_change  = Column("Recent_Tier_Change",    String(10))   # "Yes" / "No"
    change_date         = Column("Change_Date",           String(20))
    ai_alert_flag       = Column("AI_Alert_Flag",         String(10))   # "Yes" / "No"
    tier_previous       = Column("Previous_Tier",         String(30))
    affected_hcp_count  = Column("Affected_HCP_Count",    String(10))
    covered_lives       = Column("Covered_Lives_Est",     String(20))
    impact_level        = Column("Access_Impact_Level",   String(20))   # HIGH / MEDIUM / LOW
    recommended_action  = Column("Recommended_Action",    String(500))
