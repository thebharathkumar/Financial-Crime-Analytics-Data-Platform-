"""
AML Data Pipeline Orchestration.

Coordinates the end-to-end flow of transaction records through ingestion,
validation, transformation, enrichment, risk scoring, and output stages.
Designed to be embedded in both batch and micro-batch processing contexts.
"""

from __future__ import annotations

import copy
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from .data_quality import AMLDataQualityEngine
from .entity_resolution import Entity, EntityResolutionEngine
from .risk_scoring import AMLRiskScoringEngine, RiskScore


class PipelineStage(str, Enum):
    INGESTION = "INGESTION"
    VALIDATION = "VALIDATION"
    TRANSFORMATION = "TRANSFORMATION"
    ENRICHMENT = "ENRICHMENT"
    SCORING = "SCORING"
    OUTPUT = "OUTPUT"


@dataclass
class PipelineRecord:
    """Tracks a single record as it moves through pipeline stages."""

    record_id: str
    raw_data: Dict[str, Any]
    transformed_data: Dict[str, Any] = field(default_factory=dict)
    stage: str = PipelineStage.INGESTION.value
    errors: List[str] = field(default_factory=list)
    quality_score: float = 0.0
    risk_score: Optional[float] = None
    risk_level: Optional[str] = None

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0


class TransformationRules:
    """Static transformation methods applied during the TRANSFORMATION stage."""

    # Map of raw field aliases → canonical field names
    _FIELD_ALIASES: Dict[str, str] = {
        "txn_id": "transaction_id",
        "tx_id": "transaction_id",
        "src_account": "source_account",
        "src_acct": "source_account",
        "dst_account": "destination_account",
        "dest_account": "destination_account",
        "dst_acct": "destination_account",
        "amt": "amount",
        "ccy": "currency",
        "ts": "timestamp",
        "transaction_time": "timestamp",
        "txn_type": "transaction_type",
        "type": "transaction_type",
    }

    # High-risk country codes (ISO 3166-1 alpha-2)
    _HIGH_RISK_COUNTRIES = frozenset(
        {
            "AF", "BY", "CF", "CD", "CG", "GN", "HT", "IR", "IQ", "KP",
            "LY", "ML", "MM", "NI", "PK", "PA", "RU", "SO", "SS", "SY",
            "VE", "YE", "ZW",
        }
    )

    @classmethod
    def normalize_transaction(cls, raw: Dict[str, Any]) -> Dict[str, Any]:
        """
        Produce a clean, canonical transaction dictionary from a raw record.

        Steps:
        - Remap aliased field names to canonical names.
        - Parse amount to float.
        - Uppercase currency code.
        - Strip whitespace from string fields.
        - Assign a transaction_id if missing.

        Args:
            raw: Raw transaction dictionary from the source system.

        Returns:
            Normalised dictionary.
        """
        record: Dict[str, Any] = {}
        # Remap aliases first
        for src_key, value in raw.items():
            canonical = cls._FIELD_ALIASES.get(src_key, src_key)
            record[canonical] = value

        # Strip strings
        for key, val in record.items():
            if isinstance(val, str):
                record[key] = val.strip()

        # Ensure transaction_id
        if not record.get("transaction_id"):
            record["transaction_id"] = str(uuid.uuid4())

        # Parse amount
        if record.get("amount") is not None:
            try:
                record["amount"] = float(record["amount"])
            except (TypeError, ValueError):
                record["amount"] = None

        # Normalise currency
        if record.get("currency"):
            record["currency"] = str(record["currency"]).strip().upper()

        # Ensure transaction_type has a default
        if not record.get("transaction_type"):
            record["transaction_type"] = "UNKNOWN"

        return record

    @staticmethod
    def enrich_with_entity(record: Dict[str, Any], entity_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge entity-level data into the transaction record.

        Entity attributes (e.g., pep_flag, risk_score, country_code) are
        added under an ``entity_context`` key to avoid collision with
        transaction-level fields.

        Args:
            record:      Normalised transaction record.
            entity_data: Entity dictionary from the resolution engine or data store.

        Returns:
            Enriched record with ``entity_context`` populated.
        """
        enriched = dict(record)
        enriched["entity_context"] = {
            "entity_id": entity_data.get("entity_id") or entity_data.get("id"),
            "entity_name": entity_data.get("name"),
            "pep_flag": entity_data.get("pep_flag", False),
            "entity_risk_score": entity_data.get("risk_score", 0.0),
            "country_code": entity_data.get("country_code"),
            "customer_type": entity_data.get("customer_type", "retail"),
        }
        return enriched

    @classmethod
    def apply_business_rules(cls, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Flag transaction records based on AML business rules.

        Rules applied:
        1. High-value flag: amount >= 10,000.
        2. Cross-border flag: source_country != destination_country.
        3. High-risk country flag: either party is in a sanctioned/high-risk country.
        4. Structuring indicator: amount is just below 10,000 (9,000–9,999.99).
        5. Round-amount indicator: amount is a round number (divisible by 1,000).

        Args:
            record: Normalised (and optionally enriched) transaction record.

        Returns:
            Record with boolean flag fields appended.
        """
        flagged = dict(record)
        amount = float(record.get("amount") or 0)

        flagged["flag_high_value"] = amount >= 10_000
        flagged["flag_structuring_indicator"] = 9_000 <= amount < 10_000
        flagged["flag_round_amount"] = amount > 0 and amount % 1_000 == 0

        src_country = str(record.get("source_country", "")).upper()
        dst_country = str(record.get("destination_country", "")).upper()
        flagged["flag_cross_border"] = bool(
            src_country and dst_country and src_country != dst_country
        )

        countries = {src_country, dst_country} - {""}
        flagged["flag_high_risk_country"] = bool(
            countries & cls._HIGH_RISK_COUNTRIES
        )

        return flagged


class AMLPipeline:
    """
    Orchestrates transaction records through the complete AML processing lifecycle.

    Stage sequence:
    INGESTION → VALIDATION → TRANSFORMATION → ENRICHMENT → SCORING → OUTPUT
    """

    def __init__(
        self,
        data_quality_engine: AMLDataQualityEngine,
        entity_engine: EntityResolutionEngine,
        scoring_engine: AMLRiskScoringEngine,
    ) -> None:
        self._dq_engine = data_quality_engine
        self._entity_engine = entity_engine
        self._scoring_engine = scoring_engine
        self._stats: Dict[str, Any] = self._reset_stats()

    @staticmethod
    def _reset_stats() -> Dict[str, Any]:
        return {
            "total_records": 0,
            "ingested": 0,
            "validated": 0,
            "validation_failed": 0,
            "transformed": 0,
            "enriched": 0,
            "scored": 0,
            "output": 0,
            "errors": [],
            "start_time": None,
            "end_time": None,
            "duration_seconds": None,
        }

    # ------------------------------------------------------------------
    # Stage methods
    # ------------------------------------------------------------------

    def _ingest(self, records: List[Dict[str, Any]]) -> List[PipelineRecord]:
        """Wrap raw dicts in PipelineRecord containers."""
        pipeline_records: List[PipelineRecord] = []
        for raw in records:
            rec_id = str(raw.get("transaction_id", raw.get("id", uuid.uuid4())))
            pr = PipelineRecord(record_id=rec_id, raw_data=copy.deepcopy(raw))
            pr.stage = PipelineStage.INGESTION.value
            pipeline_records.append(pr)
        self._stats["ingested"] = len(pipeline_records)
        return pipeline_records

    def _validate(self, records: List[PipelineRecord]) -> List[PipelineRecord]:
        """Run data quality checks; attach quality score and any error messages."""
        for pr in records:
            report = self._dq_engine.validate_record(pr.raw_data)
            pr.quality_score = report.quality_score
            pr.stage = PipelineStage.VALIDATION.value
            for result in report.results:
                if not result.passed:
                    # Only ERROR severity blocks progression
                    rule_severity = self._dq_engine._rules[
                        next(
                            i
                            for i, r in enumerate(self._dq_engine._rules)
                            if r.rule_id == result.rule_id
                        )
                    ].severity
                    if rule_severity == "ERROR":
                        pr.errors.append(
                            f"[{result.rule_id}] {result.message} (field={result.field_path})"
                        )
        self._stats["validated"] = sum(1 for r in records if r.is_valid)
        self._stats["validation_failed"] = sum(1 for r in records if not r.is_valid)
        return records

    def _transform(self, records: List[PipelineRecord]) -> List[PipelineRecord]:
        """Normalise and apply business rules to each valid record."""
        for pr in records:
            if not pr.is_valid:
                continue
            try:
                normalised = TransformationRules.normalize_transaction(pr.raw_data)
                flagged = TransformationRules.apply_business_rules(normalised)
                pr.transformed_data = flagged
                pr.stage = PipelineStage.TRANSFORMATION.value
                self._stats["transformed"] = self._stats.get("transformed", 0) + 1
            except Exception as exc:  # noqa: BLE001
                pr.errors.append(f"Transformation error: {exc}")
        return records

    def _enrich(self, records: List[PipelineRecord]) -> List[PipelineRecord]:
        """Attach entity context to each transformed record."""
        for pr in records:
            if not pr.is_valid or not pr.transformed_data:
                continue
            try:
                # Build a minimal entity dict from available fields
                entity_data: Dict[str, Any] = {
                    "entity_id": pr.transformed_data.get("source_account"),
                    "name": pr.transformed_data.get("source_account"),
                    "country_code": pr.transformed_data.get("source_country", ""),
                    "customer_type": pr.transformed_data.get("customer_type", "retail"),
                    "pep_flag": pr.raw_data.get("is_pep", False),
                    "risk_score": 0.0,
                }
                pr.transformed_data = TransformationRules.enrich_with_entity(
                    pr.transformed_data, entity_data
                )
                pr.stage = PipelineStage.ENRICHMENT.value
                self._stats["enriched"] = self._stats.get("enriched", 0) + 1
            except Exception as exc:  # noqa: BLE001
                pr.errors.append(f"Enrichment error: {exc}")
        return records

    def _score(self, records: List[PipelineRecord]) -> List[PipelineRecord]:
        """Compute risk scores for enriched records."""
        for pr in records:
            if not pr.is_valid or not pr.transformed_data:
                continue
            try:
                ctx = pr.transformed_data.get("entity_context", {})
                features: Dict[str, Any] = {
                    "transaction_amount": pr.transformed_data.get("amount", 0),
                    "velocity_30d": pr.raw_data.get("velocity_30d", 0),
                    "high_risk_country": pr.transformed_data.get("flag_high_risk_country", False),
                    "customer_type": ctx.get("customer_type", "retail"),
                    "is_pep": ctx.get("pep_flag", False),
                    "adverse_media_hits": pr.raw_data.get("adverse_media_hits", 0),
                    "centrality_score": pr.raw_data.get("centrality_score", 0.0),
                    "layering_flag": pr.raw_data.get("layering_flag", False),
                }
                entity_id = ctx.get("entity_id") or pr.record_id
                risk: RiskScore = self._scoring_engine.score_entity(entity_id, features)
                pr.risk_score = risk.weighted_score
                pr.risk_level = risk.risk_level
                pr.transformed_data["risk_score"] = risk.weighted_score
                pr.transformed_data["risk_level"] = risk.risk_level
                pr.stage = PipelineStage.SCORING.value
                self._stats["scored"] = self._stats.get("scored", 0) + 1
            except Exception as exc:  # noqa: BLE001
                pr.errors.append(f"Scoring error: {exc}")
        return records

    def _output(self, records: List[PipelineRecord]) -> List[PipelineRecord]:
        """Mark records as output-ready; in production this would write to sink."""
        for pr in records:
            if pr.is_valid:
                pr.stage = PipelineStage.OUTPUT.value
                self._stats["output"] = self._stats.get("output", 0) + 1
        return records

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run(
        self, records: List[Dict[str, Any]]
    ) -> Tuple[List[PipelineRecord], Dict[str, Any]]:
        """
        Execute the complete AML pipeline over a batch of raw transaction records.

        Args:
            records: List of raw transaction dictionaries.

        Returns:
            Tuple of (processed PipelineRecord list, pipeline statistics dict).
        """
        self._stats = self._reset_stats()
        self._stats["total_records"] = len(records)
        self._stats["start_time"] = time.time()

        pipeline_records = self._ingest(records)
        pipeline_records = self._validate(pipeline_records)
        pipeline_records = self._transform(pipeline_records)
        pipeline_records = self._enrich(pipeline_records)
        pipeline_records = self._score(pipeline_records)
        pipeline_records = self._output(pipeline_records)

        self._stats["end_time"] = time.time()
        self._stats["duration_seconds"] = round(
            self._stats["end_time"] - self._stats["start_time"], 4
        )

        return pipeline_records, self.get_pipeline_stats()

    def get_pipeline_stats(self) -> Dict[str, Any]:
        """
        Return a copy of the current pipeline execution statistics.

        Returns:
            Dictionary with counters for each stage and timing information.
        """
        return dict(self._stats)
