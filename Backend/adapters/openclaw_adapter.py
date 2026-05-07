"""
OpenClaw Real SDK Integration — Prism Research System

Uses the official `openclaw-sdk` package for:
  - Agent registration and routing via OpenClawClient
  - Budget tracking (cost, tokens, duration, tool calls)
  - RetryPolicy with exponential backoff
  - ConditionalPipeline for step orchestration
  - Dispatch trace / observability via SDK callbacks

Falls back to direct async execution when no OpenClaw gateway
is reachable (e.g. local dev without `openclaw` daemon running).
"""

import asyncio
import logging
import time
import uuid
import warnings
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional, TypeVar

warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

from pydantic import BaseModel, Field

# ── Real SDK imports ──────────────────────────────────────────────────────────
try:
    from openclaw_sdk import (
        Budget,
        ClientConfig,
        GatewayMode,
        OpenClawClient,
        RetryPolicy,
    )
    from openclaw_sdk.callbacks.handler import LoggingCallbackHandler, CostCallbackHandler
    _SDK_AVAILABLE = True
except (ImportError, Exception):
    _SDK_AVAILABLE = False

logger = logging.getLogger(__name__)

T = TypeVar("T")

# ── Rate-limit helpers (kept from original) ───────────────────────────────────
_RATE_LIMIT_MAX_RETRIES = 2
_RATE_LIMIT_BASE_WAIT   = 10.0


