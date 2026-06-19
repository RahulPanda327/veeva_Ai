"""Pydantic schemas for HCP data."""
from typing import Optional
from pydantic import BaseModel


class HCPBase(BaseModel):
    hcp_id: str
    hcp_full_name: str
    specialty: Optional[str] = None
    territory_id: Optional[str] = None
    hcp_segment: Optional[str] = None
    npi_number: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None


class HCPResponse(HCPBase):
    sub_specialty: Optional[str] = None
    decile_rank: Optional[int] = None
    affiliated_hospital: Optional[str] = None

    model_config = {"from_attributes": True}
