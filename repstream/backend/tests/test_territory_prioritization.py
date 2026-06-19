"""Unit tests for Module 1 — Territory Prioritization service layer."""
import pytest
from datetime import date
from unittest.mock import MagicMock, patch

from app.services.territory_prioritization.ai_ranking import assign_priority_tier, rank_hcps
from app.services.territory_prioritization.feature_engineering import (
    compute_competitor_share,
    compute_percentile_threshold,
    compute_rx_trend,
)
from app.services.territory_prioritization.weekly_target import (
    build_territory_summary,
    compute_weekly_target,
)
from app.services.territory_prioritization.data_ingestion import get_current_and_prior_quarter


class TestRxTrend:
    def test_positive_trend(self):
        assert compute_rx_trend(45.0, 30.0) == pytest.approx(50.0, rel=1e-3)

    def test_negative_trend(self):
        assert compute_rx_trend(8.0, 12.0) == pytest.approx(-33.33, rel=1e-2)

    def test_zero_q4_returns_zero(self):
        assert compute_rx_trend(10.0, 0.0) == 0.0

    def test_flat_trend(self):
        assert compute_rx_trend(20.0, 20.0) == pytest.approx(0.0)


class TestCompetitorShare:
    def test_normal_share(self):
        assert compute_competitor_share(10.0, 40.0) == pytest.approx(0.2, rel=1e-3)

    def test_zero_total(self):
        assert compute_competitor_share(0.0, 0.0) == 0.0

    def test_share_capped_at_one(self):
        # All competitor, zero brand
        assert compute_competitor_share(20.0, 0.0) == pytest.approx(1.0)


class TestPriorityTier:
    def test_high_by_trend(self):
        assert assign_priority_tier(rx_trend_pct=20.0, rx_q1=5.0, percentile_threshold=100.0) == "HIGH"

    def test_high_by_percentile(self):
        assert assign_priority_tier(rx_trend_pct=5.0, rx_q1=80.0, percentile_threshold=50.0) == "HIGH"

    def test_low_by_trend(self):
        assert assign_priority_tier(rx_trend_pct=-15.0, rx_q1=5.0, percentile_threshold=100.0) == "LOW"

    def test_medium(self):
        assert assign_priority_tier(rx_trend_pct=5.0, rx_q1=30.0, percentile_threshold=50.0) == "MEDIUM"

    def test_boundary_high_trend(self):
        # Exactly 15% is not strictly >15, so should be MEDIUM
        assert assign_priority_tier(rx_trend_pct=15.0, rx_q1=5.0, percentile_threshold=100.0) == "MEDIUM"


class TestWeeklyTarget:
    def test_compute_weekly_target(self):
        ranked = [{"priority_tier": "HIGH"}] * 10 + [{"priority_tier": "MEDIUM"}] * 5
        assert compute_weekly_target(ranked) == 7   # ceil(10 * 0.65)

    def test_zero_high(self):
        ranked = [{"priority_tier": "MEDIUM"}] * 10
        assert compute_weekly_target(ranked) == 0

    def test_single_high(self):
        ranked = [{"priority_tier": "HIGH"}]
        assert compute_weekly_target(ranked) == 1   # ceil(1 * 0.65) = 1


class TestRankHcps:
    def test_ordering(self, sample_hcp_features):
        ranked = rank_hcps(sample_hcp_features)
        tiers = [h["priority_tier"] for h in ranked]
        # HIGH should come before MEDIUM/LOW
        high_indices = [i for i, t in enumerate(tiers) if t == "HIGH"]
        medium_indices = [i for i, t in enumerate(tiers) if t == "MEDIUM"]
        low_indices = [i for i, t in enumerate(tiers) if t == "LOW"]
        if high_indices and (medium_indices or low_indices):
            assert max(high_indices) < min(medium_indices + low_indices)

    def test_all_hcps_get_tier(self, sample_hcp_features):
        ranked = rank_hcps(sample_hcp_features)
        assert all("priority_tier" in h for h in ranked)
        assert all(h["priority_tier"] in ("HIGH", "MEDIUM", "LOW") for h in ranked)


class TestTerritorySummary:
    def test_summary_counts(self, sample_hcp_features):
        ranked = rank_hcps(sample_hcp_features)
        summary = build_territory_summary(ranked, "TERR-001", "Test Territory", "Q1 2025")
        assert summary["total_hcps"] == 3
        assert summary["high_priority_count"] + summary["medium_priority_count"] + summary["low_priority_count"] == 3


class TestQuarterCalc:
    def test_q2_gives_q1_prior(self):
        (yr1, q1), (yr4, q4) = get_current_and_prior_quarter(date(2025, 4, 15))
        assert (yr1, q1) == (2025, 2)
        assert (yr4, q4) == (2025, 1)

    def test_q1_wraps_to_prior_year(self):
        (yr1, q1), (yr4, q4) = get_current_and_prior_quarter(date(2025, 2, 1))
        assert (yr1, q1) == (2025, 1)
        assert (yr4, q4) == (2024, 4)
