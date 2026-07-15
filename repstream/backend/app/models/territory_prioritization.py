"""SQLAlchemy models for the Territory Prioritization module (all read-only)."""
from sqlalchemy import Boolean, Column, Date, DateTime, Float, Integer, String, Text, func
from app.database import Base
from app.config import settings


class HealthcarePractitioner(Base):
    """Maps to vw_tdim_healthcarepractitioner_zenpep_reporting."""

    __tablename__ = "vw_tdim_healthcarepractitioner_zenpep_reporting"
    __table_args__ = {"schema": settings.HUB_SCHEMA, "extend_existing": True}

    hcp_id = Column(String(50), primary_key=True)
    npi_number = Column(String(20))
    hcp_first_name = Column(String(100))
    hcp_last_name = Column(String(100))
    hcp_full_name = Column(String(200))
    specialty = Column(String(100))
    sub_specialty = Column(String(100))
    address_line1 = Column(String(200))
    address_line2 = Column(String(200))
    city = Column(String(100))
    state = Column(String(50))
    zip_code = Column(String(20))
    territory_id = Column(String(50))
    hcp_segment = Column(String(50))
    decile_rank = Column(Integer)
    icd10_codes = Column(String(500))
    is_active = Column(Boolean, default=True)
    affiliated_hospital = Column(String(200))
    affiliated_group = Column(String(200))


class PrescriberSales(Base):
    """Maps to vw_tfact_prescribersales_zenpep_reporting."""

    __tablename__ = "vw_tfact_prescribersales_zenpep_reporting"
    __table_args__ = {"schema": settings.HUB_SCHEMA, "extend_existing": True}

    record_id = Column(String(80), primary_key=True)
    hcp_id = Column(String(50), index=True)
    territory_id = Column(String(50), index=True)
    product_name = Column(String(100))
    brand_name = Column(String(100))
    market_name = Column(String(100))
    year = Column(Integer)
    quarter = Column(Integer)
    month = Column(Integer)
    period_date = Column(Date)
    total_rx = Column(Float, default=0.0)
    new_rx = Column(Float, default=0.0)
    refill_rx = Column(Float, default=0.0)
    market_total_rx = Column(Float, default=0.0)
    competitor_rx = Column(Float, default=0.0)
    market_share = Column(Float, default=0.0)
    competitor_brand = Column(String(100))
    is_brand = Column(Integer, default=0)


class CallActivity(Base):
    """Maps to vw_tfact_callactivitydetails_zenpep_reporting."""

    __tablename__ = "vw_tfact_callactivitydetails_zenpep_reporting"
    __table_args__ = {"schema": settings.HUB_SCHEMA, "extend_existing": True}

    call_id = Column(String(80), primary_key=True)
    hcp_id = Column(String(50), index=True)
    rep_id = Column(String(50), index=True)
    territory_id = Column(String(50), index=True)
    call_date = Column(Date)
    call_type = Column(String(50))
    call_outcome = Column(String(50))
    products_discussed = Column(Text)
    call_notes = Column(Text)
    is_reached = Column(Boolean, default=True)
    call_duration_minutes = Column(Integer)
    rx_written_at_call = Column(Boolean, default=False)
    next_call_planned = Column(Date)


class TerritoryHierarchy(Base):
    """Maps to vw_tdim_terr_hierarchy_zenpep_reporting."""

    __tablename__ = "vw_tdim_terr_hierarchy_zenpep_reporting"
    __table_args__ = {"schema": settings.HUB_SCHEMA, "extend_existing": True}

    territory_id = Column("sf_terr_pk", String(100), primary_key=True)
    territory_name = Column(String(100))
    territory_code = Column(String(50))
    district_id = Column(String(50))
    district_name = Column(String(100))
    region_id = Column(String(50))
    region_name = Column(String(100))
    area_id = Column(String(50))
    area_name = Column(String(100))
    zone_id = Column(String(50))
    zone_name = Column(String(100))
    is_active = Column(Boolean, default=True)


class Employee(Base):
    """Maps to vw_tdim_employee_zenpep_reporting."""

    __tablename__ = "vw_tdim_employee_zenpep_reporting"
    __table_args__ = {"schema": settings.HUB_SCHEMA, "extend_existing": True}

    rep_id = Column(String(50), primary_key=True)
    employee_id = Column(String(50))
    first_name = Column(String(100))
    last_name = Column(String(100))
    full_name = Column(String(200))
    email = Column(String(200))
    title = Column(String(100))
    role = Column(String(100))
    manager_id = Column(String(50))
    is_active = Column(Boolean, default=True)
    hire_date = Column(Date)


class EmployeeTerritory(Base):
    """Maps to vw_tdim_employee_territory_zenpep_reporting."""

    __tablename__ = "vw_tdim_employee_territory_zenpep_reporting"
    __table_args__ = {"schema": settings.HUB_SCHEMA, "extend_existing": True}

    record_id = Column(String(80), primary_key=True)
    rep_id = Column(String(50), index=True)
    territory_id = Column(String(50), index=True)
    effective_start_date = Column(Date)
    effective_end_date = Column(Date)
    is_current = Column(Boolean, default=True)
