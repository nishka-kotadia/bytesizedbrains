"""
Analyzer Agent for the Multi-Agent Research Intelligence System.

Deduplicates sources by normalized title, ranks them by relevance score,
truncates to the configured maximum, and calls the LLM to generate a
2–4 sentence key-findings summary for each retained source.
"""

import logging
import re
import string

from api.llm import LLM_MODEL, LLM_PROVIDER
from models.config import Config
from models.source import Source

logger = logging.getLogger(__name__)

_KEY_FINDINGS_FALLBACK = "Key findings not available."


class AnalyzerAgent:
    """Deduplicates, ranks, and annotates sources with key-findings summaries."""

    def __init__(self, llm_client) -> None:
        self.llm_client = llm_client

    async def analyze(self, sources: list[Source], config: Config) -> list[Source]:
        """Deduplicate, rank, truncate, and annotate sources."""
        deduplicated = self._deduplicate(sources)
        deduplicated.sort(key=lambda s: s.relevance, reverse=True)
        retained = deduplicated[: config.maxSources]

        logger.info(
            "AnalyzerAgent: %d sources after dedup/sort/truncate (input=%d, maxSources=%d).",
            len(retained), len(sources), config.maxSources,
        )

        # Generate key_findings in a single batched LLM call instead of one
        # call per source, to avoid rate-limit timeouts on free-tier providers.
        annotated = await self._batch_key_findings(retained)
        return annotated

    async def _batch_key_findings(self, sources: list[Source]) -> list[Source]:
        """Generate key_findings for all sources in a single LLM call."""
        if not sources:
            return sources

        # Build a compact prompt listing all sources
        items = []
        for i, s in enumerate(sources, 1):
            snippet = (s.abstract or "")[:150]  # cut from 300 to 150
            items.append(f"{i}. {s.title}: {snippet}")
        prompt = (
            "For each source, write one sentence (max 80 chars) on its key finding. "
            "Reply with ONLY a numbered list.\n\n" + "\n".join(items)
        )

        try:
            if LLM_PROVIDER in ("openai", "groq"):
                response = await self.llm_client.chat.completions.create(
                    model=LLM_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=512,
                )
                raw = response.choices[0].message.content or ""
            elif LLM_PROVIDER == "anthropic":
                response = await self.llm_client.messages.create(
                    model=LLM_MODEL,
                    max_tokens=1024,
                    messages=[{"role": "user", "content": prompt}],
                )
                raw = next(
                    (b.text for b in response.content if hasattr(b, "text")), ""
                )
            else:
                raise ValueError(f"Unsupported LLM_PROVIDER: {LLM_PROVIDER!r}.")

            # Parse numbered lines back to per-source findings
            findings: dict[int, str] = {}
            for line in raw.splitlines():
                line = line.strip()
                import re
                m = re.match(r"^(\d+)[.)]\s*(.*)", line)
                if m:
                    findings[int(m.group(1))] = m.group(2).strip()

            annotated = []
            for i, s in enumerate(sources, 1):
                kf = findings.get(i, _KEY_FINDINGS_FALLBACK)
                annotated.append(s.model_copy(update={"key_findings": kf}))
            return annotated

        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "AnalyzerAgent: batch key_findings LLM call failed: %s. Using fallback.", exc
            )
            return [
                s.model_copy(update={"key_findings": _KEY_FINDINGS_FALLBACK})
                for s in sources
            ]

    @staticmethod
    def _normalize_title(title: str) -> str:
        """Return a normalized version of title for deduplication comparison."""
        lowered = title.lower()
        no_punct = lowered.translate(str.maketrans("", "", string.punctuation))
        return re.sub(r"\s+", " ", no_punct).strip()

    def _deduplicate(self, sources: list[Source]) -> list[Source]:
        """Remove sources whose normalized title matches an already-seen title."""
        seen: set[str] = set()
        unique: list[Source] = []
        for source in sources:
            key = self._normalize_title(source.title)
            if key not in seen:
                seen.add(key)
                unique.append(source)
        return unique

    async def _call_llm_for_findings(self, source: Source) -> str:
        """Call the LLM to generate a 2–4 sentence key-findings summary."""
        prompt = (
            "Summarize the key findings of this research in 2-4 sentences:\n\n"
            f"Title: {source.title}\n"
            f"Abstract: {source.abstract}"
        )

        try:
            if LLM_PROVIDER in ("openai", "groq"):
                response = await self.llm_client.chat.completions.create(
                    model=LLM_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=256,
                )
                return response.choices[0].message.content or _KEY_FINDINGS_FALLBACK

            elif LLM_PROVIDER == "anthropic":
                response = await self.llm_client.messages.create(
                    model=LLM_MODEL,
                    max_tokens=512,
                    messages=[{"role": "user", "content": prompt}],
                )
                for block in response.content:
                    if hasattr(block, "text"):
                        return block.text
                return _KEY_FINDINGS_FALLBACK

            else:
                raise ValueError(f"Unsupported LLM_PROVIDER: {LLM_PROVIDER!r}.")

        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "AnalyzerAgent: LLM call failed for source %r: %s. Using fallback.",
                source.title, exc,
            )
            return _KEY_FINDINGS_FALLBACK
