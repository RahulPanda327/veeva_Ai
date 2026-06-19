"""Shared pytest fixtures for RepStream backend tests."""
import pytest
from datetime import date
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.utils.auth import RepIdentity, create_access_token


@pytest.fixture
def test_client():
    return TestClient(app)


@pytest.fixture
def rep_identity():
    return RepIdentity(
        rep_id="REP001",
        territory_id="TERR-001",
        email="rep@example.com",
        full_name="Test Rep",
        role="rep",
    )


@pytest.fixture
def auth_headers(rep_identity):
    token = create_access_token(
        {
            "sub": rep_identity.rep_id,
            "territory_id": rep_identity.territory_id,
            "email": rep_identity.email,
        }
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def sample_hcp_features():
    return [
        {
            "hcp_id": "HCP001",
            "name": "Dr. Jane Smith",
            "specialty": "Gastroenterology",
            "territory_id": "TERR-001",
            "segment": "A",
            "city": "Boston",
            "state": "MA",
            "rx_q1": 45.0,
            "rx_q4": 30.0,
            "rx_trend_pct": 50.0,
            "competitor_rx": 10.0,
            "competitor_brand": "Creon",
            "competitor_brand_share": 0.18,
            "last_call_date": date(2025, 3, 15),
        },
        {
            "hcp_id": "HCP002",
            "name": "Dr. Bob Jones",
            "specialty": "Internal Medicine",
            "territory_id": "TERR-001",
            "segment": "B",
            "city": "Cambridge",
            "state": "MA",
            "rx_q1": 8.0,
            "rx_q4": 12.0,
            "rx_trend_pct": -33.3,
            "competitor_rx": 5.0,
            "competitor_brand": "Pancreaze",
            "competitor_brand_share": 0.38,
            "last_call_date": date(2025, 2, 1),
        },
        {
            "hcp_id": "HCP003",
            "name": "Dr. Alice Chen",
            "specialty": "Gastroenterology",
            "territory_id": "TERR-001",
            "segment": "A",
            "city": "Brookline",
            "state": "MA",
            "rx_q1": 20.0,
            "rx_q4": 18.0,
            "rx_trend_pct": 11.1,
            "competitor_rx": 3.0,
            "competitor_brand": "Creon",
            "competitor_brand_share": 0.13,
            "last_call_date": None,
        },
    ]
