"""Load call transcripts batch for Module 3 NLP analysis."""
from typing import List

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.objection_handler import CallTranscript


def load_transcripts(
    db: Session,
    territory_id: str,
    period_start: str,
    period_end: str,
) -> List[CallTranscript]:
    """Return all transcripts for a territory within a date range."""
    stmt = (
        select(CallTranscript)
        .where(
            CallTranscript.territory_id == territory_id,
            CallTranscript.call_date >= period_start,
            CallTranscript.call_date <= period_end,
        )
        .order_by(CallTranscript.call_date.desc())
    )
    return list(db.scalars(stmt).all())


def load_transcripts_with_objections(
    db: Session,
    territory_id: str,
    period_start: str,
    period_end: str,
) -> List[CallTranscript]:
    """Return only transcripts flagged as containing objections."""
    stmt = (
        select(CallTranscript)
        .where(
            CallTranscript.territory_id == territory_id,
            CallTranscript.has_objection.is_(True),
            CallTranscript.call_date >= period_start,
            CallTranscript.call_date <= period_end,
        )
    )
    return list(db.scalars(stmt).all())
