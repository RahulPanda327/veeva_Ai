"""SQLAlchemy model for hub_insight360.insight360_active_alerts (read-only).

Column names verified against live Azure Synapse DB on 2026-06-19.
"""
from sqlalchemy import Column, String, Text
from app.database import Base
from app.config import settings


class ActiveAlert(Base):
    __tablename__ = "insight360_active_alerts"
    __table_args__ = {"schema": settings.HUB_SCHEMA, "extend_existing": True}

    # Real DB column        Python attribute
    alert_id         = Column("Alert_Id",              String(80), primary_key=True)
    severity         = Column("Alert_Priority",         String(20))  # CRITICAL / HIGH / MEDIUM / LOW
    detection_method = Column("Alert_Type",             String(50))  # ANOMALY DETECTION / ML TREND / ANOMALY
    title            = Column("Alert_Title",            String(200))
    detected_at      = Column("Detection_Datetime",     String(50))  # stored as string "2026-04-28 08:15"
    territory_id     = Column("Territory_Durable_Id",   String(50),  index=True)
    territory_name   = Column("Territory_Name",         String(200))
    ai_affected_hcp_count = Column("Affected_HCP_Count",  String(10))   # stored as string e.g. "8"
    ai_territory_reach    = Column("Territory_Reach",      String(100))  # "3 of 12 territories"
    ai_rx_risk            = Column("Rx_Risk_Level",        String(20))   # High / Medium / Low
    ai_counter_script     = Column("Counter_Strategy",     Text)
    recommended_actions   = Column("Recommended_Actions",  Text)         # "Deploy to Field | View Affected HCPs | Dismiss"
