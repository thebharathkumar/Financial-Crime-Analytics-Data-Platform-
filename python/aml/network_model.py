"""
Network Graph Model for AML Transaction Analysis.

Provides adjacency-list-based graph primitives for modelling transaction
flows between accounts and entities, with built-in detection of suspicious
patterns such as cycles, layering chains, and high-centrality nodes.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple


class NodeType(str, Enum):
    ACCOUNT = "ACCOUNT"
    ENTITY = "ENTITY"
    TRANSACTION = "TRANSACTION"


class EdgeType(str, Enum):
    TRANSFER = "TRANSFER"
    OWNERSHIP = "OWNERSHIP"
    CONTROL = "CONTROL"
    ASSOCIATION = "ASSOCIATION"


@dataclass
class TransactionNode:
    """A vertex in the transaction network graph."""

    node_id: str
    entity_id: Optional[str]
    node_type: NodeType
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TransactionEdge:
    """A directed, weighted edge in the transaction network graph."""

    edge_id: str
    source_id: str
    target_id: str
    weight: float
    edge_type: EdgeType
    timestamp: float          # Unix epoch seconds
    amount: float = 0.0


class NetworkModel:
    """
    Directed weighted graph for AML network analysis.

    All graph operations are implemented from first principles (no third-party
    graph libraries) to ensure compatibility across deployment environments and
    to give full control over AML-specific traversal semantics.
    """

    # Transactions below this amount are not considered high-value for
    # suspicious path detection.
    _HIGH_VALUE_THRESHOLD: float = 10_000.0
    # Minimum number of hops for a path to be flagged as suspicious due
    # to complexity alone.
    _MIN_SUSPICIOUS_HOPS: int = 3
    # Minimum total amount flowing through a path to flag it regardless of
    # hop count.
    _SUSPICIOUS_PATH_AMOUNT: float = 50_000.0

    def __init__(self) -> None:
        self._nodes: Dict[str, TransactionNode] = {}
        # adjacency: source_id -> list of (target_id, edge_id)
        self._adj: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
        # reverse adjacency for in-degree computations
        self._radj: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
        self._edges: Dict[str, TransactionEdge] = {}

    # ------------------------------------------------------------------
    # Graph construction
    # ------------------------------------------------------------------

    def add_node(self, node: TransactionNode) -> None:
        """
        Add a node to the graph.

        Args:
            node: TransactionNode to add.  Silently overwrites existing node
                  with same id.
        """
        self._nodes[node.node_id] = node
        # Ensure adjacency slots exist even for isolated nodes
        if node.node_id not in self._adj:
            self._adj[node.node_id] = []

    def add_edge(self, edge: TransactionEdge) -> None:
        """
        Add a directed edge to the graph.

        Auto-creates stub nodes for source/target if they are not present so
        that edge-first ingestion is supported.

        Args:
            edge: TransactionEdge to add.
        """
        self._edges[edge.edge_id] = edge
        # Auto-create stub nodes if not already present
        for nid in (edge.source_id, edge.target_id):
            if nid not in self._nodes:
                self._nodes[nid] = TransactionNode(
                    node_id=nid, entity_id=None, node_type=NodeType.ACCOUNT
                )
        self._adj[edge.source_id].append((edge.target_id, edge.edge_id))
        self._radj[edge.target_id].append((edge.source_id, edge.edge_id))

    # ------------------------------------------------------------------
    # Basic queries
    # ------------------------------------------------------------------

    def get_neighbors(self, node_id: str) -> List[str]:
        """
        Return direct successor node IDs for a given node.

        Args:
            node_id: Source node identifier.

        Returns:
            List of neighbour node IDs (may contain duplicates if multiple
            edges exist between the same pair).
        """
        return [target for target, _ in self._adj.get(node_id, [])]

    def _get_edge_between(self, source_id: str, target_id: str) -> Optional[TransactionEdge]:
        """Return the first edge from source to target, or None."""
        for tgt, eid in self._adj.get(source_id, []):
            if tgt == target_id:
                return self._edges[eid]
        return None

    # ------------------------------------------------------------------
    # Cycle detection
    # ------------------------------------------------------------------

    def detect_cycles(self, start_node_id: str) -> bool:
        """
        Determine whether the graph contains a cycle reachable from *start_node_id*.

        Uses iterative DFS with a 'grey set' (currently on the DFS stack) to
        detect back-edges.

        Args:
            start_node_id: Node from which to begin the DFS.

        Returns:
            True if a cycle is reachable from the start node, False otherwise.
        """
        if start_node_id not in self._nodes:
            return False

        visited: Set[str] = set()
        stack: Set[str] = set()

        def dfs(node_id: str) -> bool:
            visited.add(node_id)
            stack.add(node_id)
            for neighbour in self.get_neighbors(node_id):
                if neighbour not in visited:
                    if dfs(neighbour):
                        return True
                elif neighbour in stack:
                    return True
            stack.discard(node_id)
            return False

        return dfs(start_node_id)

    # ------------------------------------------------------------------
    # Suspicious path detection
    # ------------------------------------------------------------------

    def find_suspicious_paths(
        self, source_id: str, max_hops: int = 5
    ) -> List[List[str]]:
        """
        Find paths originating at *source_id* that exhibit suspicious characteristics.

        A path is considered suspicious if:
        - It has >= ``_MIN_SUSPICIOUS_HOPS`` hops, **or**
        - The total transaction amount along the path exceeds
          ``_SUSPICIOUS_PATH_AMOUNT``.

        BFS is used to enumerate all simple paths up to *max_hops* depth.

        Args:
            source_id: Starting node for path enumeration.
            max_hops:  Maximum path length (number of edges) to explore.

        Returns:
            List of paths, where each path is an ordered list of node IDs.
        """
        if source_id not in self._nodes:
            return []

        suspicious: List[List[str]] = []
        # BFS queue: (current_node, path_so_far, total_amount, visited_set)
        queue: deque = deque([(source_id, [source_id], 0.0, {source_id})])

        while queue:
            current, path, total_amount, visited = queue.popleft()

            if len(path) > 1:  # at least one edge traversed
                hops = len(path) - 1
                if hops >= self._MIN_SUSPICIOUS_HOPS or total_amount >= self._SUSPICIOUS_PATH_AMOUNT:
                    suspicious.append(list(path))

            if len(path) - 1 >= max_hops:
                continue

            for neighbour, eid in self._adj.get(current, []):
                if neighbour in visited:
                    continue
                edge = self._edges[eid]
                new_amount = total_amount + edge.amount
                new_visited = visited | {neighbour}
                queue.append((neighbour, path + [neighbour], new_amount, new_visited))

        return suspicious

    # ------------------------------------------------------------------
    # Centrality
    # ------------------------------------------------------------------

    def calculate_centrality(self, node_id: str) -> float:
        """
        Compute normalised degree centrality for *node_id*.

        Degree centrality = (in-degree + out-degree) / (2 * (N - 1))
        where N is the total number of nodes in the graph.

        Args:
            node_id: Target node.

        Returns:
            Centrality score in [0, 1].  Returns 0.0 for unknown nodes or
            single-node graphs.
        """
        n = len(self._nodes)
        if n <= 1 or node_id not in self._nodes:
            return 0.0
        out_degree = len(self._adj.get(node_id, []))
        in_degree = len(self._radj.get(node_id, []))
        return (in_degree + out_degree) / (2 * (n - 1))

    # ------------------------------------------------------------------
    # Layering detection
    # ------------------------------------------------------------------

    def detect_layering_patterns(self) -> List[str]:
        """
        Identify nodes involved in potential layering activity.

        Layering is characterised by rapid sequential transaction chains:
        funds flow through a series of 3 or more intermediary accounts in
        quick succession, obscuring the origin of the money.

        Detection heuristic:
        - A node participates in layering if it is part of a directed chain of
          length >= 3 where each consecutive edge has a higher timestamp than
          the previous (temporal ordering) and each edge is a TRANSFER.

        Returns:
            Sorted list of node IDs involved in detected layering chains.
        """
        layering_nodes: Set[str] = set()

        for start_id in self._nodes:
            # DFS to find temporally ordered transfer chains
            stack: List[Tuple[str, List[str], float]] = [
                (start_id, [start_id], -1.0)
            ]
            while stack:
                node_id, chain, last_ts = stack.pop()
                for neighbour, eid in self._adj.get(node_id, []):
                    edge = self._edges[eid]
                    if edge.edge_type != EdgeType.TRANSFER:
                        continue
                    if edge.timestamp < last_ts:
                        continue  # not temporally ordered
                    new_chain = chain + [neighbour]
                    if len(new_chain) >= 3:
                        layering_nodes.update(new_chain)
                    if len(new_chain) < 6:  # bound search depth
                        stack.append((neighbour, new_chain, edge.timestamp))

        return sorted(layering_nodes)

    # ------------------------------------------------------------------
    # Graph statistics
    # ------------------------------------------------------------------

    def get_network_stats(self) -> Dict[str, Any]:
        """
        Compute summary statistics for the network.

        Returns:
            Dictionary containing:
            - node_count (int)
            - edge_count (int)
            - density (float): actual edges / max possible edges
            - suspicious_nodes (List[str]): high-centrality node IDs (top 10%)
        """
        n = len(self._nodes)
        e = len(self._edges)
        max_edges = n * (n - 1) if n > 1 else 1
        density = e / max_edges

        centralities = {
            nid: self.calculate_centrality(nid) for nid in self._nodes
        }
        if centralities:
            sorted_by_centrality = sorted(
                centralities.items(), key=lambda x: x[1], reverse=True
            )
            top_10_pct = max(1, int(len(sorted_by_centrality) * 0.10))
            suspicious_nodes = [nid for nid, _ in sorted_by_centrality[:top_10_pct]]
        else:
            suspicious_nodes = []

        return {
            "node_count": n,
            "edge_count": e,
            "density": round(density, 6),
            "suspicious_nodes": suspicious_nodes,
        }
