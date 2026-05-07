"""
Idea Generator Agent for actionable research ideas.

Generates novel research hypotheses and directions by:
- Combining findings from different research areas
- Identifying unexplored intersections
- Ranking ideas by impact, feasibility, and novelty
- Providing concrete next steps

Integrates with knowledge graph and LLM reasoning.
"""

import asyncio
import json
import logging
import re
import uuid
from typing import List

from api.llm import get_llm_client
from models.graph import KnowledgeGraph, ResearchGap, ResearchIdea

logger = logging.getLogger(__name__)


class IdeaGeneratorAgent:
    """Generates actionable research ideas from knowledge graph."""

    def __init__(self, llm_client):
        self.llm_client = llm_client

    async def generate_ideas(
        self,
        graph: KnowledgeGraph,
        gaps: List[ResearchGap],
        original_query: str,
        config,
    ) -> List[ResearchIdea]:
        """
        Generate actionable research ideas based on:
        1. Identified gaps
        2. Source findings
        3. Intersection analysis
        4. Novelty scoring

        Returns top 3-5 ideas ranked by impact/feasibility/novelty.
        """
        ideas = []

        # Generate ideas from gaps
        gap_ideas = await self._generate_ideas_from_gaps(gaps, graph)
        ideas.extend(gap_ideas)

        # Generate ideas from source intersections
        intersection_ideas = await self._generate_intersection_ideas(graph, original_query)
        ideas.extend(intersection_ideas)

        # Generate ideas from trend analysis
        if len(ideas) < 3:
            trend_ideas = await self._generate_trend_ideas(graph, original_query)
            ideas.extend(trend_ideas)

        # Rank and filter
        ideas = self._rank_ideas(ideas)
        ideas = ideas[:5]  # Top 5 ideas

        logger.info(f"Generated {len(ideas)} research ideas")
        return ideas

    async def _generate_ideas_from_gaps(
        self, gaps: List[ResearchGap], graph: KnowledgeGraph
    ) -> List[ResearchIdea]:
        """Convert research gaps into concrete ideas. LLM errors propagate up."""
        ideas = []
        for gap in gaps:
            affected_titles = [
                graph.nodes[nid].title for nid in gap.affected_nodes if nid in graph.nodes
            ]
            prompt = f"""
            You are a research visionary. Based on this research gap:
            Gap Title: {gap.title}
            Description: {gap.description}
            Affected Research Areas: {', '.join(affected_titles)}
            Generate ONE concrete, actionable research idea that addresses this gap.
            Format as JSON:
            {{
                "title": "Concise idea title",
                "hypothesis": "Testable hypothesis",
                "description": "2-3 sentence detailed description",
                "next_steps": ["Step 1", "Step 2", "Step 3"],
                "expected_impact": "high|medium|low",
                "feasibility": "high|medium|low",
                "novelty": "high|medium|low"
            }}
            """
            from api.llm import LLM_MODEL, LLM_PROVIDER
            if LLM_PROVIDER == "anthropic":
                resp = await self.llm_client.messages.create(
                    model=LLM_MODEL, max_tokens=400,
                    system="You are a research ideation expert.",
                    messages=[{"role": "user", "content": prompt}],
                )
                response = next((b.text for b in resp.content if hasattr(b, "text")), "")
            else:
                resp = await self.llm_client.chat.completions.create(
                    model=LLM_MODEL,
                    messages=[
                        {"role": "system", "content": "You are a research ideation expert."},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.8, max_tokens=400,
                )
                response = resp.choices[0].message.content or ""

            # Only catch JSON parse errors — LLM errors propagate
            try:
                json_match = re.search(r"\{.*\}", response, re.DOTALL)
                if json_match:
                    idea_data = json.loads(json_match.group())
                    ideas.append(ResearchIdea(
                        idea_id=f"idea_{uuid.uuid4().hex[:8]}",
                        title=idea_data.get("title", ""),
                        description=idea_data.get("description", ""),
                        hypothesis=idea_data.get("hypothesis"),
                        impact_score=self._score_from_text(idea_data.get("expected_impact", "medium")),
                        feasibility_score=self._score_from_text(idea_data.get("feasibility", "medium")),
                        novelty_score=self._score_from_text(idea_data.get("novelty", "medium")),
                        supporting_gaps=[gap.gap_id],
                        related_nodes=gap.affected_nodes,
                        next_steps=idea_data.get("next_steps", []),
                    ))
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning("Gap idea parse error for gap=%s: %s", gap.gap_id, e)
        return ideas

    async def _generate_intersection_ideas(
        self, graph: KnowledgeGraph, original_query: str
    ) -> List[ResearchIdea]:
        """Generate ideas by exploring topic intersections. LLM errors propagate up."""
        ideas = []
        topic_counts = {}
        for node in graph.nodes.values():
            for keyword in node.keywords:
                topic_counts[keyword] = topic_counts.get(keyword, 0) + 1
        topics = [t[0] for t in sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)[:6]]
        if len(topics) < 2:
            return ideas

        prompt = f"""
        Based on research in these areas: {', '.join(topics)}
        Original research query: {original_query}
        Generate 2-3 novel research ideas combining multiple topics.
        Format as JSON:
        {{
            "ideas": [
                {{
                    "title": "...", "hypothesis": "...", "description": "...",
                    "combines_topics": ["topic1", "topic2"],
                    "next_steps": ["...", "...", "..."],
                    "estimated_effort": "months|weeks",
                    "potential_impact": "high|medium|low"
                }}
            ]
        }}
        """
        from api.llm import LLM_MODEL, LLM_PROVIDER
        if LLM_PROVIDER == "anthropic":
            resp = await self.llm_client.messages.create(
                model=LLM_MODEL, max_tokens=800,
                system="You are a creative research strategist.",
                messages=[{"role": "user", "content": prompt}],
            )
            response = next((b.text for b in resp.content if hasattr(b, "text")), "")
        else:
            resp = await self.llm_client.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": "You are a creative research strategist."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.9, max_tokens=800,
            )
            response = resp.choices[0].message.content or ""

        try:
            json_match = re.search(r"\{.*\}", response, re.DOTALL)
            if json_match:
                for idea_data in json.loads(json_match.group()).get("ideas", []):
                    ideas.append(ResearchIdea(
                        idea_id=f"idea_{uuid.uuid4().hex[:8]}",
                        title=idea_data.get("title", ""),
                        description=idea_data.get("description", ""),
                        hypothesis=idea_data.get("hypothesis"),
                        impact_score=self._score_from_text(idea_data.get("potential_impact", "medium")),
                        novelty_score=0.85,
                        feasibility_score=self._effort_to_feasibility(idea_data.get("estimated_effort", "months")),
                        next_steps=idea_data.get("next_steps", []),
                    ))
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("Intersection idea parse error: %s", e)
        return ideas

    async def _generate_trend_ideas(
        self, graph: KnowledgeGraph, original_query: str
    ) -> List[ResearchIdea]:
        """Generate ideas based on emerging trends. LLM errors propagate up."""
        ideas = []
        recent_nodes = [n for n in graph.nodes.values() if n.year >= 2023]
        if not recent_nodes:
            return ideas

        from collections import Counter
        trending_str = ", ".join(t[0] for t in Counter(
            kw for n in recent_nodes for kw in n.keywords
        ).most_common(5))

        prompt = f"""
        Recent research trends: {trending_str}
        Original query: {original_query}
        Generate 1-2 forward-looking research ideas building on these trends.
        Format as JSON:
        {{
            "ideas": [
                {{
                    "title": "...", "hypothesis": "...", "description": "...",
                    "why_timely": "...",
                    "next_steps": ["...", "...", "..."],
                    "timeline": "1-2 years|2-3 years|3+ years"
                }}
            ]
        }}
        """
        from api.llm import LLM_MODEL, LLM_PROVIDER
        if LLM_PROVIDER == "anthropic":
            resp = await self.llm_client.messages.create(
                model=LLM_MODEL, max_tokens=500,
                system="You are a research foresight expert.",
                messages=[{"role": "user", "content": prompt}],
            )
            response = next((b.text for b in resp.content if hasattr(b, "text")), "")
        else:
            resp = await self.llm_client.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": "You are a research foresight expert."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7, max_tokens=500,
            )
            response = resp.choices[0].message.content or ""

        try:
            json_match = re.search(r"\{.*\}", response, re.DOTALL)
            if json_match:
                for idea_data in json.loads(json_match.group()).get("ideas", []):
                    ideas.append(ResearchIdea(
                        idea_id=f"idea_{uuid.uuid4().hex[:8]}",
                        title=idea_data.get("title", ""),
                        description=idea_data.get("description", ""),
                        hypothesis=idea_data.get("hypothesis"),
                        impact_score=0.8, novelty_score=0.7, feasibility_score=0.6,
                        next_steps=idea_data.get("next_steps", []),
                    ))
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("Trend idea parse error: %s", e)
        return ideas

    @staticmethod
    def _rank_ideas(ideas: List[ResearchIdea]) -> List[ResearchIdea]:
        """Rank ideas by combined impact/feasibility/novelty score."""
        def combined_score(idea: ResearchIdea) -> float:
            return idea.impact_score * 0.5 + idea.novelty_score * 0.3 + idea.feasibility_score * 0.2

        return sorted(ideas, key=combined_score, reverse=True)

    @staticmethod
    def _score_from_text(text: str) -> float:
        """Convert text rating to numeric score."""
        text = text.lower().strip()
        if "high" in text:
            return 0.85
        elif "medium" in text:
            return 0.6
        elif "low" in text:
            return 0.35
        return 0.5

    @staticmethod
    def _effort_to_feasibility(effort: str) -> float:
        """Convert effort estimate to feasibility score."""
        effort = effort.lower().strip()
        if "week" in effort:
            return 0.9  # Quick = feasible
        elif "month" in effort:
            return 0.7
        else:
            return 0.4  # Long-term = less immediately feasible

    def get_importance_score(self, idea: ResearchIdea) -> float:
        """Calculate overall importance score for an idea."""
        return (
            idea.impact_score * 0.5
            + idea.novelty_score * 0.3
            + idea.feasibility_score * 0.2
        )
