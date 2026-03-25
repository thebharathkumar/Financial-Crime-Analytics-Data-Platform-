"""
Unit tests for EntityResolutionEngine.
"""

import pytest

from python.aml.entity_resolution import Entity, EntityResolutionEngine


@pytest.fixture
def engine() -> EntityResolutionEngine:
    return EntityResolutionEngine(similarity_threshold=0.80)


# ---------------------------------------------------------------------------
# normalize_name
# ---------------------------------------------------------------------------

class TestNormalizeName:
    def test_lowercases_and_strips(self, engine: EntityResolutionEngine) -> None:
        assert engine.normalize_name("  John SMITH  ") == "john smith"

    def test_handles_none(self, engine: EntityResolutionEngine) -> None:
        assert engine.normalize_name(None) == ""

    def test_handles_empty_string(self, engine: EntityResolutionEngine) -> None:
        assert engine.normalize_name("") == ""

    def test_removes_legal_suffixes(self, engine: EntityResolutionEngine) -> None:
        result = engine.normalize_name("Acme Corporation Ltd")
        assert "ltd" not in result
        assert "corporation" not in result
        assert "acme" in result

    def test_normalises_accented_characters(self, engine: EntityResolutionEngine) -> None:
        # NFKD decomposition converts Á→A, é→e, í→i, etc., so base letters are preserved.
        result = engine.normalize_name("Ángel García")
        assert result == "angel garcia"

    def test_collapses_whitespace(self, engine: EntityResolutionEngine) -> None:
        result = engine.normalize_name("John   Michael   Smith")
        assert "  " not in result


# ---------------------------------------------------------------------------
# normalize_address
# ---------------------------------------------------------------------------

class TestNormalizeAddress:
    def test_expands_abbreviations(self, engine: EntityResolutionEngine) -> None:
        result = engine.normalize_address("123 Main St")
        assert "street" in result

    def test_handles_none(self, engine: EntityResolutionEngine) -> None:
        assert engine.normalize_address(None) == ""

    def test_lowercases(self, engine: EntityResolutionEngine) -> None:
        result = engine.normalize_address("456 PARK AVE")
        assert result == result.lower()

    def test_removes_punctuation(self, engine: EntityResolutionEngine) -> None:
        result = engine.normalize_address("10, Downing St.")
        assert "," not in result


# ---------------------------------------------------------------------------
# calculate_similarity
# ---------------------------------------------------------------------------

class TestCalculateSimilarity:
    def test_identical_entities_score_one(self, engine: EntityResolutionEngine) -> None:
        e = Entity(
            id="e1",
            name="John Smith",
            address="123 Main Street",
            dob="1980-01-15",
            national_id="ABC123456",
            account_numbers=["ACC001"],
        )
        score = engine.calculate_similarity(e, e)
        assert score >= 0.90

    def test_similar_entities_above_threshold(self, engine: EntityResolutionEngine) -> None:
        a = Entity(
            id="a1",
            name="John Smith",
            address="123 Main Street",
            dob="1980-01-15",
            national_id="ABC123456",
            account_numbers=["ACC001"],
        )
        b = Entity(
            id="b1",
            name="Jon Smith",          # slight typo
            address="123 Main St",     # abbreviated
            dob="1980-01-15",
            national_id="ABC123456",
            account_numbers=["ACC001"],
        )
        score = engine.calculate_similarity(a, b)
        assert score >= 0.70

    def test_completely_different_entities_low_score(
        self, engine: EntityResolutionEngine
    ) -> None:
        a = Entity(id="a2", name="Alice Wang", national_id="ZZZ999")
        b = Entity(id="b2", name="Robert Johnson", national_id="AAA111")
        score = engine.calculate_similarity(a, b)
        assert score < 0.50

    def test_score_in_range(self, engine: EntityResolutionEngine) -> None:
        a = Entity(id="x", name="Test Entity")
        b = Entity(id="y", name="Another Entity")
        score = engine.calculate_similarity(a, b)
        assert 0.0 <= score <= 1.0

    def test_shared_account_numbers_increase_score(
        self, engine: EntityResolutionEngine
    ) -> None:
        a = Entity(id="a3", name="Different Name A", account_numbers=["SHARED001"])
        b = Entity(id="b3", name="Different Name B", account_numbers=["SHARED001"])
        score_shared = engine.calculate_similarity(a, b)
        a_no_acct = Entity(id="a3", name="Different Name A")
        b_no_acct = Entity(id="b3", name="Different Name B")
        score_no_shared = engine.calculate_similarity(a_no_acct, b_no_acct)
        assert score_shared > score_no_shared


