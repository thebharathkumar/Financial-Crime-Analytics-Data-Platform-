"""
AML Data Quality Validation Engine.

Provides a configurable rules-based framework for validating transaction
records and other AML data against regulatory and business-quality standards.
Each rule is independent, enabling partial validation and severity-based
triage of data issues.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional


class Severity(str):
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


# ISO 4217 subset of commonly used currency codes
_VALID_CURRENCIES = frozenset(
    {
        "USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD", "CNY", "HKD",
        "SGD", "SEK", "NOK", "DKK", "MXN", "BRL", "INR", "KRW", "ZAR", "RUB",
        "TRY", "SAR", "AED", "THB", "IDR", "MYR", "PHP", "PLN", "CZK", "HUF",
        "ILS", "CLP", "COP", "PEN", "VND", "NGN", "EGP", "PKR", "BDT", "QAR",
        "KWD", "OMR", "BHD", "JOD", "LBP", "MAD", "TND", "GHS", "KES", "TZS",
    }
)

# Sanity upper limit per single transaction (10 million USD equivalent)
_MAX_TRANSACTION_AMOUNT = 10_000_000.0

# Basic account number pattern: alphanumeric, 6–34 characters
_ACCOUNT_FORMAT_PATTERN = re.compile(r"^[A-Za-z0-9\-]{6,34}$")


@dataclass
class ValidationRule:
    """Describes a single data quality rule."""

    rule_id: str
    name: str
    description: str
    severity: str        # "ERROR" | "WARNING" | "INFO"
    field_path: str      # dot-separated path to the validated field


@dataclass
class ValidationResult:
    """Outcome of applying one ValidationRule to a record."""

    rule_id: str
    passed: bool
    message: str
    field_path: str
    value: Any = None


@dataclass
class DataQualityReport:
    """Aggregated validation results for a single record."""

    record_id: str
    total_rules: int
    passed_rules: int
    failed_rules: int
    results: List[ValidationResult] = field(default_factory=list)
    quality_score: float = 0.0   # 0-100 based on weighted pass rate

    def __post_init__(self) -> None:
        if self.total_rules > 0:
            self.quality_score = round(100 * self.passed_rules / self.total_rules, 2)


class AMLDataQualityEngine:
    """
    Validates transaction and entity records against AML data quality rules.

    Rules are split into two tiers:
    1. Built-in rules (hard-coded, always active).
    2. Custom rules registered via ``add_rule``.

    Each rule is paired with a validator callable: ``(record: dict) -> bool``.
    """

    def __init__(self) -> None:
        self._rules: List[ValidationRule] = []
        self._validators: Dict[str, Callable[[Dict[str, Any]], bool]] = {}
        self._register_builtin_rules()

    # ------------------------------------------------------------------
    # Rule registration
    # ------------------------------------------------------------------

    def _register_builtin_rules(self) -> None:
        """Register the standard AML transaction validation rules."""

        def _not_null(field_key: str) -> Callable[[Dict[str, Any]], bool]:
            return lambda rec: rec.get(field_key) is not None and str(rec.get(field_key, "")).strip() != ""

        # Required field presence rules
        required_fields = [
            ("transaction_id", "Transaction ID"),
            ("amount", "Transaction Amount"),
            ("source_account", "Source Account"),
            ("destination_account", "Destination Account"),
            ("timestamp", "Transaction Timestamp"),
        ]
        for idx, (fld, label) in enumerate(required_fields, start=1):
            rule = ValidationRule(
                rule_id=f"DQ-{idx:03d}",
                name=f"not_null_{fld}",
                description=f"{label} must not be null or empty.",
                severity=Severity.ERROR,
                field_path=fld,
            )
            self.add_rule(rule, _not_null(fld))

        # Positive amount
        self.add_rule(
            ValidationRule(
                rule_id="DQ-006",
                name="positive_amount",
                description="Transaction amount must be greater than zero.",
                severity=Severity.ERROR,
                field_path="amount",
            ),
            lambda rec: (
                rec.get("amount") is not None
                and float(rec["amount"]) > 0
            ),
        )

        # Valid currency (ISO 4217)
        self.add_rule(
            ValidationRule(
                rule_id="DQ-007",
                name="valid_currency",
                description="Currency must be a recognised ISO 4217 code.",
                severity=Severity.ERROR,
                field_path="currency",
            ),
            lambda rec: str(rec.get("currency", "")).upper() in _VALID_CURRENCIES,
        )

        # Timestamp not in the future
        self.add_rule(
            ValidationRule(
                rule_id="DQ-008",
                name="timestamp_not_future",
                description="Transaction timestamp must not be in the future.",
                severity=Severity.ERROR,
                field_path="timestamp",
            ),
            self._validate_timestamp_not_future,
        )

        # Amount within sanity limit
        self.add_rule(
            ValidationRule(
                rule_id="DQ-009",
                name="amount_within_limits",
                description=f"Amount must not exceed {_MAX_TRANSACTION_AMOUNT:,.0f}.",
                severity=Severity.WARNING,
                field_path="amount",
            ),
            lambda rec: (
                rec.get("amount") is not None
                and float(rec["amount"]) <= _MAX_TRANSACTION_AMOUNT
            ),
        )

        # Account number format
        self.add_rule(
            ValidationRule(
                rule_id="DQ-010",
                name="account_format_valid",
                description="Source and destination accounts must match expected format.",
                severity=Severity.WARNING,
                field_path="source_account",
            ),
            self._validate_account_format,
        )

    @staticmethod
    def _validate_timestamp_not_future(record: Dict[str, Any]) -> bool:
        ts = record.get("timestamp")
        if ts is None:
            return False
        try:
            if isinstance(ts, (int, float)):
                dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            elif isinstance(ts, datetime):
                dt = ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
            else:
                # Try parsing ISO 8601 string
                ts_str = str(ts).replace("Z", "+00:00")
                dt = datetime.fromisoformat(ts_str)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
            return dt <= datetime.now(tz=timezone.utc)
        except (ValueError, OSError, OverflowError):
            return False

    @staticmethod
    def _validate_account_format(record: Dict[str, Any]) -> bool:
        for key in ("source_account", "destination_account"):
            val = record.get(key, "")
            if val and not _ACCOUNT_FORMAT_PATTERN.match(str(val)):
                return False
        return True

    def add_rule(
        self,
        rule: ValidationRule,
        validator_fn: Callable[[Dict[str, Any]], bool],
    ) -> None:
        """
        Register a custom validation rule.

        Args:
            rule:         ValidationRule metadata.
            validator_fn: Callable that returns True if the record passes.
        """
        self._rules.append(rule)
        self._validators[rule.rule_id] = validator_fn

    # ------------------------------------------------------------------
    # Validation methods
    # ------------------------------------------------------------------

    def validate_record(self, record: Dict[str, Any]) -> DataQualityReport:
        """
        Apply all registered rules to a single record.

        Args:
            record: Dictionary representing a transaction or entity record.

        Returns:
            DataQualityReport with per-rule results and an overall quality score.
        """
        record_id = str(record.get("transaction_id", record.get("id", "unknown")))
        results: List[ValidationResult] = []

        for rule in self._rules:
            validator = self._validators.get(rule.rule_id)
            if validator is None:
                continue
            try:
                passed = bool(validator(record))
            except Exception as exc:  # noqa: BLE001
                passed = False
                results.append(
                    ValidationResult(
                        rule_id=rule.rule_id,
                        passed=False,
                        message=f"Validator raised exception: {exc}",
                        field_path=rule.field_path,
                        value=record.get(rule.field_path),
                    )
                )
                continue

            message = "OK" if passed else f"Failed: {rule.description}"
            results.append(
                ValidationResult(
                    rule_id=rule.rule_id,
                    passed=passed,
                    message=message,
                    field_path=rule.field_path,
                    value=record.get(rule.field_path),
                )
            )

        passed_count = sum(1 for r in results if r.passed)
        return DataQualityReport(
            record_id=record_id,
            total_rules=len(results),
            passed_rules=passed_count,
            failed_rules=len(results) - passed_count,
            results=results,
        )

    def validate_batch(
        self, records: List[Dict[str, Any]]
    ) -> List[DataQualityReport]:
        """
        Validate a list of records.

        Args:
            records: List of record dictionaries.

        Returns:
            List of DataQualityReport, one per record, in the same order.
        """
        return [self.validate_record(rec) for rec in records]

    @staticmethod
    def get_quality_summary(
        reports: List[DataQualityReport],
    ) -> Dict[str, Any]:
        """
        Aggregate quality metrics across a batch of reports.

        Args:
            reports: List of DataQualityReport from a batch validation run.

        Returns:
            Dictionary with:
            - total_records (int)
            - pass_rate (float): fraction of records with no ERROR failures
            - avg_quality_score (float): mean quality_score across records
            - common_failures (List[str]): rule names that failed most often
        """
        if not reports:
            return {
                "total_records": 0,
                "pass_rate": 0.0,
                "avg_quality_score": 0.0,
                "common_failures": [],
            }

        failure_counts: Dict[str, int] = {}
        error_free_count = 0

        for report in reports:
            has_error = False
            for result in report.results:
                if not result.passed:
                    failure_counts[result.rule_id] = (
                        failure_counts.get(result.rule_id, 0) + 1
                    )
                    has_error = True
            if not has_error:
                error_free_count += 1

        sorted_failures = sorted(
            failure_counts.items(), key=lambda x: x[1], reverse=True
        )
        common_failures = [rule_id for rule_id, _ in sorted_failures[:5]]

        avg_quality = sum(r.quality_score for r in reports) / len(reports)

        return {
            "total_records": len(reports),
            "pass_rate": round(error_free_count / len(reports), 4),
            "avg_quality_score": round(avg_quality, 2),
            "common_failures": common_failures,
        }
