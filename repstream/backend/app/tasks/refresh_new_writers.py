"""Weekly Celery batch: refresh Module 2 New Writer Identification cache."""
import logging
from datetime import date

from app.database import SessionLocal
from app.services.new_writer_id.icd10_matching import enrich_with_icd10
from app.services.new_writer_id.match_scoring import enrich_with_peer_match
from app.services.new_writer_id.non_writer_detection import (
    detect_non_writers,
    enrich_with_hcp_dimensions,
)
from app.services.territory_prioritization.data_ingestion import get_current_and_prior_quarter
from app.utils.cache import cache_set, territory_cache_key
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _get_all_territory_ids(db) -> list[str]:
    from sqlalchemy import select, distinct
    from app.models.territory_prioritization import TerritoryHierarchy
    return list(db.execute(select(distinct(TerritoryHierarchy.territory_id))).scalars().all())


@celery_app.task(name="app.tasks.refresh_new_writers.refresh_all_new_writers", bind=True, max_retries=3)
def refresh_all_new_writers(self):
    """Recompute new-writer candidate list for every active territory."""
    logger.info("Starting weekly New Writer Identification refresh.")
    db = SessionLocal()
    try:
        territory_ids = _get_all_territory_ids(db)
        (yr1, q1), (yr4, q4) = get_current_and_prior_quarter(date.today())
        for territory_id in territory_ids:
            try:
                raw = detect_non_writers(db, territory_id, yr1, q1, yr4, q4)
                enriched = enrich_with_hcp_dimensions(db, raw, territory_id)
                enriched = enrich_with_icd10(enriched)
                enriched = enrich_with_peer_match(db, enriched, territory_id)
                cache_key = territory_cache_key("new_writers:candidates", territory_id)
                cache_set(cache_key, enriched, ttl=7 * 24 * 3600)
                logger.debug("Territory %s: %d new-writer candidates.", territory_id, len(enriched))
            except Exception as exc:
                logger.error("New writer refresh failed for territory %s: %s", territory_id, exc)
        logger.info("New Writer refresh complete.")
    finally:
        db.close()
