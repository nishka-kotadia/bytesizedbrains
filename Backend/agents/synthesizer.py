"""
Synthesizer Agent for the Multi-Agent Research Intelligence System.

Calls the LLM to generate a structured Markdown research report from analyzed
sources, enforces word-count bounds per depth level, applies format
transformations (Markdown, Plain Text, Structured JSON), and falls back to a
partial report after two consecutive LLM failures.
"""

import logging
import re

from api.llm import LLM_MODEL, LLM_PROVIDER
from models.config import Config, DepthLevel, OutputFormat
from models.source import Source

logger = logging.getLogger(__name__)

# Word count bounds keyed by depth level
DEPTH_WORD_BOUNDS: dict[DepthLevel, tuple[int, int]] = {
    DepthLevel.quick:    (400, 800),
    DepthLevel.standard: (800, 1500),
    DepthLevel.deep:     (1500, 3000),
}


def _make_partial_report(sources: list[Source]) -> str:
    """Return a minimal fallback report when LLM generation fails twice."""
    lines = [
        "## Executive Summary\n\nReport generation failed. Below are the sources found.\n\n## Sources\n"
    ]
    for s in sources:
        lines.append(f"- [{s.title}]({s.url})")
    return "\n".join(lines)


def _format_sources_for_prompt(sources: list[Source]) -> str:
    """Format sources into a numbered list suitable for the LLM prompt."""
    parts: list[str] = []
    for i, s in enumerate(sources, start=1):
        key = (s.key_findings or (s.abstract or "")[:100] or "N/A")[:100]
        parts.append(f"{i}. {s.title} ({s.year}) — {key}")
    return "\n\n".join(parts)


def _strip_markdown(text: str) -> str:
    """Strip Markdown formatting, returning plain text."""
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text, flags=re.DOTALL)
    text = re.sub(r"__(.+?)__", r"\1", text, flags=re.DOTALL)
    text = re.sub(r"\*(.+?)\*", r"\1", text, flags=re.DOTALL)
    text = re.sub(r"_(.+?)_", r"\1", text, flags=re.DOTALL)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"^---+\s*$", "", text, flags=re.MULTILINE)
    return text


def _parse_section(markdown: str, heading: str) -> str:
    """Extract the content of a Markdown section by its heading."""
    pattern = rf"##\s+{re.escape(heading)}\s*\n(.*?)(?=\n##\s|\Z)"
    match = re.search(pattern, markdown, flags=re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return ""


def _to_structured_json(markdown: str, sources: list[Source]) -> dict:
    """Parse a Markdown report into a structured JSON dict."""
    return {
        "executive_summary": _parse_section(markdown, "Executive Summary"),
        "key_findings": _parse_section(markdown, "Key Findings"),
        "research_gaps": _parse_section(markdown, "Research Gaps"),
        "conclusion": _parse_section(markdown, "Conclusion"),
        "sources": [
            {
                "id": s.id,
                "type": s.type,
                "title": s.title,
                "authors": s.authors,
                "venue": s.venue,
                "year": s.year,
                "url": s.url,
                "abstract": s.abstract,
                "relevance": s.relevance,
                "key_findings": s.key_findings,
            }
            for s in sources
        ],
    }


class SynthesizerAgent:
    """Generates a structured research report from analyzed sources."""

    def __init__(self, llm_client) -> None:
        self.llm_client = llm_client

    async def synthesize(self, sources: list[Source], config: Config) -> str | dict:
        """Generate a research report and apply the configured format transformation."""
        min_words, max_words = DEPTH_WORD_BOUNDS[config.depth]
        formatted_sources = _format_sources_for_prompt(sources)

        system_prompt = "You are a research synthesis expert. Write a concise Markdown report."
        user_prompt = (
            f"Write a research report on these {len(sources)} sources. "
            "Sections: ## Summary, ## Key Findings, ## Gaps, ## Conclusion. "
            f"Be concise ({min_words}-{max_words} words).\n\n"
            f"Sources:\n{formatted_sources}"
        )

        markdown_report: str | None = None
        last_exc: Exception | None = None

        for attempt in range(2):
            try:
                markdown_report = await self._call_llm(system_prompt, user_prompt)
                logger.info(
                    "SynthesizerAgent: report generated on attempt %d (%d words).",
                    attempt + 1, len(markdown_report.split()),
                )
                break
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                logger.warning(
                    "SynthesizerAgent: LLM call failed on attempt %d: %s.",
                    attempt + 1, exc,
                )

        if markdown_report is None:
            logger.error(
                "SynthesizerAgent: both LLM attempts failed (%s). Returning partial report.",
                last_exc,
            )
            partial = _make_partial_report(sources)
            return self._apply_format(partial, sources, config)

        return self._apply_format(markdown_report, sources, config)

    async def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        """Dispatch to the configured LLM provider and return the response text."""
        if LLM_PROVIDER in ("openai", "groq"):
            response = await self.llm_client.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.4,
                max_tokens=1024,
            )
            content = response.choices[0].message.content
            if not content:
                raise ValueError("OpenAI returned an empty response.")
            return content

        elif LLM_PROVIDER == "anthropic":
            response = await self.llm_client.messages.create(
                model=LLM_MODEL,
                max_tokens=4096,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            for block in response.content:
                if hasattr(block, "text"):
                    return block.text
            raise ValueError("Anthropic returned no text block.")

        else:
            raise ValueError(f"Unsupported LLM_PROVIDER: {LLM_PROVIDER!r}.")

    def _apply_format(self, markdown: str, sources: list[Source], config: Config) -> str | dict:
        """Apply the output format transformation specified in config.format."""
        if config.format == OutputFormat.plain_text:
            return _strip_markdown(markdown)
        if config.format == OutputFormat.structured_json:
            return _to_structured_json(markdown, sources)
        return markdown
