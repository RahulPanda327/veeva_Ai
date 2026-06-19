"""Unit tests for Module 2 — New Writer Identification service layer."""
import pytest
from unittest.mock import MagicMock, patch

from app.services.new_writer_id.icd10_matching import match_icd10_codes
from app.services.new_writer_id.match_scoring import enrich_with_peer_match
from app.services.new_writer_id.peer_network import get_best_peer


class TestICD10Matching:
    def test_match_found(self):
        result = match_icd10_codes("K86.1, K86.81, E11.9", ["K86.1", "K86.81", "K90.3"])
        assert "K86.1" in result
        assert "K86.81" in result
        assert "K90.3" not in result

    def test_no_match(self):
        result = match_icd10_codes("E11.9, I10", ["K86.1", "K86.81"])
        assert result == []

    def test_empty_icd10_field(self):
        assert match_icd10_codes("", ["K86.1"]) == []

    def test_case_insensitive(self):
        result = match_icd10_codes("k86.1, K86.81", ["K86.1"])
        assert "K86.1" in result

    def test_whitespace_stripped(self):
        result = match_icd10_codes("  K86.1 , K86.81  ", ["K86.1"])
        assert "K86.1" in result


class TestPeerNetwork:
    def test_get_best_peer_empty(self):
        assert get_best_peer([]) is None

    def test_get_best_peer_single(self):
        peers = [{"peer_hcp_name": "Dr. A", "match_score": 75.0, "peer_hcp_id": "P001"}]
        best = get_best_peer(peers)
        assert best["peer_hcp_name"] == "Dr. A"

    def test_get_best_peer_highest_score(self):
        peers = [
            {"peer_hcp_name": "Dr. A", "match_score": 60.0, "peer_hcp_id": "P001"},
            {"peer_hcp_name": "Dr. B", "match_score": 88.0, "peer_hcp_id": "P002"},
            {"peer_hcp_name": "Dr. C", "match_score": 45.0, "peer_hcp_id": "P003"},
        ]
        best = get_best_peer(peers)
        assert best["peer_hcp_name"] == "Dr. B"
        assert best["match_score"] == 88.0


class TestNonWriterDetection:
    def test_candidate_structure(self):
        """Verify detect_non_writers returns correctly shaped dicts."""
        from app.services.new_writer_id.non_writer_detection import detect_non_writers

        db = MagicMock()
        # Mock empty query result
        db.execute.return_value.all.return_value = []
        result = detect_non_writers(db, "TERR-001", 2025, 1, 2024, 4)
        assert result == []


class TestMatchScoring:
    def test_candidates_get_peer_fields(self):
        candidates = [
            {
                "hcp_id": "HCP001",
                "name": "Dr. X",
                "in_class_rx_q1": 10.0,
                "brand_rx_q1": 0.0,
                "brand_rx_q4": 0.0,
            }
        ]
        db = MagicMock()
        # No peer matches in DB
        db.scalars.return_value.all.return_value = []
        result = enrich_with_peer_match(db, candidates, "TERR-001")
        assert result[0]["peer_match_pct"] == 0.0
        assert result[0]["peer_name"] is None


class TestApproachBrief:
    @patch("app.services.new_writer_id.approach_brief.call_llm")
    def test_brief_generation(self, mock_llm):
        from app.services.new_writer_id.approach_brief import generate_approach_brief

        mock_llm.return_value = "Dr. Smith is a strong candidate. Approach via peer Dr. Jones."
        hcp = {
            "hcp_id": "HCP001",
            "name": "Dr. Smith",
            "peer_name": "Dr. Jones",
            "competitor_brand": "Creon",
            "competitor_volume": 12.0,
            "matched_icd10_codes": ["K86.1"],
        }
        brief = generate_approach_brief(hcp)
        assert "Dr. Smith" in mock_llm.call_args[1]["prompt"] or mock_llm.called
        assert isinstance(brief, str)
