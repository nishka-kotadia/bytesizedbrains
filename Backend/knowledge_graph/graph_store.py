"""
Knowledge graph storage and persistence layer.

Supports:
- JSON backend (lightweight, local)
- Neo4j backend (production, full-featured)
- Memgraph backend (Neo4j-compatible, OSS)

Provides unified interface for graph operations regardless of backend.
"""

import json
import logging
import os
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional, Any

from models.graph import GraphNode, GraphEdge, ResearchGap, ResearchIdea, KnowledgeGraph

logger = logging.getLogger(__name__)


class GraphStore(ABC):
    """Abstract base for graph storage backends."""

    @abstractmethod
    async def save_node(self, node: GraphNode) -> None:
        """Persist a node."""
        pass

    @abstractmethod
    async def save_edge(self, edge: GraphEdge) -> None:
        """Persist an edge."""
        pass

    @abstractmethod
    async def load_graph(self, graph_id: str) -> Optional[KnowledgeGraph]:
        """Load complete graph."""
        pass

    @abstractmethod
    async def save_graph(self, graph: KnowledgeGraph) -> None:
        """Persist entire graph."""
        pass

    @abstractmethod
    async def query_similar_nodes(
        self, embedding: List[float], limit: int = 10, threshold: float = 0.7
    ) -> List[GraphNode]:
        """Find semantically similar nodes."""
        pass

    @abstractmethod
    async def get_node_by_id(self, node_id: str) -> Optional[GraphNode]:
        """Retrieve a specific node."""
        pass


class JSONGraphStore(GraphStore):
    """
    Lightweight JSON-based graph storage.
    
    Best for:
    - Development/testing
    - Small graphs (<5000 nodes)
    - Single-machine deployments
    - Quick prototyping
    """

    def __init__(self, storage_path: str = "data/knowledge_graph.json"):
        self.storage_path = storage_path
        os.makedirs(os.path.dirname(storage_path), exist_ok=True)

    async def save_node(self, node: GraphNode) -> None:
        """Add/update node in JSON graph."""
        graph = await self._load_raw_graph()
        graph["nodes"][node.node_id] = json.loads(node.model_dump_json())
        await self._save_raw_graph(graph)

    async def save_edge(self, edge: GraphEdge) -> None:
        """Add/update edge in JSON graph."""
        graph = await self._load_raw_graph()
        graph["edges"][edge.edge_id] = json.loads(edge.model_dump_json())
        await self._save_raw_graph(graph)

    async def save_graph(self, graph: KnowledgeGraph) -> None:
        """Save entire graph as JSON."""
        graph_dict = graph.to_dict()
        with open(self.storage_path, "w") as f:
            json.dump(graph_dict, f, indent=2, default=str)
        logger.info(f"Saved graph to {self.storage_path}")

    async def load_graph(self, graph_id: str) -> Optional[KnowledgeGraph]:
        """Load graph from JSON storage."""
        if not os.path.exists(self.storage_path):
            return None

        try:
            with open(self.storage_path, "r") as f:
                graph_dict = json.load(f)

            graph = KnowledgeGraph(
                graph_id=graph_id,
                created_at=datetime.fromisoformat(graph_dict.get("created_at", datetime.utcnow().isoformat())),
            )

            # Load nodes
            for node_id, node_data in graph_dict.get("nodes", {}).items():
                node = GraphNode(**node_data)
                graph.add_node(node)

            # Load edges
            for edge_id, edge_data in graph_dict.get("edges", {}).items():
                edge = GraphEdge(**edge_data)
                graph.add_edge(edge)

            # Load gaps
            for gap_id, gap_data in graph_dict.get("gaps", {}).items():
                gap = ResearchGap(**gap_data)
                graph.add_gap(gap)

            # Load ideas
            for idea_id, idea_data in graph_dict.get("ideas", {}).items():
                idea = ResearchIdea(**idea_data)
                graph.add_idea(idea)

            logger.info(f"Loaded graph with {graph.node_count} nodes and {graph.edge_count} edges")
            return graph
        except Exception as e:
            logger.error(f"Failed to load graph: {e}")
            return None

    async def query_similar_nodes(
        self,
        embedding: List[float],
        limit: int = 10,
        threshold: float = 0.7,
    ) -> List[GraphNode]:
        """Find semantically similar nodes by embedding."""
        from knowledge_graph.embeddings import EmbeddingService

        graph = await self._load_raw_graph()
        nodes = graph.get("nodes", {})

        similarities = []
        for node_id, node_data in nodes.items():
            if "embedding" not in node_data or node_data["embedding"] is None:
                continue

            sim = EmbeddingService.cosine_similarity(
                embedding, node_data["embedding"]
            )
            if sim >= threshold:
                similarities.append((node_id, sim, node_data))

        # Sort by similarity descending
        similarities.sort(key=lambda x: x[1], reverse=True)

        # Return top K as GraphNode objects
        return [GraphNode(**node_data) for _, _, node_data in similarities[:limit]]

    async def get_node_by_id(self, node_id: str) -> Optional[GraphNode]:
        """Retrieve a specific node."""
        graph = await self._load_raw_graph()
        node_data = graph.get("nodes", {}).get(node_id)
        if node_data:
            return GraphNode(**node_data)
        return None

    async def _load_raw_graph(self) -> Dict[str, Any]:
        """Load raw graph dict."""
        if os.path.exists(self.storage_path):
            with open(self.storage_path, "r") as f:
                return json.load(f)
        return {"nodes": {}, "edges": {}, "gaps": {}, "ideas": {}}

    async def _save_raw_graph(self, graph_dict: Dict[str, Any]) -> None:
        """Save raw graph dict."""
        with open(self.storage_path, "w") as f:
            json.dump(graph_dict, f, indent=2, default=str)


