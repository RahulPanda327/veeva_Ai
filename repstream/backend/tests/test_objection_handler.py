"""Unit tests for Module 3 — Objection Handler service layer."""
import pytest
from unittest.mock import MagicMock, patch

from app.services.objection_handler.nlp_analysis import detect_objection_types, extract_objection_frequencies
from app.services.objection_handler.objection_classifier import (
    assign_frequency_label,
    classify_objections,
    compute_success_rate,
)


class TestObjectionTypeDetection:
    def test_coverage_detected(self):
        text = "The patient's insurance doesn't cover it — prior auth required."
        result = detect_objection_types(text)
        assert "COVERAGE" in result

    def test_cost_detected(self):
        text = "It's too expensive and the copay is too high."
        result = detect_objection_types(text)
        assert "COST" in result

    def test_competitor_detected(self):
        text = "I'm happy with Creon and don't want to switch."
        result = detect_objection_types(text)
        assert "COMPETITOR" in result
        assert "HABIT" in result

    def test_no_match(self):
        text = "Patient is doing well. Follow up in 3 months."
        result = detect_objection_types(text)
        assert result == []

    def test_multiple_categories(self):
        text = "Insurance won't cover it and it's too expensive anyway."
        result = detect_objection_types(text)
        assert "COVERAGE" in result
        assert "COST" in result


class TestFrequencyLabel:
    def test_high(self):
        assert assign_frequency_label(9) == "HIGH"
        assert assign_frequency_label(15) == "HIGH"

    def test_medium(self):
        assert assign_frequency_label(3) == "MEDIUM"
        assert assign_frequency_label(8) == "MEDIUM"

    def test_low(self):
        assert assign_frequency_label(0) == "LOW"
        assert assign_frequency_label(2) == "LOW"

    def test_boundary_high(self):
        # Must be strictly > 8 for HIGH
        assert assign_frequency_label(8) == "MEDIUM"
        assert assign_frequency_label(9) == "HIGH"


class TestSuccessRate:
    def test_normal(self):
        assert compute_success_rate(5, 10) == pytest.approx(0.5)

    def test_zero_calls(self):
        assert compute_success_rate(0, 0) == 0.0

    def test_full_conversion(self):
        assert compute_success_rate(10, 10) == pytest.approx(1.0)


class TestClassifyObjections:
    def test_sorted_by_count(self):
        frequency_data = {
            "COVERAGE": {"call_count": 12, "calls_with_resolution": 5, "calls_with_rx_30d": 4},
            "COST": {"call_count": 5, "calls_with_resolution": 2, "calls_with_rx_30d": 1},
            "HABIT": {"call_count": 2, "calls_with_resolution": 0, "calls_with_rx_30d": 0},
        }
        result = classify_objections(frequency_data, "Q1 2025", "TERR-001")
        assert result[0]["objection_type"] == "COVERAGE"
        assert result[0]["frequency"] == "HIGH"
        assert result[1]["objection_type"] == "COST"
        assert result[1]["frequency"] == "MEDIUM"
        assert result[2]["frequency"] == "LOW"

    def test_success_rate_computed(self):
        frequency_data = {
            "COVERAGE": {"call_count": 10, "calls_with_resolution": 3, "calls_with_rx_30d": 4},
        }
        result = classify_objections(frequency_data, "Q1 2025", "TERR-001")
        assert result[0]["success_rate"] == pytest.approx(0.4)


class TestTranscriptIngestion:
    def test_load_transcripts_empty(self):
        from app.services.objection_handler.transcript_ingestion import load_transcripts

        db = MagicMock()
        db.scalars.return_value.all.return_value = []
        result = load_transcripts(db, "TERR-001", "2025-01-01", "2025-03-31")
        assert result == []


class TestMLRResponseEngine:
    def test_missing_objection_returns_none(self):
        from app.services.objection_handler.mlr_response_engine import get_best_mlr_response

        db = MagicMock()
        db.scalars.return_value.first.return_value = None
        result = get_best_mlr_response(db, "OBJ_NONEXISTENT")
        assert result is None

    def test_found_objection_returns_dict(self):
        from app.services.objection_handler.mlr_response_engine import get_best_mlr_response

        mock_row = MagicMock()
        mock_row.objection_id = "OBJ001"
        mock_row.objection_type = "COVERAGE"
        mock_row.objection_text = "Not covered"
        mock_row.recommended_response = "Try patient assistance program"
        mock_row.response_source = "MLR-v1"
        mock_row.sku = "ZPP-40MG"
        mock_row.success_rate = 0.62
        mock_row.hcp_segment = "A"

        db = MagicMock()
        db.scalars.return_value.first.return_value = mock_row
        result = get_best_mlr_response(db, "OBJ001")
        assert result["objection_id"] == "OBJ001"
        assert result["success_rate"] == pytest.approx(0.62)
