"""SQLAlchemy models for the Objection Handler module (all read-only).

Column names verified against live Azure Synapse DB via sql_query_kpi_7to19.sql (KPI 8-11).
"""
from sqlalchemy import Column, String, Text
from app.database import Base
from app.config import settings


class ObjectionHandler(Base):
    """Maps to insight360_objection_handler_dul (KPI 9-11)."""

    __tablename__ = "insight360_objection_handler_dul"
    __table_args__ = {"schema": settings.HUB_SCHEMA, "extend_existing": True}

    transcript_id       = Column("Call_Transcript_Id",              String(80),  primary_key=True)
    hcp_id              = Column("HCP_Durable_Id",                  String(50),  index=True)
    territory_id        = Column("Territory_Durable_Id",            String(50),  index=True)
    hcp_full_name       = Column("HCP_Full_Name",                   String(200))
    call_date           = Column("Call_Date",                       String(30))
    objection_category  = Column("Objection_Category",              String(100), index=True)
    frequency_label     = Column("Objection_Frequency_Label",       String(20))   # HIGH / MEDIUM / LOW
    objection_text      = Column("Objection_Text",                  Text)
    transcript_summary  = Column("Transcript_Summary",              Text)
    call_count_mentions = Column("Call_Count_Mentions",             String(10))   # stored as string e.g. "12"
    detection_period    = Column("Detection_Period",                String(50))   # "Mar 15 - Apr 22"
    conversion_rate_pct = Column("Historical_Conversion_Rate_Pct", String(20))   # "67%"
    mlr_response        = Column("MLR_Approved_Response",           Text)
    mlr_sku_code        = Column("MLR_SKU_Code",                    String(100))


class CallTranscript(Base):
    """Maps to insight360_call_transcripts_dul (KPI 8)."""

    __tablename__ = "insight360_call_transcripts_dul"
    __table_args__ = {"schema": settings.HUB_SCHEMA, "extend_existing": True}

    call_id          = Column("Src_Call_Id",          String(80),  primary_key=True)
    hcp_id           = Column("HCP_Durable_Id",       String(50),  index=True)
    territory_id     = Column("Territory_Durable_Id", String(50),  index=True)
    call_date        = Column("Call_Date",            String(30))
    transcript_tone  = Column("Transcript_Tone",      String(30))   # POSITIVE / MIXED / OBJECTION
    product_detailed = Column("Product_Detailed",     String(50))   # ZENPEP / VOWST
    call_channel     = Column("Call_Channel",         String(20))   # F2F / VIRTUAL
