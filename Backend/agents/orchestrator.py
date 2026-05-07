"""
Orchestrator for the Multi-Agent Research Intelligence System.

Every agent invocation is routed through the OpenClawAdapter:
  - Protocol message created and logged for each call
  - Execution mode (EDGE / CLOUD) determined from the registry
  - Per-agent timeout enforced; failed agents marked unavailable
  - Full dispatch trace available via openclaw.get_registry_summary()

Pipeline:
    Decomposer → Planner → Search → Analyzer →
    GraphBuilder → GapDetector → IdeaGenerator → Synthesizer
"""

import asyncio
import logging
from datetime import datetime, timezone

import db.database as db
from adapters.openclaw_adapter import AgentCapability, ExecutionMode, OpenClawAdapter
from agents.analyzer import AnalyzerAgent
from agents.decomposer import DecomposerAgent
from agents.gap_detector import GapDetectorAgent
from agents.idea_generator import IdeaGeneratorAgent
from agents.planner import PlannerAgent
from agents.search import SearchAgent
from agents.synthesizer import SynthesizerAgent
from api.llm import LLM_MODEL
from knowledge_graph.embeddings import EmbeddingService
from knowledge_graph.graph_store import get_graph_store
from models.config import Config, DepthLevel
from models.graph import GraphEdge, GraphNode, KnowledgeGraph, RelationshipType
from models.session import ResearchSession, SessionStatus
from models.source import Source

logger = logging.getLogger(__name__)

STEPS = [
    (0, "decompose",    "Decomposing query into sub-questions"),
    (1, "plan",         "Building research plan"),
    (2, "search",       "Searching academic databases & web"),
    (3, "analyze",      "Analyzing and cross-referencing"),
    (4, "build_graph",  "Building knowledge graph with embeddings"),
    (5, "detect_gaps",  "Detecting research gaps and missing links"),
    (6, "generate_ideas","Generating actionable research ideas"),
    (7, "synthesize",   "Synthesizing research report"),
]

DEPTH_MAX_SOURCES: dict[DepthLevel, int] = {
    DepthLevel.quick:    10,
    DepthLevel.standard: 20,
    DepthLevel.deep:     50,
}

_PIPELINE_TIMEOUT_SECONDS = 480  # 8 minutes


