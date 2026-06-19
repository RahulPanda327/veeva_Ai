"""Weekly Celery batch: refresh Module 1 Territory Prioritization cache."""
import logging
from datetime import date

from app.database import SessionLocal
from app.services.territory_prioritization.ai_ranking import rank_hcps
from app.services.territory_prioritization.data_ingestion import (
    get_current_and_prior_quarter,
    load_last_call_dates,
    load_rx_for_territory,
    load_territory_hcps,
)
from app.services.territory_prioritization.feature_engineering import build_hcp_features
from app.services.territory_prioritization.llm_insight import generate_hcp_insight
from app.utils.cache import cache_delete_pattern, cache_set, territory_cache_key
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _get_all_territory_ids(db) -> list[str]:
    from sqlalchemy import select, distinct
    from app.models.territory_prioritization import TerritoryHierarchy
    rows = db.execute(select(distinct(TerritoryHierarchy.territory_id))).scalars().all()
    return list(rows)


@celery_app.task(name="app.tasks.refresh_territory.refresh_all_territories", bind=True, max_retries=3)
def refresh_all_territories(self):
    """Recompute ranked HCP list + AI insights for every active territory."""
    logger.info("Starting weekly Territory Prioritization refresh.")
    db = SessionLocal()
    try:
        territory_ids = _get_all_territory_ids(db)
        for territory_id in territory_ids:
            try:
                _refresh_single_territory(db, territory_id)
            except Exception as exc:
                logger.error("Failed to refresh territory %s: %s", territory_id, exc)
        logger.info("Territory refresh complete. %d territories processed.", len(territory_ids))
    finally:
        db.close()


def _refresh_single_territory(db, territory_id: str):
    ref_date = date.today()
    (yr1, q1), (yr4, q4) = get_current_and_prior_quarter(ref_date)
    period = f"Q{q1} {yr1}"

    hcps = load_territory_hcps(db, territory_id)
    rx_data = load_rx_for_territory(db, territory_id, yr1, q1, yr4, q4)
    last_calls = load_last_call_dates(db, territory_id)
    features = build_hcp_features(hcps, rx_data, last_calls)
    ranked = rank_hcps(features)

    for hcp in ranked:
        try:
            hcp["ai_insight"] = generate_hcp_insight(hcp)
        except Exception as exc:
            logger.warning("LLM insight failed for hcp %s: %s", hcp["hcp_id"], exc)
            hcp["ai_insight"] = None
        hcp["period"] = period

    cache_key = territory_cache_key("territory:ranked_hcps", territory_id)
    cache_set(cache_key, ranked, ttl=7 * 24 * 3600)   # 7-day TTL for weekly batch
    logger.debug("Territory %s: %d HCPs cached.", territory_id, len(ranked))