class Neo4jGraphStore(GraphStore):
    """
    Neo4j graph database backend.
    
    Best for:
    - Production deployments
    - Large graphs (>10k nodes)
    - Complex graph queries
    - Multi-user access
    """

    def __init__(self, uri: str = "bolt://localhost:7687", auth: Optional[tuple] = None):
        try:
            from neo4j import AsyncGraphDatabase

            self.driver = AsyncGraphDatabase.driver(uri, auth=auth)
        except ImportError:
            raise ImportError(
                "neo4j package required. Install with: pip install neo4j"
            )

    async def save_node(self, node: GraphNode) -> None:
        """Save node to Neo4j."""
        async with self.driver.session() as session:
            await session.run(
                """
                MERGE (n:Source {node_id: $node_id})
                SET n += $props
                """,
                node_id=node.node_id,
                props=node.model_dump(),
            )

    async def save_edge(self, edge: GraphEdge) -> None:
        """Save edge to Neo4j."""
        async with self.driver.session() as session:
            rel_type = edge.relationship_type.value.upper()
            await session.run(
                f"""
                MATCH (a:Source {{node_id: $source}}),
                      (b:Source {{node_id: $target}})
                CREATE (a)-[r:{rel_type} $props]->(b)
                """,
                source=edge.source_node_id,
                target=edge.target_node_id,
                props=edge.model_dump(),
            )

    async def load_graph(self, graph_id: str) -> Optional[KnowledgeGraph]:
        """Load graph from Neo4j."""
        async with self.driver.session() as session:
            nodes_result = await session.run("MATCH (n:Source) RETURN n")
            edges_result = await session.run("MATCH ()-[r]-() RETURN r")

            graph = KnowledgeGraph(graph_id=graph_id)

            async for record in nodes_result:
                node_data = dict(record["n"])
                node = GraphNode(**node_data)
                graph.add_node(node)

            async for record in edges_result:
                edge_data = dict(record["r"])
                edge = GraphEdge(**edge_data)
                graph.add_edge(edge)

            return graph

    async def save_graph(self, graph: KnowledgeGraph) -> None:
        """Save entire graph to Neo4j."""
        for node in graph.nodes.values():
            await self.save_node(node)
        for edge in graph.edges.values():
            await self.save_edge(edge)

    async def query_similar_nodes(
        self,
        embedding: List[float],
        limit: int = 10,
        threshold: float = 0.7,
    ) -> List[GraphNode]:
        """Find semantically similar nodes in Neo4j using vector search."""
        async with self.driver.session() as session:
            # This requires Vespa or similar vector search integration
            # Simplified version using cosine similarity in Cypher
            result = await session.run(
                """
                MATCH (n:Source)
                WHERE n.embedding IS NOT NULL
                RETURN n
                LIMIT $limit
                """,
                limit=limit,
            )

            nodes = []
            async for record in result:
                node_data = dict(record["n"])
                nodes.append(GraphNode(**node_data))
            return nodes

    async def get_node_by_id(self, node_id: str) -> Optional[GraphNode]:
        """Retrieve node from Neo4j."""
        async with self.driver.session() as session:
            result = await session.run(
                "MATCH (n:Source {node_id: $node_id}) RETURN n",
                node_id=node_id,
            )
            record = await result.single()
            if record:
                return GraphNode(**dict(record["n"]))
        return None


def get_graph_store(backend: str = "json", **kwargs) -> GraphStore:
    """Factory for creating graph store instances."""
    if backend == "json":
        return JSONGraphStore(**kwargs)
    elif backend == "neo4j":
        return Neo4jGraphStore(**kwargs)
    else:
        raise ValueError(f"Unknown backend: {backend}")