# ---------------------------------------------------------------------------
# resolve_entities
# ---------------------------------------------------------------------------

class TestResolveEntities:
    def test_duplicates_grouped_together(self, engine: EntityResolutionEngine) -> None:
        entities = [
            Entity(
                id="ent1",
                name="Maria Gonzalez",
                dob="1975-06-20",
                national_id="MG12345",
                account_numbers=["ACC-A"],
            ),
            Entity(
                id="ent2",
                name="Maria Gonzalez",
                dob="1975-06-20",
                national_id="MG12345",
                account_numbers=["ACC-A"],
            ),
            Entity(
                id="ent3",
                name="Carlos Rivera",
                national_id="CR99999",
            ),
        ]
        groups = engine.resolve_entities(entities)
        # Maria duplicates → one group; Carlos → singleton
        assert len(groups) == 2

    def test_unique_entities_remain_separate(self, engine: EntityResolutionEngine) -> None:
        entities = [
            Entity(id="u1", name="Alice Tan", national_id="AT0001"),
            Entity(id="u2", name="Bob Chen", national_id="BC0002"),
            Entity(id="u3", name="Carol Wu", national_id="CW0003"),
        ]
        groups = engine.resolve_entities(entities)
        assert len(groups) == 3

    def test_same_id_always_merged(self, engine: EntityResolutionEngine) -> None:
        entities = [
            Entity(id="same", name="Entity Alpha"),
            Entity(id="same", name="Entity Alpha"),
        ]
        groups = engine.resolve_entities(entities)
        assert len(groups) == 1


# ---------------------------------------------------------------------------
# merge_entities
# ---------------------------------------------------------------------------

class TestMergeEntities:
    def test_merge_combines_account_numbers(self, engine: EntityResolutionEngine) -> None:
        a = Entity(id="m1", name="Jane Doe", account_numbers=["ACC-X"])
        b = Entity(id="m2", name="Jane Doe", account_numbers=["ACC-Y"])
        merged = engine.merge_entities(a, b)
        assert set(merged.account_numbers) == {"ACC-X", "ACC-Y"}

    def test_merge_takes_max_risk_score(self, engine: EntityResolutionEngine) -> None:
        a = Entity(id="r1", name="Entity A", risk_score=30.0)
        b = Entity(id="r2", name="Entity B", risk_score=75.0)
        merged = engine.merge_entities(a, b)
        assert merged.risk_score == 75.0

    def test_merge_prefers_primary_fields(self, engine: EntityResolutionEngine) -> None:
        a = Entity(id="p1", name="Primary Name", address="Primary Address")
        b = Entity(id="p2", name="Secondary Name", address=None)
        merged = engine.merge_entities(a, b)
        assert merged.name == "Primary Name"
        assert merged.address == "Primary Address"

    def test_merge_fills_missing_fields_from_secondary(
        self, engine: EntityResolutionEngine
    ) -> None:
        a = Entity(id="f1", name="Name Only", dob=None)
        b = Entity(id="f2", name="Name Only", dob="1990-01-01")
        merged = engine.merge_entities(a, b)
        assert merged.dob == "1990-01-01"


# ---------------------------------------------------------------------------
# get_entity_network
# ---------------------------------------------------------------------------

class TestGetEntityNetwork:
    def test_network_populated_after_resolution(
        self, engine: EntityResolutionEngine
    ) -> None:
        # Provide entities with enough shared fields to exceed the 0.80 threshold.
        entities = [
            Entity(
                id="net1",
                name="Alice Wong",
                dob="1988-03-15",
                national_id="ALICE01",
                account_numbers=["ACC-NET"],
            ),
            Entity(
                id="net2",
                name="Alice Wong",
                dob="1988-03-15",
                national_id="ALICE01",
                account_numbers=["ACC-NET"],
            ),
        ]
        engine.resolve_entities(entities)
        related = engine.get_entity_network("net1")
        assert "net2" in related

    def test_unknown_entity_returns_empty(
        self, engine: EntityResolutionEngine
    ) -> None:
        result = engine.get_entity_network("does_not_exist")
        assert result == []
