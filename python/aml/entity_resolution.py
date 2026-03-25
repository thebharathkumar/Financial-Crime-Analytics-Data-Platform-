"""
Entity Resolution Engine for AML (Anti-Money Laundering) Platform.

Implements fuzzy matching and deduplication of financial entities to identify
potentially related parties, shell companies, and ownership structures.
"""

from __future__ import annotations

import re
import unicodedata
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple


@dataclass
class Entity:
    """Represents a financial entity (person, company, trust) in the AML system."""

    id: str
    name: str
    address: Optional[str] = None
    dob: Optional[str] = None          # ISO 8601 date string YYYY-MM-DD
    national_id: Optional[str] = None
    account_numbers: List[str] = field(default_factory=list)
    risk_score: float = 0.0

    def __post_init__(self) -> None:
        if not self.id:
            self.id = str(uuid.uuid4())
        if self.risk_score < 0 or self.risk_score > 100:
            raise ValueError(f"risk_score must be in [0, 100], got {self.risk_score}")


class EntityResolutionEngine:
    """
    Resolves duplicate or related entities using multi-field fuzzy matching.

    The engine normalises textual fields, computes pairwise similarity scores,
    and merges candidate pairs whose combined score exceeds a configurable
    threshold.  Merged lineage is tracked so that downstream consumers can
    traverse the resulting entity network.
    """

    # Weights must sum to 1.0
    _FIELD_WEIGHTS: Dict[str, float] = {
        "name": 0.35,
        "address": 0.20,
        "dob": 0.15,
        "national_id": 0.20,
        "account_numbers": 0.10,
    }

    def __init__(self, similarity_threshold: float = 0.80) -> None:
        """
        Initialise the engine.

        Args:
            similarity_threshold: Minimum combined similarity score (0-1) required
                                   to consider two entities as the same party.
        """
        if not 0 < similarity_threshold <= 1:
            raise ValueError("similarity_threshold must be in (0, 1]")
        self.similarity_threshold = similarity_threshold
        # Maps entity_id -> set of related entity_ids after resolution
        self._entity_network: Dict[str, Set[str]] = {}

    # ------------------------------------------------------------------
    # Normalisation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def normalize_name(name: Optional[str]) -> str:
        """
        Normalise an entity name for comparison.

        Steps:
        1. Handle None / empty.
        2. Unicode NFKD decomposition so accented chars compare cleanly.
        3. Strip non-alphabetic characters except spaces.
        4. Collapse whitespace and lowercase.

        Args:
            name: Raw name string.

        Returns:
            Normalised name suitable for fuzzy comparison.
        """
        if not name:
            return ""
        normalised = unicodedata.normalize("NFKD", name)
        normalised = normalised.encode("ascii", "ignore").decode("ascii")
        normalised = re.sub(r"[^a-zA-Z\s]", "", normalised)
        normalised = re.sub(r"\s+", " ", normalised).strip().lower()
        # Remove common legal suffixes that obscure true identity matches
        for suffix in ("ltd", "limited", "inc", "incorporated", "llc", "corp", "corporation", "co"):
            normalised = re.sub(rf"\b{suffix}\b", "", normalised)
        return re.sub(r"\s+", " ", normalised).strip()

    @staticmethod
    def normalize_address(address: Optional[str]) -> str:
        """
        Normalise a postal address for comparison.

        Args:
            address: Raw address string.

        Returns:
            Normalised address string.
        """
        if not address:
            return ""
        normalised = unicodedata.normalize("NFKD", address)
        normalised = normalised.encode("ascii", "ignore").decode("ascii")
        # Expand common abbreviations
        abbr_map = {
            r"\bst\b": "street",
            r"\bave\b": "avenue",
            r"\bblvd\b": "boulevard",
            r"\brd\b": "road",
            r"\bdr\b": "drive",
            r"\bln\b": "lane",
            r"\bapt\b": "apartment",
            r"\bfl\b": "floor",
        }
        normalised = normalised.lower()
        for pattern, replacement in abbr_map.items():
            normalised = re.sub(pattern, replacement, normalised)
        normalised = re.sub(r"[^\w\s]", " ", normalised)
        return re.sub(r"\s+", " ", normalised).strip()

    # ------------------------------------------------------------------
    # Similarity computation
    # ------------------------------------------------------------------

    @staticmethod
    def _token_set_ratio(a: str, b: str) -> float:
        """
        Compute token-based Jaccard similarity between two strings.

        Args:
            a: First string (already normalised).
            b: Second string (already normalised).

        Returns:
            Similarity score in [0, 1].
        """
        if not a and not b:
            return 1.0
        if not a or not b:
            return 0.0
        tokens_a: Set[str] = set(a.split())
        tokens_b: Set[str] = set(b.split())
        intersection = tokens_a & tokens_b
        union = tokens_a | tokens_b
        return len(intersection) / len(union) if union else 0.0

    @staticmethod
    def _char_ngram_similarity(a: str, b: str, n: int = 2) -> float:
        """
        Compute character n-gram similarity (Dice coefficient).

        Args:
            a: First string.
            b: Second string.
            n: N-gram size.

        Returns:
            Similarity score in [0, 1].
        """
        if not a and not b:
            return 1.0
        if not a or not b:
            return 0.0
        if len(a) < n or len(b) < n:
            return 1.0 if a == b else 0.0

        ngrams_a = {a[i: i + n] for i in range(len(a) - n + 1)}
        ngrams_b = {b[i: i + n] for i in range(len(b) - n + 1)}
        overlap = len(ngrams_a & ngrams_b)
        return 2 * overlap / (len(ngrams_a) + len(ngrams_b))

    def _compare_name(self, a: Optional[str], b: Optional[str]) -> float:
        na, nb = self.normalize_name(a), self.normalize_name(b)
        token_sim = self._token_set_ratio(na, nb)
        ngram_sim = self._char_ngram_similarity(na, nb)
        return 0.6 * token_sim + 0.4 * ngram_sim

    def _compare_address(self, a: Optional[str], b: Optional[str]) -> float:
        na, nb = self.normalize_address(a), self.normalize_address(b)
        return self._token_set_ratio(na, nb)

    @staticmethod
    def _compare_exact(a: Optional[str], b: Optional[str]) -> float:
        """Exact match returning 1.0 or 0.0, treating None == None as 0 (unknown)."""
        if a is None or b is None:
            return 0.0
        return 1.0 if a.strip().lower() == b.strip().lower() else 0.0

    @staticmethod
    def _compare_account_numbers(a: List[str], b: List[str]) -> float:
        """Jaccard similarity over sets of account numbers."""
        set_a, set_b = set(a), set(b)
        if not set_a and not set_b:
            return 0.0
        if not set_a or not set_b:
            return 0.0
        return len(set_a & set_b) / len(set_a | set_b)

    def calculate_similarity(self, entity_a: Entity, entity_b: Entity) -> float:
        """
        Compute a weighted similarity score between two entities.

        Each field is scored independently then combined using the class-level
        weight dictionary.

        Args:
            entity_a: First entity.
            entity_b: Second entity.

        Returns:
            Combined similarity score in [0, 1].
        """
        scores: Dict[str, float] = {
            "name": self._compare_name(entity_a.name, entity_b.name),
            "address": self._compare_address(entity_a.address, entity_b.address),
            "dob": self._compare_exact(entity_a.dob, entity_b.dob),
            "national_id": self._compare_exact(entity_a.national_id, entity_b.national_id),
            "account_numbers": self._compare_account_numbers(
                entity_a.account_numbers, entity_b.account_numbers
            ),
        }
        return sum(scores[k] * self._FIELD_WEIGHTS[k] for k in scores)

    # ------------------------------------------------------------------
    # Resolution and merging
    # ------------------------------------------------------------------

    def resolve_entities(self, entities: List[Entity]) -> List[List[Entity]]:
        """
        Group a list of entities into clusters of likely duplicates.

        Uses a union-find approach: iterate candidate pairs, merge clusters
        whenever similarity >= threshold.

        Args:
            entities: Input entity list (may contain duplicates).

        Returns:
            List of groups, where each group is a list of entities considered
            the same real-world party.  Unique entities appear in singleton groups.
        """
        n = len(entities)
        parent = list(range(n))

        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(x: int, y: int) -> None:
            parent[find(x)] = find(y)

        for i in range(n):
            for j in range(i + 1, n):
                if entities[i].id == entities[j].id:
                    union(i, j)
                    continue
                sim = self.calculate_similarity(entities[i], entities[j])
                if sim >= self.similarity_threshold:
                    union(i, j)

        groups: Dict[int, List[Entity]] = {}
        for idx, entity in enumerate(entities):
            root = find(idx)
            groups.setdefault(root, []).append(entity)

        # Persist network information
        for group in groups.values():
            for entity in group:
                related = {e.id for e in group if e.id != entity.id}
                self._entity_network.setdefault(entity.id, set()).update(related)

        return list(groups.values())

    def merge_entities(self, entity_a: Entity, entity_b: Entity) -> Entity:
        """
        Produce a single canonical Entity from two resolved duplicates.

        Strategy:
        - Prefer non-None values from entity_a (higher confidence record).
        - Merge account number lists, de-duplicating.
        - Take the maximum risk score as the conservative choice.

        Args:
            entity_a: Primary entity (preferred source for fields).
            entity_b: Secondary entity.

        Returns:
            New Entity representing the merged record.
        """
        merged_accounts = list(set(entity_a.account_numbers + entity_b.account_numbers))
        return Entity(
            id=entity_a.id,
            name=entity_a.name or entity_b.name,
            address=entity_a.address or entity_b.address,
            dob=entity_a.dob or entity_b.dob,
            national_id=entity_a.national_id or entity_b.national_id,
            account_numbers=merged_accounts,
            risk_score=max(entity_a.risk_score, entity_b.risk_score),
        )

    def get_entity_network(self, entity_id: str) -> List[str]:
        """
        Return entity IDs related to the given entity (from prior resolution).

        Args:
            entity_id: The entity whose network to retrieve.

        Returns:
            List of related entity IDs.  Empty list if entity is unknown or isolated.
        """
        return list(self._entity_network.get(entity_id, set()))
