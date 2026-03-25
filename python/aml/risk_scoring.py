"""
AML Risk Scoring Engine.

Computes weighted risk scores for financial entities based on a configurable
set of AML risk factors (transaction amounts, velocity, geography, PEP status,
adverse media, network centrality, and detected layering patterns).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class RiskFactor(str, Enum):
    """Enumeration of AML risk factors considered during entity scoring."""

    TRANSACTION_AMOUNT = "TRANSACTION_AMOUNT"
    VELOCITY = "VELOCITY"
    GEOGRAPHY = "GEOGRAPHY"
    CUSTOMER_TYPE = "CUSTOMER_TYPE"
    PEP_STATUS = "PEP_STATUS"
    ADVERSE_MEDIA = "ADVERSE_MEDIA"
    NETWORK_CENTRALITY = "NETWORK_CENTRALITY"
    LAYERING_DETECTED = "LAYERING_DETECTED"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class RiskWeight:
    """Associates a risk factor with its contribution weight (0-1)."""

    factor: RiskFactor
    weight: float

    def __post_init__(self) -> None:
        if not 0 <= self.weight <= 1:
            raise ValueError(f"weight must be in [0, 1], got {self.weight}")


@dataclass
class RiskScore:
    """Full risk assessment output for a single entity."""

    entity_id: str
    base_score: float                        # Raw, un-weighted score 0-100
    weighted_score: float                    # Final weighted score 0-100
    risk_level: str                          # LOW / MEDIUM / HIGH / CRITICAL
    contributing_factors: Dict[str, float]   # factor name -> partial score
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(tz=timezone.utc)
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "base_score": round(self.base_score, 2),
            "weighted_score": round(self.weighted_score, 2),
            "risk_level": self.risk_level,
            "contributing_factors": {k: round(v, 4) for k, v in self.contributing_factors.items()},
            "timestamp": self.timestamp.isoformat(),
        }


class AMLRiskScoringEngine:
    """
    Computes AML risk scores for entities using a weighted factor model.

    Default weights are calibrated to reflect FATF guidance and SMBC-style
    internal risk appetite policies.  All weights can be overridden at
    construction time.
    """

    DEFAULT_WEIGHTS: Dict[RiskFactor, float] = {
        RiskFactor.TRANSACTION_AMOUNT: 0.20,
        RiskFactor.VELOCITY: 0.15,
        RiskFactor.GEOGRAPHY: 0.15,
        RiskFactor.CUSTOMER_TYPE: 0.10,
        RiskFactor.PEP_STATUS: 0.15,
        RiskFactor.ADVERSE_MEDIA: 0.10,
        RiskFactor.NETWORK_CENTRALITY: 0.10,
        RiskFactor.LAYERING_DETECTED: 0.05,
    }

    # High-risk country codes (ISO 3166-1 alpha-2) per FATF grey/black list
    _HIGH_RISK_COUNTRIES = frozenset(
        {
            "AF", "BY", "CF", "CD", "CG", "GN", "HT", "IR", "IQ", "KP",
            "LY", "ML", "MM", "NI", "PK", "PA", "RU", "SO", "SS", "SY",
            "VE", "YE", "ZW",
        }
    )

    def __init__(self, weight_overrides: Optional[Dict[RiskFactor, float]] = None) -> None:
        """
        Initialise the scoring engine.

        Args:
            weight_overrides: Optional mapping of RiskFactor -> weight to
                              replace individual default weights.
        """
        self._weights: Dict[RiskFactor, float] = dict(self.DEFAULT_WEIGHTS)
        if weight_overrides:
            for factor, w in weight_overrides.items():
                if not 0 <= w <= 1:
                    raise ValueError(f"Weight for {factor} must be in [0, 1]")
                self._weights[factor] = w

    # ------------------------------------------------------------------
    # Internal scoring helpers
    # ------------------------------------------------------------------

    def _calculate_base_score(self, features: Dict[str, Any]) -> float:
        """
        Compute a raw 0-100 score from input feature values.

        Feature keys expected (all optional, default to safe/low-risk values):
        - transaction_amount (float): Single transaction amount in USD equivalent.
        - velocity_30d (int):         Number of transactions in last 30 days.
        - high_risk_country (bool|str): True / country_code if cross-border to
                                         high-risk jurisdiction.
        - customer_type (str):        "retail" | "corporate" | "correspondent".
        - is_pep (bool):              Politically Exposed Person flag.
        - adverse_media_hits (int):   Count of adverse media results.
        - centrality_score (float):   Network centrality 0-1.
        - layering_flag (bool):       Whether layering was detected.

        Args:
            features: Dictionary of feature values.

        Returns:
            Base score in [0, 100].
        """
        score = 0.0

        # Transaction amount component (max 100 raw points)
        amount: float = float(features.get("transaction_amount", 0))
        if amount >= 1_000_000:
            score += 100
        elif amount >= 100_000:
            score += 75
        elif amount >= 50_000:
            score += 55
        elif amount >= 10_000:
            score += 35
        elif amount >= 5_000:
            score += 15
        else:
            score += 5

        # Velocity (transactions in 30 days)
        velocity: int = int(features.get("velocity_30d", 0))
        if velocity >= 200:
            score += 100
        elif velocity >= 100:
            score += 70
        elif velocity >= 50:
            score += 45
        elif velocity >= 20:
            score += 25
        else:
            score += max(0, velocity * 0.5)

        # Geography
        high_risk_country = features.get("high_risk_country", False)
        if isinstance(high_risk_country, str):
            high_risk_country = high_risk_country.upper() in self._HIGH_RISK_COUNTRIES
        score += 100 if high_risk_country else 0

        # Customer type
        customer_type: str = str(features.get("customer_type", "retail")).lower()
        customer_type_score = {
            "correspondent": 80,
            "corporate": 40,
            "retail": 10,
        }.get(customer_type, 20)
        score += customer_type_score

        # PEP status (binary, maximum impact)
        score += 100 if features.get("is_pep", False) else 0

        # Adverse media hits
        adverse_hits: int = int(features.get("adverse_media_hits", 0))
        score += min(100, adverse_hits * 20)

        # Network centrality (0-1 → 0-100)
        centrality: float = float(features.get("centrality_score", 0.0))
        score += centrality * 100

        # Layering flag
        score += 100 if features.get("layering_flag", False) else 0

        # Average over 8 factors to keep in [0, 100]
        return min(100.0, score / 8.0)

    @staticmethod
    def _determine_risk_level(score: float) -> str:
        """
        Map a numeric score to a categorical risk level.

        Thresholds:
        - CRITICAL: >= 80
        - HIGH:     >= 60
        - MEDIUM:   >= 30
        - LOW:      < 30

        Args:
            score: Weighted score in [0, 100].

        Returns:
            Risk level string.
        """
        if score >= 80:
            return RiskLevel.CRITICAL.value
        if score >= 60:
            return RiskLevel.HIGH.value
        if score >= 30:
            return RiskLevel.MEDIUM.value
        return RiskLevel.LOW.value

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def score_entity(self, entity_id: str, features: Dict[str, Any]) -> RiskScore:
        """
        Produce a full RiskScore for a single entity.

        Args:
            entity_id: Unique entity identifier.
            features:  Feature dictionary (see ``_calculate_base_score`` for keys).

        Returns:
            RiskScore with base score, weighted score, risk level, and
            per-factor contributions.
        """
        base_score = self._calculate_base_score(features)

        # Per-factor partial scores for explainability
        contributing: Dict[str, float] = {}

        amount = float(features.get("transaction_amount", 0))
        contributing[RiskFactor.TRANSACTION_AMOUNT.value] = (
            min(1.0, amount / 1_000_000) * self._weights[RiskFactor.TRANSACTION_AMOUNT]
        )

        velocity = int(features.get("velocity_30d", 0))
        contributing[RiskFactor.VELOCITY.value] = (
            min(1.0, velocity / 200) * self._weights[RiskFactor.VELOCITY]
        )

        high_risk_country = features.get("high_risk_country", False)
        if isinstance(high_risk_country, str):
            high_risk_country = high_risk_country.upper() in self._HIGH_RISK_COUNTRIES
        contributing[RiskFactor.GEOGRAPHY.value] = (
            self._weights[RiskFactor.GEOGRAPHY] if high_risk_country else 0.0
        )

        customer_type = str(features.get("customer_type", "retail")).lower()
        ct_score = {"correspondent": 1.0, "corporate": 0.4, "retail": 0.1}.get(customer_type, 0.2)
        contributing[RiskFactor.CUSTOMER_TYPE.value] = (
            ct_score * self._weights[RiskFactor.CUSTOMER_TYPE]
        )

        contributing[RiskFactor.PEP_STATUS.value] = (
            self._weights[RiskFactor.PEP_STATUS] if features.get("is_pep", False) else 0.0
        )

        adverse_hits = int(features.get("adverse_media_hits", 0))
        contributing[RiskFactor.ADVERSE_MEDIA.value] = (
            min(1.0, adverse_hits / 5) * self._weights[RiskFactor.ADVERSE_MEDIA]
        )

        centrality = float(features.get("centrality_score", 0.0))
        contributing[RiskFactor.NETWORK_CENTRALITY.value] = (
            centrality * self._weights[RiskFactor.NETWORK_CENTRALITY]
        )

        contributing[RiskFactor.LAYERING_DETECTED.value] = (
            self._weights[RiskFactor.LAYERING_DETECTED]
            if features.get("layering_flag", False)
            else 0.0
        )

        weighted_score = sum(contributing.values()) * 100

        return RiskScore(
            entity_id=entity_id,
            base_score=round(base_score, 4),
            weighted_score=round(weighted_score, 4),
            risk_level=self._determine_risk_level(weighted_score),
            contributing_factors=contributing,
        )

    def batch_score_entities(
        self, entity_features: List[Dict[str, Any]]
    ) -> List[RiskScore]:
        """
        Score multiple entities in sequence.

        Each item in *entity_features* must contain an ``entity_id`` key plus
        the feature fields expected by ``score_entity``.

        Args:
            entity_features: List of feature dictionaries.

        Returns:
            List of RiskScore results in the same order as input.
        """
        results: List[RiskScore] = []
        for item in entity_features:
            entity_id = str(item.get("entity_id", "unknown"))
            features = {k: v for k, v in item.items() if k != "entity_id"}
            results.append(self.score_entity(entity_id, features))
        return results

    @staticmethod
    def get_high_risk_entities(
        scores: List[RiskScore], threshold: str = RiskLevel.HIGH.value
    ) -> List[RiskScore]:
        """
        Filter a scored list to return only entities at or above *threshold*.

        Args:
            scores:    List of RiskScore objects.
            threshold: Minimum risk level ("LOW" | "MEDIUM" | "HIGH" | "CRITICAL").

        Returns:
            Filtered and sorted (descending by weighted_score) list.
        """
        level_order = {
            RiskLevel.LOW.value: 0,
            RiskLevel.MEDIUM.value: 1,
            RiskLevel.HIGH.value: 2,
            RiskLevel.CRITICAL.value: 3,
        }
        min_level = level_order.get(threshold, 2)
        filtered = [s for s in scores if level_order.get(s.risk_level, 0) >= min_level]
        return sorted(filtered, key=lambda s: s.weighted_score, reverse=True)
