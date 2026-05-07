"""
Planner Agent for the Multi-Agent Research Intelligence System.

Converts a list of sub-questions into a prioritized list of SearchTask objects
by calling the configured LLM. Deduplicates semantically equivalent tasks,
caps the total at config.maxSources * 2, and returns tasks sorted by priority
descending.
"""

import json
import logging
import re
import string

from api.llm import LLM_MODEL, LLM_PROVIDER
from models.config import Config
from models.search import SearchTarget, SearchTask

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "Given research sub-questions, output a JSON array of search tasks. "
    "Each task: {sub_question, target (arxiv|github), query, priority (1-10)}. "
    "Max 6 tasks total. Output ONLY the JSON array."
)


class PlannerAgent:
    """Generates a prioritized search plan from decomposed sub-questions."""

    def __init__(self, llm_client) -> None:
        self.llm_client = llm_client

    async def plan(self, sub_questions: list[str], config: Config) -> list[SearchTask]:
        """Generate a prioritized list of SearchTask objects from sub-questions."""
        cap = config.maxSources * 2

        try:
            raw_text = await self._call_llm(sub_questions)
            tasks = self._parse_tasks(raw_text)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "PlannerAgent LLM call failed (%s); falling back to simple task generation.",
                exc,
            )
            tasks = self._fallback_tasks(sub_questions)

        if not tasks:
            logger.warning(
                "PlannerAgent received empty task list from LLM; falling back to simple tasks."
            )
            tasks = self._fallback_tasks(sub_questions)

        tasks = self._deduplicate(tasks)
        tasks = tasks[:cap]
        tasks.sort(key=lambda t: t.priority, reverse=True)

        logger.info(
            "PlannerAgent produced %d search tasks (cap=%d).", len(tasks), cap
        )
        return tasks

    async def _call_llm(self, sub_questions: list[str]) -> str:
        """Call the LLM and return the raw response text."""
        numbered = "\n".join(
            f"{i + 1}. {q}" for i, q in enumerate(sub_questions)
        )
        user_message = (
            f"Generate search tasks for the following research sub-questions:\n\n"
            f"{numbered}"
        )

        if LLM_PROVIDER in ("openai", "groq"):
            response = await self.llm_client.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.3,
                max_tokens=400,
            )
            return response.choices[0].message.content or ""

        elif LLM_PROVIDER == "anthropic":
            response = await self.llm_client.messages.create(
                model=LLM_MODEL,
                max_tokens=2048,
                system=_SYSTEM_PROMPT,
                messages=[
                    {"role": "user", "content": user_message},
                ],
            )
            for block in response.content:
                if hasattr(block, "text"):
                    return block.text
            return ""

        else:
            raise ValueError(
                f"Unsupported LLM_PROVIDER: {LLM_PROVIDER!r}. "
                "Supported providers are 'openai' and 'anthropic'."
            )

    def _parse_tasks(self, text: str) -> list[SearchTask]:
        """Parse a JSON array of task dicts from the LLM response."""
        stripped = text.strip()
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
        stripped = stripped.strip()

        try:
            data = json.loads(stripped)
        except json.JSONDecodeError as exc:
            logger.warning("PlannerAgent failed to parse LLM JSON response: %s", exc)
            raise

        if not isinstance(data, list):
            logger.warning(
                "PlannerAgent expected a JSON array but got %s.", type(data).__name__
            )
            return []

        tasks: list[SearchTask] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            try:
                task = SearchTask(
                    sub_question=str(item.get("sub_question", "")),
                    target=SearchTarget(item.get("target", "arxiv")),
                    query=str(item.get("query", "")),
                    priority=int(item.get("priority", 5)),
                )
                tasks.append(task)
            except Exception as exc:  # noqa: BLE001
                logger.warning("PlannerAgent skipping malformed task %r: %s", item, exc)

        return tasks

    @staticmethod
    def _fallback_tasks(sub_questions: list[str]) -> list[SearchTask]:
        """Generate simple fallback tasks when LLM parsing fails."""
        tasks: list[SearchTask] = []
        for question in sub_questions:
            tasks.append(
                SearchTask(
                    sub_question=question,
                    target=SearchTarget.arxiv,
                    query=question,
                    priority=5,
                )
            )
            tasks.append(
                SearchTask(
                    sub_question=question,
                    target=SearchTarget.github,
                    query=question,
                    priority=5,
                )
            )
        return tasks

    @staticmethod
    def _normalize_query(query: str) -> str:
        """Normalize a query string for deduplication comparison."""
        lowered = query.lower()
        no_punct = lowered.translate(str.maketrans("", "", string.punctuation))
        collapsed = re.sub(r"\s+", " ", no_punct).strip()
        return collapsed

    def _deduplicate(self, tasks: list[SearchTask]) -> list[SearchTask]:
        """Remove tasks whose normalized query matches an already-seen query."""
        seen: set[str] = set()
        unique: list[SearchTask] = []
        for task in tasks:
            key = self._normalize_query(task.query)
            if key not in seen:
                seen.add(key)
                unique.append(task)
        return unique
