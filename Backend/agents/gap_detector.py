"""
Gap Detector Agent for the Multi-Agent Research Intelligence System.

Analyzes the knowledge graph to identify:
- Research gaps (unexplored areas)
- Missing intersections (understudied combinations)
- Novelty opportunities (novel research directions)

Uses embeddings and graph structure to detect semantic and structural gaps.
"""

import asyncio
import logging
from typing import List

from api.llm import get_llm_client
from knowledge_graph.embeddings import EmbeddingService
from knowledge_graph.graph_store import get_graph_store
from models.graph import (
    KnowledgeGraph,
    ResearchGap,
    GraphNode,
    GraphEdge,
)

logger = logging.getLogger(__name__)


class GapDetectorAgent:
    """Detects research gaps in the knowledge graph."""

    def __init__(self, llm_client, embedding_service=None):
        self.llm_client = llm_client
        self.embedding_service = embedding_service  # may be None
        self.graph_store = get_graph_store("json")

    async def detect_gaps(
        self,
        graph: KnowledgeGraph,
        original_query: str,
        config,
    ) -> List[ResearchGap]:
        """
        Analyze graph structure to detect research gaps.

        Strategies:
        1. Structural gaps: Isolated nodes with few connections
        2. Semantic gaps: Clusters with no cross-cluster links
        3. Temporal gaps: Evolution or trending gaps
        4. Novelty gaps: Unexplored intersections
        """
        gaps = []

        # Strategy 1: Find structurally isolated nodes
        isolated_gaps = await self._detect_structural_gaps(graph)
        gaps.extend(isolated_gaps)

        # Strategy 2: Find semantic clusters with no bridges
        cluster_gaps = await self._detect_semantic_gaps(graph)
        gaps.extend(cluster_gaps)

        # Strategy 3: Find unexplored intersections
        intersection_gaps = await self._detect_intersection_gaps(graph, original_query)
        gaps.extend(intersection_gaps)

        logger.info(f"Detected {len(gaps)} research gaps")
        return gaps

    async def _detect_structural_gaps(self, graph: KnowledgeGraph) -> List[ResearchGap]:
        """
        Find nodes with few connections (structural isolation).
        These indicate potential research areas needing more exploration.
        """
        gaps = []

        # Calculate degree (connectivity) for each node
        node_degrees = {}
        for node_id in graph.nodes:
            neighbors = graph.get_neighbors(node_id)
            node_degrees[node_id] = len(neighbors)

        # Find nodes in bottom 20th percentile (least connected)
        if node_degrees:
            degree_values = sorted(node_degrees.values())
            cutoff_idx = max(0, len(degree_values) // 5)
            low_degree_threshold = degree_values[cutoff_idx]

            for node_id, degree in node_degrees.items():
                if degree <= low_degree_threshold and degree < 3:
                    node = graph.nodes[node_id]
                    gap = ResearchGap(
                        gap_id=f"gap_structural_{node_id}",
                        title=f"Unexplored aspects of '{node.title}'",
                        description=f"Research on '{node.title}' is isolated with only {degree} connection(s). Consider exploring related work that bridges this to other research areas.",
                        affected_nodes=[node_id],
                        severity_score=0.7 if degree == 0 else 0.4,
                    )
                    gaps.append(gap)

        return gaps

    async def _detect_semantic_gaps(self, graph: KnowledgeGraph) -> List[ResearchGap]:
        """
        Find semantic clusters in the graph using embeddings.
        Identify clusters that should be connected but aren't.
        """
        gaps = []

        if not graph.nodes:
            return gaps

        # Build adjacency for clustering
        from sklearn.cluster import KMeans

        # Collect embeddings
        embeddings = []
        node_ids = []
        for node_id, node in graph.nodes.items():
            if node.embedding:
                embeddings.append(node.embedding)
                node_ids.append(node_id)

        if len(embeddings) < 2:
            return gaps

        # Simple clustering
        try:
            import numpy as np

            embeddings_array = np.array(embeddings)
            n_clusters = max(2, min(len(node_ids) // 5, 10))

            kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
            labels = kmeans.fit_predict(embeddings_array)

            # Find cluster pairs with low inter-cluster connectivity
            for i in range(n_clusters):
                cluster_i_nodes = [node_ids[j] for j in range(len(node_ids)) if labels[j] == i]

                for j in range(i + 1, n_clusters):
                    cluster_j_nodes = [node_ids[k] for k in range(len(node_ids)) if labels[k] == j]

                    # Count cross-cluster edges
                    cross_edges = 0
                    for edge in graph.edges.values():
                        if (
                            (edge.source_node_id in cluster_i_nodes
                             and edge.target_node_id in cluster_j_nodes)
                            or (edge.source_node_id in cluster_j_nodes
                                and edge.target_node_id in cluster_i_nodes)
                        ):
                            cross_edges += 1

                    # If clusters are disconnected, it's a gap
                    if cross_edges == 0 and len(cluster_i_nodes) > 0 and len(cluster_j_nodes) > 0:
                        titles_i = ", ".join([graph.nodes[nid].title for nid in cluster_i_nodes[:2]])
                        titles_j = ", ".join([graph.nodes[nid].title for nid in cluster_j_nodes[:2]])

                        gap = ResearchGap(
                            gap_id=f"gap_semantic_{i}_{j}",
                            title=f"Missing bridge between '{titles_i}' and '{titles_j}'",
                            description=f"Two research clusters appear disconnected. Consider exploring work that bridges {titles_i} with {titles_j}.",
                            affected_nodes=cluster_i_nodes + cluster_j_nodes,
                            missing_intersections=[
                                {
                                    "cluster_a": f"Cluster {i}",
                                    "cluster_b": f"Cluster {j}",
                                }
                            ],
                            severity_score=0.6,
                        )
                        gaps.append(gap)
        except Exception as e:
            logger.warning(f"Semantic gap detection failed: {e}")

        return gaps

    async def _detect_intersection_gaps(
        self, graph: KnowledgeGraph, original_query: str
    ) -> List[ResearchGap]:
        """
        Find unexplored intersections between topics.
        Uses LLM to reason about what topics should be studied together.
        """
        gaps = []

        if not graph.nodes:
            return gaps

        # Extract key topics from nodes
        topics = list(set([kw for node in graph.nodes.values() for kw in node.keywords]))
        topics = topics[:10]  # Limit to top 10

        if len(topics) < 2:
            return gaps

        # Use LLM to identify interesting intersections
        prompt = f"""
        Given these research topics: {', '.join(topics)}
        
        And the original research query: {original_query}
        
        Identify 3-5 interesting intersections or combinations that are NOT yet explored
        in the research findings. These should be novel research directions.
        
        Format as JSON:
        {{
            "gaps": [
                {{"intersection": "Topic A + Topic B", "reason": "...", "potential_impact": "high|medium|low"}}
            ]
        }}
        """

        try:
            from api.llm import LLM_MODEL, LLM_PROVIDER
            if LLM_PROVIDER == "anthropic":
                resp = await self.llm_client.messages.create(
                    model=LLM_MODEL, max_tokens=500,
                    system="You are a research analyst identifying gaps in academic literature.",
                    messages=[{"role": "user", "content": prompt}],
                )
                response = next((b.text for b in resp.content if hasattr(b, "text")), "")
            else:
                resp = await self.llm_client.chat.completions.create(
                    model=LLM_MODEL,
                    messages=[
                        {"role": "system", "content": "You are a research analyst identifying gaps in academic literature."},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.7,
                    max_tokens=500,
                )
                response = resp.choices[0].message.content or ""

            # Parse response
            import json
            import re

            json_match = re.search(r"\{.*\}", response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                for gap_info in result.get("gaps", []):
                    gap = ResearchGap(
                        gap_id=f"gap_intersection_{len(gaps)}",
                        title=f"Unexplored: {gap_info['intersection']}",
                        description=gap_info.get(
                            "reason",
                            f"The intersection of {gap_info['intersection']} has not been explored in current research.",
                        ),
                        missing_intersections=[gap_info],
                        severity_score={"high": 0.9, "medium": 0.6, "low": 0.3}.get(
                            gap_info.get("potential_impact", "medium"), 0.6
                        ),
                    )
                    gaps.append(gap)
        except Exception as e:
            logger.warning(f"LLM intersection gap detection failed: {e}")

        return gaps
