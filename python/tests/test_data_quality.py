"""
Unit tests for AMLDataQualityEngine.
"""

from datetime import datetime, timedelta, timezone

import pytest

from python.aml.data_quality import (
    AMLDataQualityEngine,
    DataQualityReport,
    ValidationRule,
)


@pytest.fixture
def engine() -> AMLDataQualityEngine:
    return AMLDataQualityEngine()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _valid_record(**overrides) -> dict:
    base = {
        "transaction_id": "TXN-001",
        "amount": 1500.00,
        "source_account": "ACC-SRC001",
        "destination_account": "ACC-DST001",
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "currency": "USD",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# validate_record — passing cases
# ---------------------------------------------------------------------------

class TestValidRecordPasses:
    def test_valid_record_no_errors(self, engine: AMLDataQualityEngine) -> None:
        report = engine.validate_record(_valid_record())
        assert report.failed_rules == 0

    def test_valid_record_quality_score_100(self, engine: AMLDataQualityEngine) -> None:
        report = engine.validate_record(_valid_record())
        assert report.quality_score == 100.0

    def test_record_id_set(self, engine: AMLDataQualityEngine) -> None:
        report = engine.validate_record(_valid_record())
        assert report.record_id == "TXN-001"

    def test_total_rules_matches_registered(self, engine: AMLDataQualityEngine) -> None:
        report = engine.validate_record(_valid_record())
        assert report.total_rules == len(engine._rules)


# ---------------------------------------------------------------------------
# validate_record — failing cases
# ---------------------------------------------------------------------------

class TestRequiredFieldValidation:
    def test_missing_transaction_id_fails(self, engine: AMLDataQualityEngine) -> None:
        record = _valid_record()
        del record["transaction_id"]
        report = engine.validate_record(record)
        failed_ids = [r.rule_id for r in report.results if not r.passed]
        assert "DQ-001" in failed_ids

    def test_missing_amount_fails(self, engine: AMLDataQualityEngine) -> None:
        record = _valid_record()
        del record["amount"]
        report = engine.validate_record(record)
        failed_ids = [r.rule_id for r in report.results if not r.passed]
        assert "DQ-002" in failed_ids

    def test_missing_source_account_fails(self, engine: AMLDataQualityEngine) -> None:
        record = _valid_record()
        del record["source_account"]
        report = engine.validate_record(record)
        failed_ids = [r.rule_id for r in report.results if not r.passed]
        assert "DQ-003" in failed_ids

    def test_missing_destination_account_fails(self, engine: AMLDataQualityEngine) -> None:
        record = _valid_record()
        del record["destination_account"]
        report = engine.validate_record(record)
        failed_ids = [r.rule_id for r in report.results if not r.passed]
        assert "DQ-004" in failed_ids


class TestAmountValidation:
    def test_negative_amount_fails(self, engine: AMLDataQualityEngine) -> None:
        record = _valid_record(amount=-100.00)
        report = engine.validate_record(record)
        failed_ids = [r.rule_id for r in report.results if not r.passed]
        assert "DQ-006" in failed_ids

    def test_zero_amount_fails(self, engine: AMLDataQualityEngine) -> None:
        record = _valid_record(amount=0)
        report = engine.validate_record(record)
        failed_ids = [r.rule_id for r in report.results if not r.passed]
        assert "DQ-006" in failed_ids

    def test_over_limit_triggers_warning(self, engine: AMLDataQualityEngine) -> None:
        record = _valid_record(amount=15_000_000)
        report = engine.validate_record(record)
        failed_ids = [r.rule_id for r in report.results if not r.passed]
        assert "DQ-009" in failed_ids


class TestCurrencyValidation:
    def test_invalid_currency_fails(self, engine: AMLDataQualityEngine) -> None:
        record = _valid_record(currency="XYZ")
        report = engine.validate_record(record)
        failed_ids = [r.rule_id for r in report.results if not r.passed]
        assert "DQ-007" in failed_ids

    def test_valid_currency_passes(self, engine: AMLDataQualityEngine) -> None:
        for ccy in ("EUR", "GBP", "JPY"):
            record = _valid_record(currency=ccy)
            report = engine.validate_record(record)
            passed_ids = [r.rule_id for r in report.results if r.passed]
            assert "DQ-007" in passed_ids


class TestTimestampValidation:
    def test_future_timestamp_fails(self, engine: AMLDataQualityEngine) -> None:
        future = (datetime.now(tz=timezone.utc) + timedelta(days=30)).isoformat()
        record = _valid_record(timestamp=future)
        report = engine.validate_record(record)
        failed_ids = [r.rule_id for r in report.results if not r.passed]
        assert "DQ-008" in failed_ids

    def test_past_timestamp_passes(self, engine: AMLDataQualityEngine) -> None:
        past = (datetime.now(tz=timezone.utc) - timedelta(days=1)).isoformat()
        record = _valid_record(timestamp=past)
        report = engine.validate_record(record)
        passed_ids = [r.rule_id for r in report.results if r.passed]
        assert "DQ-008" in passed_ids


# ---------------------------------------------------------------------------
# validate_batch
# ---------------------------------------------------------------------------

class TestValidateBatch:
    def test_batch_returns_one_report_per_record(self, engine: AMLDataQualityEngine) -> None:
        records = [_valid_record(transaction_id=f"TXN-{i:03d}") for i in range(5)]
        reports = engine.validate_batch(records)
        assert len(reports) == 5

    def test_batch_reports_correct_record_ids(self, engine: AMLDataQualityEngine) -> None:
        records = [_valid_record(transaction_id=f"TXN-{i:03d}") for i in range(3)]
        reports = engine.validate_batch(records)
        report_ids = {r.record_id for r in reports}
        assert report_ids == {"TXN-000", "TXN-001", "TXN-002"}


# ---------------------------------------------------------------------------
# get_quality_summary
# ---------------------------------------------------------------------------

class TestQualitySummary:
    def test_all_passing_pass_rate_one(self, engine: AMLDataQualityEngine) -> None:
        records = [_valid_record(transaction_id=f"T{i}") for i in range(4)]
        reports = engine.validate_batch(records)
        summary = AMLDataQualityEngine.get_quality_summary(reports)
        assert summary["pass_rate"] == 1.0

    def test_summary_contains_required_keys(self, engine: AMLDataQualityEngine) -> None:
        reports = engine.validate_batch([_valid_record()])
        summary = AMLDataQualityEngine.get_quality_summary(reports)
        for key in ("total_records", "pass_rate", "avg_quality_score", "common_failures"):
            assert key in summary

    def test_empty_reports_returns_zero_pass_rate(self) -> None:
        summary = AMLDataQualityEngine.get_quality_summary([])
        assert summary["total_records"] == 0
        assert summary["pass_rate"] == 0.0

    def test_common_failures_listed_for_bad_records(
        self, engine: AMLDataQualityEngine
    ) -> None:
        # All records missing transaction_id → DQ-001 should appear in common_failures
        bad_records = [{"amount": 100, "source_account": "ACC-A",
                        "destination_account": "ACC-B",
                        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
                        "currency": "USD"} for _ in range(3)]
        reports = engine.validate_batch(bad_records)
        summary = AMLDataQualityEngine.get_quality_summary(reports)
        assert "DQ-001" in summary["common_failures"]


# ---------------------------------------------------------------------------
# add_rule (custom rule)
# ---------------------------------------------------------------------------

class TestCustomRule:
    def test_custom_rule_applied(self, engine: AMLDataQualityEngine) -> None:
        rule = ValidationRule(
            rule_id="CUSTOM-001",
            name="no_test_accounts",
            description="Account IDs must not start with 'TEST'.",
            severity="ERROR",
            field_path="source_account",
        )
        engine.add_rule(
            rule,
            lambda rec: not str(rec.get("source_account", "")).startswith("TEST"),
        )
        good = _valid_record(source_account="ACC-REAL")
        bad = _valid_record(source_account="TESTACCOUNT")

        good_report = engine.validate_record(good)
        bad_report = engine.validate_record(bad)

        good_passed = next(r for r in good_report.results if r.rule_id == "CUSTOM-001")
        bad_failed = next(r for r in bad_report.results if r.rule_id == "CUSTOM-001")
        assert good_passed.passed is True
        assert bad_failed.passed is False
