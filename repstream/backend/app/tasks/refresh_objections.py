"""Weekly Celery batch: refresh Module 3 Objection Handler cache."""
import logging
from datetime import date

from app.database import SessionLocal
from app.services.objection_handler.mlr_response_engine import load_all_objections
from app.services.objection_handler.objection_classifier import assign_frequency_label
from app.utils.cache import cache_set, territory_cache_key
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _get_all_territory_ids(db) -> list[str]:
    from sqlalchemy import select, distinct
    from app.models.territory_prioritization import TerritoryHierarchy
    return list(db.execute(select(distinct(TerritoryHierarchy.territory_id))).scalars().all())


@celery_app.task(name="app.tasks.refresh_objections.refresh_all_objections", bind=True, max_retries=3)
def refresh_all_objections(self):
    """Recompute objection list for every active territory for the current period."""
    logger.info("Starting weekly Objection Handler refresh.")
    db = SessionLocal()
    today = date.today()
    q = (today.month - 1) // 3 + 1
    period = f"Q{q} {today.year}"
    try:
        territory_ids = _get_all_territory_ids(db)
        for territory_id in territory_ids:
            try:
                rows = load_all_objections(db, [territory_id.split("|")[-1]], period)
                result = [
                    {
                        "objection_id": r.objection_id,
                        "objection_type": r.objection_type,
                        "objection_text": r.objection_text,
                        "frequency": assign_frequency_label(r.call_count or 0),
                        "call_count": r.call_count or 0,
                        "period": r.period or period,
                        "success_rate": r.success_rate or 0.0,
                        "territory_id": r.territory_id,
                    }
                    for r in rows
                ]
                cache_key = territory_cache_key(f"objections:list:{period}", territory_id)
                cache_set(cache_key, result, ttl=7 * 24 * 3600)
                logger.debug("Territory %s: %d objections cached.", territory_id, len(result))
            except Exception as exc:
                logger.error("Objection refresh failed for territory %s: %s", territory_id, exc)
        logger.info("Objection refresh complete for %d territories.", len(territory_ids))
    finally:
        db.close()
