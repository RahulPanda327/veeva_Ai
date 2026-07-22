"""SQLAlchemy model for insight360_competitive_intel (read-only)."""
from sqlalchemy import Column, String
from app.database import Base
from app.config import settings


class CompetitiveIntel(Base):
    __tablename__ = "insight360_competitive_intel"
    __table_args__ = {"schema": settings.HUB_SCHEMA, "extend_existing": True}

    intel_id                    = Column("Signal_Id",                   String(80),  primary_key=True)
    territory_id                = Column("Territory_Durable_Id",        String(50))
    territory_name              = Column("Territory_Name",              String(200))
    district_name                = Column("District_Name",               String(200))
    signal_type                 = Column("Signal_Type",                 String(50))   # AI DETECTED / ML TREND / ANOMALY
    competitor_name             = Column("Competitor_Name",             String(100))
    description                 = Column("Signal_Description",          String(500))
    market_share_change_pct     = Column("Market_Share_Change_Pct",     String(20))   # "-4.2%"
    competitor_call_freq_change = Column("Competitor_Call_Freq_Change", String(20))   # "+68%"
    counter_strategy            = Column("Counter_Strategy",            String(500))
    detection_date               = Column("Detection_Date",              String(20))
    # No Region_Name or Territory_Sales column exists on insight360_competitive_intel
    # (verified against INFORMATION_SCHEMA.COLUMNS) — those response fields are
    # always None for DB-sourced rows; only the sample fallback data has them.
