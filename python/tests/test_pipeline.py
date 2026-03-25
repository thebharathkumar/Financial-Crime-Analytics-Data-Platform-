"""
Unit tests for AMLPipeline and TransformationRules.
"""

from datetime import datetime, timezone

import pytest

from python.aml.data_quality import AMLDataQualityEngine
from python.aml.entity_resolution import EntityResolutionEngine
from python.aml.pipeline import AMLPipeline, PipelineStage, TransformationRules
from python.aml.risk_scoring import AMLRiskScoringEngine


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def pipeline() -> AMLPipeline:
    dq = AMLDataQualityEngine()
    er = EntityResolutionEngine()
    rs = AMLRiskScoringEngine()
    return AMLPipeline(dq, er, rs)


def _valid_raw(txn_id: str = "TXN-001") -> dict:
    return {
        "transaction_id": txn_id,
        "amount": 5000.0,
        "source_account": "ACC-SRC001",
        "destination_account": "ACC-DST001",
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "currency": "USD",
        "transaction_type": "WIRE",
    }


def _invalid_raw(txn_id: str = "TXN-BAD") -> dict:
    return {
        "transaction_id": txn_id,
        "amount": -999,            # negative — fails DQ
        "source_account": "ACC-SRC002",
        "destination_account": "ACC-DST002",
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "currency": "USD",
    }


# ---------------------------------------------------------------------------
# Full pipeline run
# ---------------------------------------------------------------------------

class TestPipelineRun:
    def test_valid_records_reach_output_stage(self, pipeline: AMLPipeline) -> None:
        records = [_valid_raw(f"TXN-{i:03d}") for i in range(3)]
        processed, _ = pipeline.run(records)
        output_count = sum(
            1 for pr in processed if pr.stage == PipelineStage.OUTPUT.value
        )
        assert output_count == 3

    def test_invalid_records_do_not_reach_output(self, pipeline: AMLPipeline) -> None:
        records = [_invalid_raw()]
        processed, _ = pipeline.run(records)
        assert processed[0].stage != PipelineStage.OUTPUT.value
        assert len(processed[0].errors) > 0

    def test_pipeline_stats_populated(self, pipeline: AMLPipeline) -> None:
        records = [_valid_raw()]
        _, stats = pipeline.run(records)
        assert stats["total_records"] == 1
        assert stats["ingested"] == 1
        assert stats["output"] == 1
        assert stats["duration_seconds"] is not None

    def test_mixed_batch_separates_valid_invalid(self, pipeline: AMLPipeline) -> None:
        records = [
            _valid_raw("GOOD-001"),
            _invalid_raw("BAD-001"),
            _valid_raw("GOOD-002"),
        ]
        processed, stats = pipeline.run(records)
        output_records = [
            pr for pr in processed if pr.stage == PipelineStage.OUTPUT.value
        ]
        assert len(output_records) == 2
        assert stats["validation_failed"] == 1

    def test_risk_score_assigned_to_valid_records(self, pipeline: AMLPipeline) -> None:
        records = [_valid_raw()]
        processed, _ = pipeline.run(records)
        valid = [pr for pr in processed if pr.is_valid]
        for pr in valid:
            assert pr.risk_score is not None
            assert pr.risk_level is not None

    def test_empty_batch_returns_empty_result(self, pipeline: AMLPipeline) -> None:
        processed, stats = pipeline.run([])
        assert len(processed) == 0
        assert stats["total_records"] == 0


# ---------------------------------------------------------------------------
# TransformationRules
# ---------------------------------------------------------------------------

class TestTransformationRules:
    def test_normalize_remaps_aliases(self) -> None:
        raw = {
            "txn_id": "ABC-123",
            "amt": 9999.99,
            "ccy": "eur",
            "src_account": "SRC-001",
            "dst_account": "DST-001",
        }
        result = TransformationRules.normalize_transaction(raw)
        assert result["transaction_id"] == "ABC-123"
        assert result["amount"] == 9999.99
        assert result["currency"] == "EUR"
        assert result["source_account"] == "SRC-001"
        assert result["destination_account"] == "DST-001"

    def test_normalize_uppercases_currency(self) -> None:
        raw = _valid_raw()
        raw["currency"] = "gbp"
        result = TransformationRules.normalize_transaction(raw)
        assert result["currency"] == "GBP"

    def test_normalize_generates_id_if_missing(self) -> None:
        raw = {
            "amount": 100,
            "source_account": "ACC-A",
            "destination_account": "ACC-B",
            "currency": "USD",
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        }
        result = TransformationRules.normalize_transaction(raw)
        assert "transaction_id" in result
        assert len(result["transaction_id"]) > 0

    def test_business_rules_flags_high_value(self) -> None:
        record = {"amount": 15000.0}
        flagged = TransformationRules.apply_business_rules(record)
        assert flagged["flag_high_value"] is True

    def test_business_rules_flags_structuring(self) -> None:
        record = {"amount": 9500.0}
        flagged = TransformationRules.apply_business_rules(record)
        assert flagged["flag_structuring_indicator"] is True
        assert flagged["flag_high_value"] is False

    def test_business_rules_flags_round_amount(self) -> None:
        record = {"amount": 5000.0}
        flagged = TransformationRules.apply_business_rules(record)
        assert flagged["flag_round_amount"] is True

    def test_business_rules_flags_cross_border(self) -> None:
        record = {
            "amount": 500.0,
            "source_country": "US",
            "destination_country": "DE",
        }
        flagged = TransformationRules.apply_business_rules(record)
        assert flagged["flag_cross_border"] is True

    def test_business_rules_flags_high_risk_country(self) -> None:
        record = {
            "amount": 500.0,
            "source_country": "IR",    # Iran
            "destination_country": "US",
        }
        flagged = TransformationRules.apply_business_rules(record)
        assert flagged["flag_high_risk_country"] is True

    def test_enrich_with_entity_adds_context(self) -> None:
        record = {"transaction_id": "TXN-001", "amount": 100}
        entity = {
            "entity_id": "ENT-001",
            "name": "Test Corp",
            "pep_flag": True,
            "risk_score": 55.0,
            "country_code": "SG",
            "customer_type": "corporate",
        }
        enriched = TransformationRules.enrich_with_entity(record, entity)
        assert "entity_context" in enriched
        assert enriched["entity_context"]["pep_flag"] is True
        assert enriched["entity_context"]["entity_id"] == "ENT-001"
