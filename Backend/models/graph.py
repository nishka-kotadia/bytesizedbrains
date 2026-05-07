"""
Knowledge Graph data models and types.

Defines:
- GraphNode: Represents a source/entity in the knowledge graph
- GraphEdge: Represents relationships between sources
- KnowledgeGraph: In-memory graph representation with JSON serialization
"""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Set

from pydantic import BaseModel, Field


class RelationshipType(str, Enum):
    """Types of relationships between research sources."""

    CITES = "cites"  # A cites B
    EXTENDS = "extends"  # A extends/builds upon B
    CONTRADICTS = "contradicts"  # A contradicts B
    COMPLEMENTS = "complements"  # A complements B
    BUILDS_UPON = "builds_upon"  # A builds upon B
    REFUTES = "refutes"  # A refutes B
    RELATED = "related"  # Generic relationship


class GraphNode(BaseModel):
    """Represents a research source as a graph node."""

    node_id: str = Field(..., description="Unique identifier (arxiv ID or GitHub URL)")
    title: str
    authors: str
    venue: str
    year: int
    source_type: str  # "paper" or "repo"
    url: str
    abstract: Optional[str] = None
    relevance_score: float = Field(default=0.5, ge=0.0, le=1.0)
    
    # Embedding representation for semantic similarity
    embedding: Optional[List[float]] = Field(
        default=None,
        description="Vector embedding (1536-dim for OpenAI text-embedding-3-small)",
    )
    
    # Metadata
    discovered_at: datetime = Field(default_factory=datetime.utcnow)
    importance_score: float = Field(default=0.5, ge=0.0, le=1.0)
    
    # Keywords/topics
    keywords: List[str] = Field(default_factory=list)
    
    class Config:
        json_schema_extra = {
            "example": {
                "node_id": "2024.01234",
                "title": "Example Paper",
                "authors": "Author A, Author B",
                "venue": "NeurIPS",
                "year": 2024,
                "source_type": "paper",
                "url": "https://arxiv.org/abs/2024.01234",
                "relevance_score": 0.85,
            }
        }


class GraphEdge(BaseModel):
    """Represents a directed relationship between two nodes."""

    edge_id: str = Field(..., description="Unique edge identifier")
    source_node_id: str = Field(..., description="Originating node")
    target_node_id: str = Field(..., description="Target node")
    relationship_type: RelationshipType
    confidence_score: float = Field(default=0.5, ge=0.0, le=1.0)
    
    # Why this relationship exists
    reason: Optional[str] = Field(
        default=None, description="Explanation of the relationship"
    )
    
    # Evidence supporting this edge
    evidence: List[str] = Field(
        default_factory=list, description="Citations or textual evidence"
    )
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_schema_extra = {
            "example": {
                "edge_id": "e_2024.01234->2024.05678",
                "source_node_id": "2024.01234",
                "target_node_id": "2024.05678",
                "relationship_type": "cites",
                "confidence_score": 0.9,
                "reason": "Paper A explicitly cites Paper B in related work",
            }
        }


class ResearchGap(BaseModel):
    """Represents a detected gap in research."""

    gap_id: str
    title: str
    description: str
    affected_nodes: List[str] = Field(
        default_factory=list, description="Node IDs related to this gap"
    )
    missing_intersections: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Unexplored combinations of research areas",
    )
    severity_score: float = Field(default=0.5, ge=0.0, le=1.0)
    discovered_at: datetime = Field(default_factory=datetime.utcnow)


class ResearchIdea(BaseModel):
    """Represents a generated actionable research idea."""

    idea_id: str
    title: str
    description: str
    hypothesis: Optional[str] = None
    
    # Scoring
    impact_score: float = Field(default=0.5, ge=0.0, le=1.0)
    feasibility_score: float = Field(default=0.5, ge=0.0, le=1.0)
    novelty_score: float = Field(default=0.5, ge=0.0, le=1.0)
    
    # Supporting evidence
    supporting_gaps: List[str] = Field(default_factory=list)
    related_nodes: List[str] = Field(default_factory=list)
    next_steps: List[str] = Field(default_factory=list)
    
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class KnowledgeGraph(BaseModel):
    """In-memory knowledge graph with JSON serialization support."""

    graph_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    nodes: Dict[str, GraphNode] = Field(default_factory=dict)
    edges: Dict[str, GraphEdge] = Field(default_factory=dict)
    gaps: Dict[str, ResearchGap] = Field(default_factory=dict)
    ideas: Dict[str, ResearchIdea] = Field(default_factory=dict)
    
    # Statistics
    node_count: int = 0
    edge_count: int = 0

    def add_node(self, node: GraphNode) -> None:
        """Add a node to the graph."""
        self.nodes[node.node_id] = node
        self.node_count = len(self.nodes)

    def add_edge(self, edge: GraphEdge) -> None:
        """Add an edge to the graph."""
        if edge.source_node_id not in self.nodes:
            raise ValueError(f"Source node {edge.source_node_id} not in graph")
        if edge.target_node_id not in self.nodes:
            raise ValueError(f"Target node {edge.target_node_id} not in graph")
        
        self.edges[edge.edge_id] = edge
        self.edge_count = len(self.edges)

    def get_neighbors(self, node_id: str) -> List[str]:
        """Get all nodes connected to a given node."""
        neighbors = set()
        for edge in self.edges.values():
            if edge.source_node_id == node_id:
                neighbors.add(edge.target_node_id)
            elif edge.target_node_id == node_id:
                neighbors.add(edge.source_node_id)
        return list(neighbors)

    def get_incoming_edges(self, node_id: str) -> List[GraphEdge]:
        """Get edges pointing to this node."""
        return [e for e in self.edges.values() if e.target_node_id == node_id]

    def get_outgoing_edges(self, node_id: str) -> List[GraphEdge]:
        """Get edges originating from this node."""
        return [e for e in self.edges.values() if e.source_node_id == node_id]

    def add_gap(self, gap: ResearchGap) -> None:
        """Register a detected gap."""
        self.gaps[gap.gap_id] = gap

    def add_idea(self, idea: ResearchIdea) -> None:
        """Register a generated research idea."""
        self.ideas[idea.idea_id] = idea

    def to_dict(self) -> Dict:
        """Convert graph to dictionary for JSON serialization."""
        return {
            "graph_id": self.graph_id,
            "created_at": self.created_at.isoformat(),
            "statistics": {
                "node_count": self.node_count,
                "edge_count": self.edge_count,
                "gap_count": len(self.gaps),
                "idea_count": len(self.ideas),
            },
            "nodes": {
                nid: node.model_dump(mode="json")
                for nid, node in self.nodes.items()
            },
            "edges": {
                eid: edge.model_dump(mode="json")
                for eid, edge in self.edges.items()
            },
            "gaps": {
                gid: gap.model_dump(mode="json") for gid, gap in self.gaps.items()
            },
            "ideas": {
                iid: idea.model_dump(mode="json")
                for iid, idea in self.ideas.items()
            },
        }

    class Config:
        json_schema_extra = {
            "example": {
                "graph_id": "kg_session_123",
                "nodes": {},
                "edges": {},
                "gaps": {},
                "ideas": {},
            }
        }