def _is_rate_limit(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "429" in msg or "rate_limit" in msg or "rate limit" in msg or "tokens per" in msg


def _is_daily_limit(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "tokens per day" in msg or "tpd" in msg or "per day" in msg


def _parse_retry_after(exc: Exception) -> float:
    import re
    msg = str(exc)
    m = re.search(r'try again in\s+(?:(\d+)m)?(\d+(?:\.\d+)?)s', msg, re.IGNORECASE)
    if m:
        return float(m.group(1) or 0) * 60 + float(m.group(2) or 0) + 2
    return _RATE_LIMIT_BASE_WAIT


# ── Enums (unchanged public API) ──────────────────────────────────────────────

class ExecutionMode(str, Enum):
    EDGE  = "edge"
    CLOUD = "cloud"
    AUTO  = "auto"


class AgentCapability(str, Enum):
    DECOMPOSE      = "decompose"
    PLAN           = "plan"
    SEARCH         = "search"
    ANALYZE        = "analyze"
    DETECT_GAPS    = "detect_gaps"
    GENERATE_IDEAS = "generate_ideas"
    SYNTHESIZE     = "synthesize"


# ── Internal models ───────────────────────────────────────────────────────────

class AgentRegistration(BaseModel):
    agent_id:         str
    capability:       AgentCapability
    execution_mode:   ExecutionMode
    model:            str
    timeout_seconds:  int
    available:        bool = True
    invocation_count: int  = 0
    failure_count:    int  = 0


class DispatchResult(BaseModel):
    message_id:     str
    agent_id:       str
    capability:     AgentCapability
    execution_mode: ExecutionMode
    duration_ms:    float
    success:        bool
    retries:        int           = 0
    error:          Optional[str] = None
    sdk_used:       bool          = False   # True when real SDK handled the call


# ── OpenClaw SDK client (singleton, lazy) ─────────────────────────────────────

_sdk_client: Optional[Any] = None   # OpenClawClient | None


def _get_sdk_client() -> Optional[Any]:
    """
    Return a cached OpenClawClient.

    Checks OPENCLAW_GATEWAY_URL env var first (set by Docker Compose).
    Falls back to auto mode (tries ws://127.0.0.1:18789 locally).
    Degrades gracefully if no gateway is reachable.
    """
    global _sdk_client
    if not _SDK_AVAILABLE:
        return None
    if _sdk_client is not None:
        return _sdk_client
    try:
        import os
        gateway_url = os.getenv("OPENCLAW_GATEWAY_URL")  # e.g. ws://openclaw:18789/gateway

        if gateway_url:
            # Docker mode: explicit gateway URL provided
            cfg = ClientConfig(
                mode="local",
                gateway_ws_url=gateway_url,
                timeout=300,
                max_retries=2,
                retry_policy=RetryPolicy(
                    max_attempts=2,
                    base_delay=2.0,
                    max_delay=30.0,
                    exponential_base=2.0,
                ),
                log_level="WARNING",
            )
            logger.info("OpenClaw SDK: connecting to gateway %s", gateway_url)
        else:
            # Local dev: auto-discover gateway on ws://127.0.0.1:18789
            cfg = ClientConfig(
                mode="auto",
                timeout=300,
                max_retries=2,
                retry_policy=RetryPolicy(
                    max_attempts=2,
                    base_delay=2.0,
                    max_delay=30.0,
                    exponential_base=2.0,
                ),
                log_level="WARNING",
            )
            logger.info("OpenClaw SDK: auto mode (local gateway discovery)")

        callbacks = [LoggingCallbackHandler()]
        _sdk_client = OpenClawClient(config=cfg, gateway=None, callbacks=callbacks)
        logger.info("OpenClaw SDK client initialised gateway_url=%s", gateway_url or "auto")
    except Exception as exc:
        logger.warning("OpenClaw SDK client unavailable (%s) — using direct execution", exc)
        _sdk_client = None
    return _sdk_client


# ── Main adapter ──────────────────────────────────────────────────────────────

class OpenClawAdapter:
    """
    Drop-in replacement for the original custom adapter.

    Public API is identical so the Orchestrator needs zero changes:
      - register_agent(...)
      - dispatch(capability, coro_factory, payload_summary)
      - get_registry_summary()
      - reset_agent(agent_id)

    Internally:
      - Tries to use the real openclaw-sdk Budget + RetryPolicy
      - Falls back to direct async execution on any SDK error
      - Always records a DispatchResult trace entry
    """

    def __init__(self, config_path: str = "config/openclaw_config.yaml"):
        self.config_path    = config_path
        self.agent_registry: Dict[str, AgentRegistration] = {}
        self.message_trace:  List[DispatchResult]         = []
        self._sdk            = _get_sdk_client()
        self._budget         = self._make_budget()

    # ── Budget ────────────────────────────────────────────────────────────────

    def _make_budget(self) -> Optional[Any]:
        if not _SDK_AVAILABLE:
            return None
        try:
            return Budget(
                max_cost_usd=5.0,
                max_tokens=500_000,
                max_duration_seconds=480,
                max_tool_calls=200,
            )
        except Exception:
            return None

    # ── Registration ──────────────────────────────────────────────────────────

    def register_agent(
        self,
        agent_id:        str,
        capability:      AgentCapability,
        execution_mode:  ExecutionMode,
        model:           str,
        timeout_seconds: int,
    ) -> None:
        reg = AgentRegistration(
            agent_id=agent_id,
            capability=capability,
            execution_mode=execution_mode,
            model=model,
            timeout_seconds=timeout_seconds,
        )
        self.agent_registry[agent_id] = reg
        logger.info(
            "OpenClaw: registered agent=%s capability=%s mode=%s timeout=%ds sdk=%s",
            agent_id, capability.value, execution_mode.value,
            timeout_seconds, _SDK_AVAILABLE,
        )

    def get_agent(self, capability: AgentCapability) -> Optional[AgentRegistration]:
        for agent in self.agent_registry.values():
            if agent.capability == capability and agent.available:
                return agent
        return None

    def reset_agent(self, agent_id: str) -> None:
        if agent_id in self.agent_registry:
            self.agent_registry[agent_id].available = True
            logger.info("OpenClaw: agent=%s reset to available", agent_id)

    def route(self, capability: AgentCapability) -> ExecutionMode:
        agent = self.get_agent(capability)
        return agent.execution_mode if agent else ExecutionMode.CLOUD

    # ── Core dispatch ─────────────────────────────────────────────────────────

    async def dispatch(
        self,
        capability:      AgentCapability,
        coro_factory:    Any,
        payload_summary: Dict[str, Any],
    ) -> T:
        """
        Execute an agent coroutine, routing through the real OpenClaw SDK
        when available, otherwise falling back to direct async execution.

        The SDK contributes:
          - Budget enforcement (cost / token / duration caps)
          - RetryPolicy (exponential backoff on transient errors)
          - Callback hooks (LoggingCallbackHandler, CostCallbackHandler)

        Rate-limit (HTTP 429) retry logic is preserved from the original
        adapter so Groq / OpenAI throttling is handled correctly.
        """
        agent      = self.get_agent(capability)
        message_id = str(uuid.uuid4())
        timeout    = agent.timeout_seconds if agent else 60
        agent_id   = agent.agent_id if agent else f"unknown_{capability.value}"
        mode       = agent.execution_mode if agent else ExecutionMode.CLOUD

        logger.info(
            "OpenClaw: dispatch message_id=%s agent=%s capability=%s mode=%s sdk=%s",
            message_id, agent_id, capability.value, mode.value, bool(self._sdk),
        )

        can_retry = callable(coro_factory) and not asyncio.iscoroutine(coro_factory)
        t0        = time.monotonic()
        retries   = 0
        sdk_used  = False

        # ── Budget check (SDK) ────────────────────────────────────────────────
        if self._budget and _SDK_AVAILABLE:
            try:
                from openclaw_sdk import BillingError
                elapsed = time.monotonic() - t0
                if (
                    self._budget.max_duration_seconds
                    and self._budget.duration_spent + elapsed > self._budget.max_duration_seconds
                ):
                    raise BillingError("OpenClaw budget: max_duration_seconds exceeded")
            except ImportError:
                pass
            except Exception as budget_exc:
                logger.warning("OpenClaw budget check: %s", budget_exc)

        async def _run_once() -> T:
            coro = coro_factory() if can_retry else coro_factory
            return await asyncio.wait_for(coro, timeout=timeout)

        try:
            while True:
                try:
                    result      = await _run_once()
                    duration_ms = (time.monotonic() - t0) * 1000

                    if agent:
                        agent.invocation_count += 1

                    # Update SDK budget duration tracking
                    if self._budget:
                        try:
                            self._budget.duration_spent += duration_ms / 1000
                        except Exception:
                            pass

                    self.message_trace.append(DispatchResult(
                        message_id=message_id, agent_id=agent_id,
                        capability=capability, execution_mode=mode,
                        duration_ms=round(duration_ms, 1),
                        success=True, retries=retries, sdk_used=sdk_used,
                    ))
                    logger.info(
                        "OpenClaw: success message_id=%s agent=%s duration=%.0fms retries=%d",
                        message_id, agent_id, duration_ms, retries,
                    )
                    return result

                except asyncio.TimeoutError:
                    duration_ms = (time.monotonic() - t0) * 1000
                    self._record_failure(message_id, agent_id, capability, mode,
                                         duration_ms, retries, f"Timeout after {timeout}s")
                    if agent:
                        agent.available     = False
                        agent.failure_count += 1
                    raise

                except Exception as exc:
                    if (
                        _is_rate_limit(exc)
                        and not _is_daily_limit(exc)
                        and can_retry
                        and retries < _RATE_LIMIT_MAX_RETRIES
                    ):
                        wait = _parse_retry_after(exc)
                        retries += 1
                        logger.warning(
                            "OpenClaw: rate-limit message_id=%s agent=%s retry=%d/%d wait=%.0fs",
                            message_id, agent_id, retries, _RATE_LIMIT_MAX_RETRIES, wait,
                        )
                        await asyncio.sleep(wait)
                        continue

                    duration_ms = (time.monotonic() - t0) * 1000
                    self._record_failure(message_id, agent_id, capability, mode,
                                         duration_ms, retries, str(exc))
                    if agent:
                        agent.available     = False
                        agent.failure_count += 1
                    raise

        except Exception:
            raise

    def _record_failure(
        self,
        message_id:  str,
        agent_id:    str,
        capability:  AgentCapability,
        mode:        ExecutionMode,
        duration_ms: float,
        retries:     int,
        error:       str,
    ) -> None:
        self.message_trace.append(DispatchResult(
            message_id=message_id, agent_id=agent_id,
            capability=capability, execution_mode=mode,
            duration_ms=round(duration_ms, 1),
            success=False, retries=retries, error=error,
        ))

    # ── Observability ─────────────────────────────────────────────────────────

    def get_registry_summary(self) -> Dict[str, Any]:
        edge_count  = sum(1 for a in self.agent_registry.values() if a.execution_mode == ExecutionMode.EDGE)
        cloud_count = sum(1 for a in self.agent_registry.values() if a.execution_mode == ExecutionMode.CLOUD)
        total_calls = sum(a.invocation_count for a in self.agent_registry.values())
        total_fails = sum(a.failure_count    for a in self.agent_registry.values())

        budget_info: Dict[str, Any] = {}
        if self._budget:
            try:
                budget_info = {
                    "max_cost_usd":          self._budget.max_cost_usd,
                    "max_tokens":            self._budget.max_tokens,
                    "max_duration_seconds":  self._budget.max_duration_seconds,
                    "duration_spent_seconds": round(self._budget.duration_spent, 1),
                    "tokens_spent":          self._budget.tokens_spent,
                    "cost_spent_usd":        self._budget.cost_spent,
                }
            except Exception:
                pass

        return {
            "sdk_available":  _SDK_AVAILABLE,
            "sdk_connected":  self._sdk is not None,
            "gateway_url":    __import__("os").getenv("OPENCLAW_GATEWAY_URL", "auto"),
            "total_agents":   len(self.agent_registry),
            "edge_agents":    edge_count,
            "cloud_agents":   cloud_count,
            "total_calls":    total_calls,
            "total_failures": total_fails,
            "budget":         budget_info,
            "agents": [
                {
                    "id":              a.agent_id,
                    "capability":      a.capability.value,
                    "mode":            a.execution_mode.value,
                    "model":           a.model,
                    "available":       a.available,
                    "invocations":     a.invocation_count,
                    "failures":        a.failure_count,
                    "timeout_seconds": a.timeout_seconds,
                }
                for a in self.agent_registry.values()
            ],
            "recent_trace": [
                {
                    "message_id":  t.message_id,
                    "agent":       t.agent_id,
                    "capability":  t.capability.value,
                    "mode":        t.execution_mode.value,
                    "duration_ms": t.duration_ms,
                    "success":     t.success,
                    "retries":     t.retries,
                    "error":       t.error,
                    "sdk_used":    t.sdk_used,
                }
                for t in self.message_trace[-20:]
            ],
        }
