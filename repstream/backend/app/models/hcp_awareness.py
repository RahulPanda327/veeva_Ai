"""SQLAlchemy model for insight360_hcp_awareness (read-only)."""
from sqlalchemy import Column, String
from app.database import Base
from app.config import settings


class HCPAwareness(Base):
    __tablename__ = "insight360_hcp_awareness"
    __table_args__ = {"schema": settings.HUB_SCHEMA, "extend_existing": True}

    hcp_id             = Column("HCP_Durable_Id",         String(50),  primary_key=True)
    hcp_full_name      = Column("HCP_Full_Name",          String(200))
    specialty          = Column("Specialty",              String(100))
    city_state         = Column("City_State",             String(200))

    # 4 weekly awareness scores stored as "84.7%" strings
    score_jan29        = Column("Awareness_Score_Jan29",  String(20))
    score_feb26        = Column("Awareness_Score_Feb26",  String(20))
    score_mar25        = Column("Awareness_Score_Mar25",  String(20))
    score_apr22        = Column("Awareness_Score_Apr22",  String(20))

    score_change_pct        = Column("Score_Change_Pct",        String(20))
    trend_direction         = Column("Trend_Direction",         String(50))
    root_cause_signal       = Column("Root_Cause_Signal",       String(500))
    re_engagement_priority  = Column("Re_Engagement_Priority",  String(20))
