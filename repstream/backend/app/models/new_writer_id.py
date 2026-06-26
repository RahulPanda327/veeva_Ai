"""SQLAlchemy models for the New Writer ID module (all read-only).

Column names verified against live Azure Synapse DB via sql_query_kpi_7to19.sql (KPI 7).
"""
from sqlalchemy import Column, String, Text
from app.database import Base
from app.config import settings


class PeerMatch(Base):
    """Maps to insight360_peer_match (KPI 7).

    Peer_Match_Pct is stored as a percentage string e.g. "87%".
    Parse to float with: float(row.peer_match_pct.replace('%', ''))
    """

    __tablename__ = "insight360_peer_match"
    __table_args__ = {"schema": settings.HUB_SCHEMA, "extend_existing": True}

    hcp_id              = Column("HCP_Durable_Id",        String(50),  primary_key=True)
    hcp_full_name       = Column("HCP_Full_Name",         String(200))
    specialty           = Column("Specialty",             String(100))
    city_state          = Column("City_State",            String(200))
    peer_match_pct      = Column("Peer_Match_Pct",        String(20))   # "87%"
    peer_connector_id   = Column("Peer_Connector_HCP_Id", String(50))
    peer_connector_name = Column("Peer_Connector_Name",   String(200))
    warm_approach_text  = Column("Warm_Approach_Text",    Text)
