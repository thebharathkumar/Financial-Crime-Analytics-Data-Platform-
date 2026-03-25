"""
Unit tests for AMLRiskScoringEngine.
"""

import pytest

from python.aml.risk_scoring import AMLRiskScoringEngine, RiskFactor, RiskLevel, RiskScore


@pytest.fixture
def engine() -> AMLRiskScoringEngine:
    return AMLRiskScoringEngine()


# ---------------------------------------------------------------------------
# Helper feature builders
# ---------------------------------------------------------------------------

def _low_risk_features(entity_id: str = "ent-low") -> dict:
    return {
        "entity_id": entity_id,
        "transaction_amount": 500,
        "velocity_30d": 3,
        "high_risk_country": False,
        "customer_type": "retail",
        "is_pep": False,
        "adverse_media_hits": 0,
        "centrality_score": 0.0,
        "layering_flag": False,
    }


def _high_risk_features(entity_id: str = "ent-high") -> dict:
    return {
        "entity_id": entity_id,
        "transaction_amount": 2_000_000,
        "velocity_30d": 150,
        "high_risk_country": True,
        "customer_type": "correspondent",
        "is_pep": True,
        "adverse_media_hits": 5,
        "centrality_score": 0.85,
        "layering_flag": True,
    }


# ---------------------------------------------------------------------------
# score_entity
# ---------------------------------------------------------------------------

class TestScoreEntity:
    def test_low_risk_features_produce_low_level(self, engine: AMLRiskScoringEngine) -> None:
        features = _low_risk_features()
        entity_id = features.pop("entity_id")
        result = engine.score_entity(entity_id, features)
        assert result.risk_level == RiskLevel.LOW.value

    def test_high_risk_features_produce_high_or_critical(
        self, engine: AMLRiskScoringEngine
    ) -> None:
        features = _high_risk_features()
        entity_id = features.pop("entity_id")
        result = engine.score_entity(entity_id, features)
        assert result.risk_level in (RiskLevel.HIGH.value, RiskLevel.CRITICAL.value)

    def test_pep_entity_gets_elevated_score(self, engine: AMLRiskScoringEngine) -> None:
        base = _low_risk_features("pep-test")
        pep = dict(base)
        non_pep = dict(base)
        pep["is_pep"] = True
        non_pep["is_pep"] = False

        for d in (pep, non_pep):
            d.pop("entity_id", None)

        pep_result = engine.score_entity("pep-test", pep)
        non_pep_result = engine.score_entity("non-pep-test", non_pep)
        assert pep_result.weighted_score > non_pep_result.weighted_score

    def test_score_fields_populated(self, engine: AMLRiskScoringEngine) -> None:
        features = _low_risk_features()
        entity_id = features.pop("entity_id")
        result = engine.score_entity(entity_id, features)
        assert result.entity_id == entity_id
        assert 0 <= result.base_score <= 100
        assert 0 <= result.weighted_score <= 100
        assert result.risk_level in (
            RiskLevel.LOW.value, RiskLevel.MEDIUM.value,
            RiskLevel.HIGH.value, RiskLevel.CRITICAL.value,
        )
        assert result.timestamp is not None

    def test_contributing_factors_contain_all_risk_factors(
        self, engine: AMLRiskScoringEngine
    ) -> None:
        features = _low_risk_features()
        entity_id = features.pop("entity_id")
        result = engine.score_entity(entity_id, features)
        for factor in RiskFactor:
            assert factor.value in result.contributing_factors

    def test_layering_flag_increases_score(self, engine: AMLRiskScoringEngine) -> None:
        base = _low_risk_features()
        base.pop("entity_id")
        layering = dict(base)
        layering["layering_flag"] = True
        no_layering = dict(base)
        no_layering["layering_flag"] = False

        r_layer = engine.score_entity("layer-test", layering)
        r_none = engine.score_entity("no-layer-test", no_layering)
        assert r_layer.weighted_score > r_none.weighted_score

    def test_high_risk_country_code_triggers_flag(
        self, engine: AMLRiskScoringEngine
    ) -> None:
        features = _low_risk_features()
        features.pop("entity_id")
        features["high_risk_country"] = "IR"  # Iran — on FATF list
        result = engine.score_entity("geo-test", features)
        # Should have non-zero geography contribution
        geo_contrib = result.contributing_factors.get(RiskFactor.GEOGRAPHY.value, 0)
        assert geo_contrib > 0


# ---------------------------------------------------------------------------
# batch_score_entities
# ---------------------------------------------------------------------------

class TestBatchScoreEntities:
    def test_batch_returns_correct_count(self, engine: AMLRiskScoringEngine) -> None:
        batch = [_low_risk_features(f"e{i}") for i in range(5)]
        results = engine.batch_score_entities(batch)
        assert len(results) == 5

    def test_batch_entity_ids_match_input(self, engine: AMLRiskScoringEngine) -> None:
        batch = [_low_risk_features(f"entity-{i}") for i in range(3)]
        results = engine.batch_score_entities(batch)
        output_ids = {r.entity_id for r in results}
        assert output_ids == {"entity-0", "entity-1", "entity-2"}


# ---------------------------------------------------------------------------
# get_high_risk_entities
# ---------------------------------------------------------------------------

class TestGetHighRiskEntities:
    def _make_score(self, entity_id: str, weighted: float, level: str) -> RiskScore:
        return RiskScore(
            entity_id=entity_id,
            base_score=weighted,
            weighted_score=weighted,
            risk_level=level,
            contributing_factors={},
        )

    def test_filters_below_high(self) -> None:
        scores = [
            self._make_score("low", 10.0, RiskLevel.LOW.value),
            self._make_score("medium", 45.0, RiskLevel.MEDIUM.value),
            self._make_score("high", 70.0, RiskLevel.HIGH.value),
            self._make_score("critical", 90.0, RiskLevel.CRITICAL.value),
        ]
        result = AMLRiskScoringEngine.get_high_risk_entities(scores, threshold="HIGH")
        ids = [r.entity_id for r in result]
        assert "high" in ids
        assert "critical" in ids
        assert "low" not in ids
        assert "medium" not in ids

    def test_results_sorted_descending(self) -> None:
        scores = [
            self._make_score("a", 65.0, RiskLevel.HIGH.value),
            self._make_score("b", 90.0, RiskLevel.CRITICAL.value),
            self._make_score("c", 75.0, RiskLevel.HIGH.value),
        ]
        result = AMLRiskScoringEngine.get_high_risk_entities(scores, threshold="HIGH")
        weighted_scores = [r.weighted_score for r in result]
        assert weighted_scores == sorted(weighted_scores, reverse=True)

    def test_empty_list_returns_empty(self) -> None:
        result = AMLRiskScoringEngine.get_high_risk_entities([], threshold="HIGH")
        assert result == []


# ---------------------------------------------------------------------------
# _determine_risk_level
# ---------------------------------------------------------------------------

class TestDetermineRiskLevel:
    def test_thresholds(self) -> None:
        assert AMLRiskScoringEngine._determine_risk_level(10) == RiskLevel.LOW.value
        assert AMLRiskScoringEngine._determine_risk_level(45) == RiskLevel.MEDIUM.value
        assert AMLRiskScoringEngine._determine_risk_level(65) == RiskLevel.HIGH.value
        assert AMLRiskScoringEngine._determine_risk_level(85) == RiskLevel.CRITICAL.value