class Orchestrator:
    """Runs the full research pipeline, routing every agent through OpenClaw."""

    def __init__(self, llm_client) -> None:
        self.llm_client = llm_client
        self.openclaw = OpenClawAdapter("config/openclaw_config.yaml")
        try:
            self.embedding_service = EmbeddingService(provider="auto")
            logger.info("Orchestrator: embedding service initialised provider=%s",
                        type(self.embedding_service.provider).__name__)
        except Exception as exc:
            logger.warning("Orchestrator: embedding service unavailable (%s) — semantic edges disabled", exc)
            self.embedding_service = None
        self.graph_store = get_graph_store("json")
        self._register_agents()

    # ── Agent registration ────────────────────────────────────────────────────

    def _register_agents(self) -> None:
        """Register all pipeline agents with the OpenClaw adapter."""
        agents = [
            # (agent_id,        capability,                      mode,                  model,        timeout)
            ("decomposer",     AgentCapability.DECOMPOSE,       ExecutionMode.EDGE,    LLM_MODEL, 60),
            ("planner",        AgentCapability.PLAN,            ExecutionMode.EDGE,    LLM_MODEL, 60),
            ("search",         AgentCapability.SEARCH,          ExecutionMode.EDGE,    LLM_MODEL, 120),
            ("analyzer",       AgentCapability.ANALYZE,         ExecutionMode.CLOUD,   LLM_MODEL, 120),
            ("gap_detector",   AgentCapability.DETECT_GAPS,     ExecutionMode.CLOUD,   LLM_MODEL, 180),
            ("idea_generator", AgentCapability.GENERATE_IDEAS,  ExecutionMode.CLOUD,   LLM_MODEL, 180),
            ("synthesizer",    AgentCapability.SYNTHESIZE,      ExecutionMode.EDGE,    LLM_MODEL, 120),
        ]
        for agent_id, capability, mode, model, timeout in agents:
            self.openclaw.register_agent(agent_id, capability, mode, model, timeout)

    # ── Pipeline entry point ──────────────────────────────────────────────────

    async def run_pipeline(self, session: ResearchSession, queue: asyncio.Queue) -> None:
        session.status = SessionStatus.running
        logger.info(
            "Orchestrator: pipeline started session_id=%s query=%r  "
            "openclaw_registry=%s",
            session.session_id, session.query,
            self.openclaw.get_registry_summary()["total_agents"],
        )
        try:
            await asyncio.wait_for(
                self._run_pipeline_inner(session, queue),
                timeout=_PIPELINE_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            msg = f"Research pipeline timed out after {_PIPELINE_TIMEOUT_SECONDS}s."
            logger.error("Orchestrator: timeout session_id=%s", session.session_id)
            session.status = SessionStatus.error
            session.error_msg = msg
            await queue.put({"type": "pipeline_error", "data": {"error": msg}})
        except Exception as exc:
            logger.error(
                "Orchestrator: unrecoverable error session_id=%s: %s",
                session.session_id, exc, exc_info=True,
            )
            session.status = SessionStatus.error
            session.error_msg = str(exc)
            await queue.put({"type": "pipeline_error", "data": {"error": str(exc)}})
            raise

    # ── Inner pipeline ────────────────────────────────────────────────────────

    async def _run_pipeline_inner(self, session: ResearchSession, queue: asyncio.Queue) -> None:
        cfg = self._apply_depth_limit(session.config)
        kg  = KnowledgeGraph(graph_id=f"kg_{session.session_id}")

        # ── Step 0: Decompose ─────────────────────────────────────────────────
        idx, name, label = STEPS[0]
        await self._push_step_start(queue, idx, name, label)
        decomposer = DecomposerAgent(self.llm_client)
        sub_questions = await self.openclaw.dispatch(
            AgentCapability.DECOMPOSE,
            lambda: decomposer.decompose(session.query),
            {"query_length": len(session.query)},
        )
        await self._push_step_complete(queue, idx, name, f"Generated {len(sub_questions)} sub-question(s).")
        logger.info("Orchestrator: decompose done sub_questions=%d", len(sub_questions))

        # ── Step 1: Plan ──────────────────────────────────────────────────────
        idx, name, label = STEPS[1]
        await self._push_step_start(queue, idx, name, label)
        planner = PlannerAgent(self.llm_client)
        search_tasks = await self.openclaw.dispatch(
            AgentCapability.PLAN,
            lambda: planner.plan(sub_questions, cfg),
            {"sub_questions": len(sub_questions), "max_sources": cfg.maxSources},
        )
        await self._push_step_complete(queue, idx, name, f"Created {len(search_tasks)} search task(s).")
        logger.info("Orchestrator: plan done tasks=%d", len(search_tasks))

        # ── Step 2: Search ────────────────────────────────────────────────────
        idx, name, label = STEPS[2]
        await self._push_step_start(queue, idx, name, label)
        search_agent = SearchAgent(self.llm_client, session.query, self.embedding_service)
        sources = await self.openclaw.dispatch(
            AgentCapability.SEARCH,
            lambda: search_agent.search(search_tasks, cfg, queue),
            {"tasks": len(search_tasks)},
        )
        await self._push_step_complete(queue, idx, name, f"Found {len(sources)} source(s).")
        logger.info("Orchestrator: search done sources=%d", len(sources))

        # ── Step 3: Analyze ───────────────────────────────────────────────────
        idx, name, label = STEPS[3]
        await self._push_step_start(queue, idx, name, label)
        analyzer = AnalyzerAgent(self.llm_client)
        analyzed = await self.openclaw.dispatch(
            AgentCapability.ANALYZE,
            lambda: analyzer.analyze(sources, cfg),
            {"sources": len(sources)},
        )
        await self._push_step_complete(queue, idx, name, f"Analyzed {len(analyzed)} source(s).")
        logger.info("Orchestrator: analyze done analyzed=%d", len(analyzed))

        # ── Step 4: Build knowledge graph ─────────────────────────────────────
        idx, name, label = STEPS[4]
        await self._push_step_start(queue, idx, name, label)
        kg = await self._build_knowledge_graph(analyzed, kg, session.query)
        await self._push_step_complete(
            queue, idx, name,
            f"Built graph: {kg.node_count} nodes, {kg.edge_count} edges.",
        )
        logger.info("Orchestrator: graph built nodes=%d edges=%d", kg.node_count, kg.edge_count)

        # ── Step 5: Detect gaps ───────────────────────────────────────────────
        idx, name, label = STEPS[5]
        await self._push_step_start(queue, idx, name, label)
        logger.info("Orchestrator: starting gap detection nodes=%d edges=%d",
                    kg.node_count, kg.edge_count)
        gap_detector = GapDetectorAgent(self.llm_client, self.embedding_service)
        try:
            gaps = await self.openclaw.dispatch(
                AgentCapability.DETECT_GAPS,
                lambda: gap_detector.detect_gaps(kg, session.query, cfg),
                {"nodes": kg.node_count, "edges": kg.edge_count},
            )
        except Exception as exc:
            logger.error("Orchestrator: gap detection failed: %s", exc, exc_info=True)
            gaps = []
        await self._push_step_complete(queue, idx, name, f"Detected {len(gaps)} research gap(s).")
        logger.info("Orchestrator: gaps detected gaps=%d", len(gaps))

        # ── Step 6: Generate ideas ────────────────────────────────────────────
        idx, name, label = STEPS[6]
        await self._push_step_start(queue, idx, name, label)
        logger.info("Orchestrator: starting idea generation gaps=%d nodes=%d",
                    len(gaps), kg.node_count)
        idea_gen = IdeaGeneratorAgent(self.llm_client)
        try:
            ideas = await self.openclaw.dispatch(
                AgentCapability.GENERATE_IDEAS,
                lambda: idea_gen.generate_ideas(kg, gaps, session.query, cfg),
                {"gaps": len(gaps)},
            )
        except Exception as exc:
            logger.error("Orchestrator: idea generation failed: %s", exc, exc_info=True)
            ideas = []
        await self._push_step_complete(queue, idx, name, f"Generated {len(ideas)} idea(s).")
        logger.info("Orchestrator: ideas generated ideas=%d", len(ideas))
        # ── Step 7: Synthesize ────────────────────────────────────────────────
        idx, name, label = STEPS[7]
        await self._push_step_start(queue, idx, name, label)
        synthesizer = SynthesizerAgent(self.llm_client)
        try:
            report = await self.openclaw.dispatch(
                AgentCapability.SYNTHESIZE,
                lambda: synthesizer.synthesize(analyzed, cfg),
                {"sources": len(analyzed), "format": cfg.format.value},
            )
        except Exception as exc:
            logger.warning("Orchestrator: synthesis failed (degrading gracefully): %s", exc)
            # Build a minimal report from sources so the user gets something useful
            lines = ["## Research Results\n\nFull synthesis unavailable (rate limit reached). Sources found:\n"]
            for s in analyzed:
                lines.append(f"- **[{s.title}]({s.url})** — {s.authors} ({s.year})")
                if s.key_findings:
                    lines.append(f"  - {s.key_findings}")
            report = "\n".join(lines)
        await self._push_step_complete(queue, idx, name, "Research report synthesized.")
        logger.info("Orchestrator: synthesis done")

        # ── Persist & emit ────────────────────────────────────────────────────
        session.sources      = analyzed
        session.report       = report if isinstance(report, str) else str(report)
        session.status       = SessionStatus.complete
        session.completed_at = datetime.now(tz=timezone.utc)

        # Persist gaps and ideas into the graph so they appear in the JSON store
        for gap in gaps:
            kg.add_gap(gap)
        for idea in ideas:
            kg.add_idea(idea)

        await self.graph_store.save_graph(kg)

        # Store gaps, ideas, and graph on the session for DB persistence
        session.gaps            = [g.model_dump(mode="json") for g in gaps]
        session.ideas           = [i.model_dump(mode="json") for i in ideas]
        session.knowledge_graph = kg.to_dict()

        await db.save_session(session)

        # Log final OpenClaw registry state
        summary = self.openclaw.get_registry_summary()
        logger.info(
            "Orchestrator: pipeline_complete session_id=%s  "
            "openclaw total_calls=%d total_failures=%d",
            session.session_id, summary["total_calls"], summary["total_failures"],
        )

        await queue.put({
            "type": "pipeline_complete",
            "data": {
                "report":          report,
                "sources":         [s.model_dump() for s in analyzed],
                "gaps":            [g.model_dump(mode="json") for g in gaps],
                "ideas":           [i.model_dump(mode="json") for i in ideas],
                "knowledge_graph": kg.to_dict(),
                "openclaw":        summary,          # expose adapter state to frontend
            },
        })

    # ── Knowledge graph builder ───────────────────────────────────────────────

    async def _build_knowledge_graph(
        self,
        sources: list[Source],
        graph: KnowledgeGraph,
        original_query: str,
    ) -> KnowledgeGraph:
        for source in sources:
            node = GraphNode(
                node_id=source.id,
                title=source.title,
                authors=source.authors,
                venue=source.venue,
                year=source.year,
                source_type=source.type.value,
                url=source.url,
                abstract=source.abstract,
                embedding=source.embedding,
                relevance_score=source.relevance / 100.0,
                keywords=[],
            )
            graph.add_node(node)

        if len(graph.nodes) > 1:
            await self._create_semantic_edges(graph)

        await self._extract_keywords(graph)
        return graph

    async def _create_semantic_edges(self, graph: KnowledgeGraph) -> None:
        import math
        import re

        node_list = list(graph.nodes.items())

        # ── Embedding-based edges (when available) ────────────────────────────
        nodes_with_embeddings = [(nid, node) for nid, node in node_list if node.embedding]
        if len(nodes_with_embeddings) >= 2:
            similarity_threshold = 0.25
            for i, (id_a, node_a) in enumerate(nodes_with_embeddings):
                for id_b, node_b in nodes_with_embeddings[i + 1:]:
                    similarity = EmbeddingService.cosine_similarity(node_a.embedding, node_b.embedding)
                    if similarity >= similarity_threshold:
                        edge = GraphEdge(
                            edge_id=f"e_{id_a}_{id_b}_related",
                            source_node_id=id_a,
                            target_node_id=id_b,
                            relationship_type=RelationshipType.RELATED,
                            confidence_score=float(similarity),
                            reason=f"Semantically similar (score: {similarity:.2f})",
                            evidence=[],
                        )
                        try:
                            graph.add_edge(edge)
                        except ValueError:
                            pass
            logger.info(
                "Orchestrator: embedding edges created edges=%d", graph.edge_count
            )
            return  # embedding edges done — skip keyword fallback

        # ── Keyword-overlap fallback (no embeddings available) ────────────────
        logger.info(
            "Orchestrator: no embeddings found — building keyword-overlap edges"
        )
        stopwords = {
            'the','a','an','of','in','for','on','with','and','or','to','is','are',
            'that','this','from','by','as','at','we','our','their','its','be','been',
            'have','has','had','was','were','will','would','can','could','should',
            'may','might','also','which','when','where','how','what','who','than',
            'more','most','such','these','those','into','over','after','between',
            'through','during','using','used','based','show','shows','shown',
            'propose','proposed','present','presented','paper','study','work',
            'method','approach','model','result','results','data','analysis',
        }

        def keywords_for(node) -> set:
            text = f"{node.title} {node.abstract or ''}"
            words = re.findall(r'\b[a-zA-Z]{4,}\b', text.lower())
            return {w for w in words if w not in stopwords}

        node_keywords = {nid: keywords_for(node) for nid, node in node_list}

        for i, (id_a, node_a) in enumerate(node_list):
            kw_a = node_keywords[id_a]
            if not kw_a:
                continue
            for id_b, node_b in node_list[i + 1:]:
                kw_b = node_keywords[id_b]
                if not kw_b:
                    continue
                # Jaccard similarity
                intersection = len(kw_a & kw_b)
                union = len(kw_a | kw_b)
                jaccard = intersection / union if union else 0.0
                if jaccard >= 0.08:  # at least ~8% keyword overlap
                    # Determine relationship type by year
                    if node_a.year and node_b.year and abs(node_a.year - node_b.year) <= 1:
                        rel = RelationshipType.COMPLEMENTS
                    else:
                        rel = RelationshipType.RELATED
                    edge = GraphEdge(
                        edge_id=f"e_{id_a}_{id_b}_kw",
                        source_node_id=id_a,
                        target_node_id=id_b,
                        relationship_type=rel,
                        confidence_score=round(min(jaccard * 3, 1.0), 2),
                        reason=f"Keyword overlap ({intersection} shared terms, Jaccard={jaccard:.2f})",
                        evidence=[],
                    )
                    try:
                        graph.add_edge(edge)
                    except ValueError:
                        pass

        logger.info(
            "Orchestrator: keyword-overlap edges created edges=%d", graph.edge_count
        )

    async def _extract_keywords(self, graph: KnowledgeGraph) -> None:
        """Extract keywords from title + abstract using TF-IDF-style frequency scoring."""
        import re
        from collections import Counter

        stopwords = {
            'the','a','an','of','in','for','on','with','and','or','to','is','are',
            'that','this','from','by','as','at','we','our','their','its','be','been',
            'have','has','had','was','were','will','would','can','could','should',
            'may','might','also','which','when','where','how','what','who','than',
            'more','most','such','these','those','into','over','after','between',
            'through','during','using','used','based','show','shows','shown',
            'propose','proposed','present','presented','paper','study','work',
            'method','approach','model','result','results','data','analysis',
        }

        # Build corpus-level word frequencies for IDF weighting
        corpus_freq: Counter = Counter()
        node_texts: dict[str, str] = {}
        for nid, node in graph.nodes.items():
            text = f"{node.title} {node.abstract or ''}"
            words = re.findall(r'\b[a-zA-Z]{4,}\b', text.lower())
            clean = [w for w in words if w not in stopwords]
            node_texts[nid] = " ".join(clean)
            corpus_freq.update(set(clean))  # document frequency

        n_docs = max(len(graph.nodes), 1)

        for nid, node in graph.nodes.items():
            words = node_texts[nid].split()
            if not words:
                node.keywords = []
                continue
            # TF: term frequency within this node's text
            tf = Counter(words)
            # TF-IDF score: tf * log(n_docs / doc_freq)
            import math
            scores = {
                w: tf[w] * math.log(n_docs / corpus_freq[w])
                for w in tf
            }
            node.keywords = [w for w, _ in sorted(scores.items(), key=lambda x: x[1], reverse=True)][:8]

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _apply_depth_limit(config: Config) -> Config:
        depth_max = DEPTH_MAX_SOURCES[config.depth]
        if config.maxSources == depth_max:
            return config
        return config.model_copy(update={"maxSources": depth_max})

    @staticmethod
    async def _push_step_start(queue: asyncio.Queue, idx: int, name: str, label: str) -> None:
        await queue.put({"type": "step_start",    "data": {"step_name": name, "step_index": idx, "label": label}})

    @staticmethod
    async def _push_step_complete(queue: asyncio.Queue, idx: int, name: str, summary: str) -> None:
        await queue.put({"type": "step_complete", "data": {"step_name": name, "step_index": idx, "summary": summary}})
