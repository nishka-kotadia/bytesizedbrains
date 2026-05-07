"""
Decomposer Agent for the Multi-Agent Research Intelligence System.

Breaks a broad research query into 3–7 focused sub-questions using the
configured LLM provider. Validates sub-question length, retries once on
insufficient output, and falls back to the original query after two failures.
"""

import logging
import re

from api.llm import LLM_MODEL, LLM_PROVIDER

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "Break the research query into 3 focused sub-questions. "
    "Output ONLY a numbered list, no preamble."
)

_MAX_SUB_QUESTION_LEN = 200
_MIN_SUB_QUESTIONS = 3
_MAX_SUB_QUESTIONS = 7


class DecomposerAgent:
    """Decomposes a research query into focused sub-questions via an LLM."""

    def __init__(self, llm_client) -> None:
        """
        Args:
            llm_client: An async LLM client returned by ``api.llm.get_llm_client()``.
                        Supports both ``openai.AsyncOpenAI`` and
                        ``anthropic.AsyncAnthropic`` clients.
        """
        self.llm_client = llm_client

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def decompose(self, query: str) -> list[str]:
        """Break *query* into 3–7 focused sub-questions.

        Retries once if the first LLM call produces fewer than 3 valid
        sub-questions. Falls back to ``[query]`` after two failed attempts
        and logs a warning.

        Args:
            query: The raw research query string.

        Returns:
            A list of sub-question strings (each ≤ 200 characters).
            Guaranteed to be non-empty; may be ``[query]`` on fallback.
        """
        for attempt in range(1, 3):  # attempts 1 and 2
            try:
                raw_text = await self._call_llm(query)
                sub_questions = self._parse_sub_questions(raw_text)
                valid = self._validate(sub_questions)
                if len(valid) >= _MIN_SUB_QUESTIONS:
                    return valid[:_MAX_SUB_QUESTIONS]
                logger.warning(
                    "DecomposerAgent attempt %d produced only %d valid "
                    "sub-question(s) for query %r — expected at least %d.",
                    attempt,
                    len(valid),
                    query,
                    _MIN_SUB_QUESTIONS,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "DecomposerAgent attempt %d raised an exception: %s",
                    attempt,
                    exc,
                )

        # Both attempts failed — fall back to the original query.
        logger.warning(
            "DecomposerAgent failed to produce at least %d sub-questions "
            "after 2 attempts for query %r. Falling back to original query.",
            _MIN_SUB_QUESTIONS,
            query,
        )
        return [query]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _call_llm(self, query: str) -> str:
        """Call the LLM and return the raw response text.

        Dispatches to the correct provider API based on ``LLM_PROVIDER``.

        Args:
            query: The research query to decompose.

        Returns:
            The raw text content of the LLM response.

        Raises:
            ValueError: If ``LLM_PROVIDER`` is not a supported provider.
        """
        user_message = (
            f"Break this research query into 3–7 focused sub-questions:\n\n{query}"
        )

        if LLM_PROVIDER in ("openai", "groq"):
            response = await self.llm_client.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.7,
                max_tokens=200,
            )
            return response.choices[0].message.content or ""

        elif LLM_PROVIDER == "anthropic":
            response = await self.llm_client.messages.create(
                model=LLM_MODEL,
                max_tokens=1024,
                system=_SYSTEM_PROMPT,
                messages=[
                    {"role": "user", "content": user_message},
                ],
            )
            # Anthropic returns a list of content blocks; grab the first text block.
            for block in response.content:
                if hasattr(block, "text"):
                    return block.text
            return ""

        else:
            raise ValueError(
                f"Unsupported LLM_PROVIDER: {LLM_PROVIDER!r}. "
                "Supported providers are 'openai' and 'anthropic'."
            )

    @staticmethod
    def _parse_sub_questions(text: str) -> list[str]:
        """Extract sub-questions from a numbered or bulleted list in *text*.

        Accepts lines that start with:
        - A digit followed by ``.`` or ``)`` (e.g. ``1.``, ``2)``)
        - A bullet character (``-``, ``*``, ``•``)

        Args:
            text: Raw LLM response text.

        Returns:
            A list of stripped sub-question strings (may be empty).
        """
        sub_questions: list[str] = []
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            # Match numbered items: "1.", "1)", "1 ." etc.
            match = re.match(r"^\d+[\.\)]\s*(.*)", stripped)
            if match:
                content = match.group(1).strip()
                if content:
                    sub_questions.append(content)
                continue
            # Match bullet items: "- ...", "* ...", "• ..."
            match = re.match(r"^[-*•]\s+(.*)", stripped)
            if match:
                content = match.group(1).strip()
                if content:
                    sub_questions.append(content)
        return sub_questions

    @staticmethod
    def _validate(sub_questions: list[str]) -> list[str]:
        """Filter out sub-questions that exceed the maximum character limit.

        Args:
            sub_questions: Parsed sub-question strings.

        Returns:
            Only those sub-questions whose length is ≤ 200 characters.
        """
        return [sq for sq in sub_questions if len(sq) <= _MAX_SUB_QUESTION_LEN]
