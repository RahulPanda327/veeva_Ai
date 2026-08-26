"""Pydantic schemas for Module 1 — Territory Prioritization."""
from typing import Literal, Optional
from pydantic import BaseModel, Field

from app.schemas.filters import OrgFilters


class HCPViewProfile(BaseModel):
    formatted_name: Optional[str] = None
    specialist_description: Optional[str] = None
    is_ama_do_not_contact: Optional[str] = None
    email: Optional[str] = None
    hcp_status: Optional[str] = None
    hcp_type: Optional[str] = None
    medical_degree: Optional[str] = None
    npi: Optional[str] = None
    pdrp_output: Optional[str] = None
    website: Optional[str] = None
    target: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None
    state: Optional[str] = None


class NewWriterKPIs(BaseModel):
    """Module 2 tiles, surfaced on the Territory Prioritization summary.

    Counted over the same candidate list /new-writers/candidates returns for the
    current filter, so a tile here and the module's own screen can never disagree.
    """

    Non_writers_in_Territory: int = Field(
        default=0,
        description="HCPs in the territory not currently prescribing the product, "
                    "but plausible new writers",
    )
    Prescribing_in_class: int = Field(
        default=0,
        description="HCPs prescribing other products in the same therapeutic class, "
                    "making them candidates",
    )
    Diagnosis_match: int = Field(
        default=0,
        description="HCPs whose patient diagnoses match the conditions the product treats",
    )
    Warm_condidates: int = Field(
        default=0,
        description="High-potential HCPs backed by two or more signals "
                    "(in-class prescribing, diagnosis match, peer affinity)",
    )


class ObjectionHandlerKPIs(BaseModel):
    """Module 3 tiles, surfaced on the Territory Prioritization summary.

    Counted over the same objection rows /objections/list returns for the current
    filter, for the same reason as NewWriterKPIs.
    """

    calls_analysed: int = Field(
        default=0, description="Field calls the AI examined for objections"
    )
    objections_detected: int = Field(
        default=0, description="Objections identified across those calls"
    )
    recurring_patterns: int = Field(
        default=0, description="Objections seen in more than one call rather than once"
    )
    High_frequency: int = Field(
        default=0, description="Objections labelled HIGH frequency, needing most attention"
    )


class TerritorySummary(BaseModel):
    total_hcps: int
    high_priority_count: int
    medium_priority_count: int
    low_priority_count: int
    weekly_target: int
    period: str
    last_refresh: str
    territory_id: str
    territory_name: Optional[str] = None
    filters: Optional[OrgFilters] = Field(
        default=None, description="Manager → employee → territory tree for the filter dropdowns"
    )
    # Declared with defaults rather than Optional[...] = None so the two blocks are
    # always present in the payload. response_model drops anything the schema does
    # not name, and a client rendering KPI tiles should not have to branch on a
    # missing key when the honest answer is a zero.
    new_writer_id: NewWriterKPIs = Field(default_factory=NewWriterKPIs)
    objection_handler: ObjectionHandlerKPIs = Field(default_factory=ObjectionHandlerKPIs)


class HCPRankedItem(BaseModel):
    hcp_id: str
    name: str
    specialty: Optional[str] = None
    segment: Optional[str] = None
    view_profile: Optional[HCPViewProfile] = None
    rx_q1: float = Field(default=0.0, description="Total brand Rx in current quarter")
    rx_q4: float = Field(default=0.0, description="Total brand Rx in prior quarter")
    last_rx_date: Optional[str] = None           # most recent date with Zenpep Rx > 0
    last_call_date: Optional[str] = None          # HCP dim view Modified_Date
    ai_priority_tier: Literal["HIGH", "MEDIUM", "LOW"] = "LOW"
    # The composite score the tier is derived from, as a display string ("70.44%").
    # Declared here or FastAPI drops it: response_model=List[HCPRankedItem] filters
    # the payload to the fields on this model, so a key the service sets but the
    # schema does not name never reaches the client.
    ai_score: Optional[str] = Field(
        default=None, description="Composite AI priority score, formatted for display"
    )
    ai_score_reason: Optional[str] = Field(
        default=None, description="One or two sentences explaining how ai_score was reached"
    )
    ai_generated_insight: Optional[str] = None


class HCPInsightResponse(BaseModel):
    hcp_id: str
    ai_generated_insight: str
    ai_insight_highlight: Optional[str] = None
    generated_at: str
    cached: bool = False
