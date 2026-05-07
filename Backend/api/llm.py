"""
LLM provider factory for the Multi-Agent Research Intelligence System.

Reads LLM_PROVIDER, LLM_MODEL, and LLM_API_KEY from the environment (via
python-dotenv) and exposes a get_llm_client() factory that returns the
appropriate async client instance.

Module-level variables LLM_PROVIDER and LLM_MODEL are intentionally public so
other modules (e.g. the health endpoint) can read them without re-parsing the
environment.
"""

import os
import logging

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "openai")
LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
LLM_API_KEY: str | None = os.getenv("LLM_API_KEY")

if not LLM_API_KEY:
    logger.warning(
        "LLM_API_KEY is not set. Research requests will return HTTP 503."
    )


def get_llm_client():
    """Return an async LLM client for the configured provider.

    Raises:
        RuntimeError: If LLM_API_KEY is not configured.
        ValueError: If LLM_PROVIDER is not a supported provider.
    """
    if not LLM_API_KEY:
        raise RuntimeError(
            "LLM_API_KEY is not configured. Set the LLM_API_KEY environment "
            "variable before making research requests."
        )

    if LLM_PROVIDER == "openai":
        import openai  # noqa: PLC0415
        return openai.AsyncOpenAI(api_key=LLM_API_KEY)

    elif LLM_PROVIDER == "anthropic":
        import anthropic  # noqa: PLC0415
        return anthropic.AsyncAnthropic(api_key=LLM_API_KEY)

    elif LLM_PROVIDER == "groq":
        import openai  # noqa: PLC0415
        # Groq is OpenAI-compatible — disable SDK retries so our adapter controls retry logic
        return openai.AsyncOpenAI(
            api_key=LLM_API_KEY,
            base_url="https://api.groq.com/openai/v1",
            max_retries=0,  # adapter handles retries with correct wait times
        )

    else:
        raise ValueError(
            f"Unsupported LLM_PROVIDER: {LLM_PROVIDER!r}. "
            "Supported providers are 'openai', 'anthropic', and 'groq'."
        )
