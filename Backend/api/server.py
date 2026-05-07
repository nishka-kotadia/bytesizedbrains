"""
FastAPI application for the Multi-Agent Research Intelligence System.

Exposes REST + SSE endpoints:
    POST   /api/research
    GET    /api/research/{session_id}/stream
    GET    /api/health
    GET    /api/history
    GET    /api/history/{session_id}
    DELETE /api/history/{session_id}
"""

import asyncio
import json
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from db import database as db
from db.database import init_db
from models.events import HealthResponse, ResearchRequest, ResearchResponse, SessionSummary, FollowUpRequest
from models.session import ResearchSession, SessionStatus
from agents.orchestrator import Orchestrator
from api.llm import LLM_PROVIDER, LLM_MODEL, LLM_API_KEY, get_llm_client
from api.logging_config import configure_logging

logger = logging.getLogger(__name__)

APP_VERSION = "1.0.0"

# Per-session SSE event queues
session_queues: dict[str, asyncio.Queue] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run startup/shutdown logic for the FastAPI application."""
    configure_logging()
    await init_db()
    yield


app = FastAPI(
    title="Multi-Agent Research System",
    version=APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Return the current health status of the API."""
    return HealthResponse(
        status="ok",
        version=APP_VERSION,
        llm_provider=LLM_PROVIDER,
        llm_model=LLM_MODEL,
    )


@app.get("/api/openclaw")
async def openclaw_status():
    """Return the OpenClaw adapter registry and dispatch trace."""
    from adapters.openclaw_adapter import OpenClawAdapter, AgentCapability, ExecutionMode
    from api.llm import LLM_MODEL
    # Build a fresh adapter just to show the registered config
    # (live stats come from the per-request orchestrator instances)
    adapter = OpenClawAdapter("config/openclaw_config.yaml")
    agents = [
        ("decomposer",     AgentCapability.DECOMPOSE,      ExecutionMode.EDGE,  LLM_MODEL, 30),
        ("planner",        AgentCapability.PLAN,           ExecutionMode.EDGE,  LLM_MODEL, 30),
        ("search",         AgentCapability.SEARCH,         ExecutionMode.EDGE,  LLM_MODEL, 60),
        ("analyzer",       AgentCapability.ANALYZE,        ExecutionMode.CLOUD, LLM_MODEL, 60),
        ("gap_detector",   AgentCapability.DETECT_GAPS,    ExecutionMode.CLOUD, LLM_MODEL, 45),
        ("idea_generator", AgentCapability.GENERATE_IDEAS, ExecutionMode.CLOUD, LLM_MODEL, 45),
        ("synthesizer",    AgentCapability.SYNTHESIZE,     ExecutionMode.EDGE,  LLM_MODEL, 45),
    ]
    for agent_id, cap, mode, model, timeout in agents:
        adapter.register_agent(agent_id, cap, mode, model, timeout)
    return adapter.get_registry_summary()


@app.get("/api/history")
async def get_history() -> list[SessionSummary]:
    """Return all completed sessions ordered by most recent first."""
    return await db.list_sessions()


@app.get("/api/history/{session_id}")
async def get_session_by_id(session_id: str) -> ResearchSession:
    """Return the full session record or 404 if not found."""
    session = await db.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id!r} not found")
    return session


@app.delete("/api/history/{session_id}", status_code=204)
async def delete_session_by_id(session_id: str) -> Response:
    """Delete a session by ID. Returns 204 on success or 404 if not found."""
    deleted = await db.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Session {session_id!r} not found")
    return Response(status_code=204)


@app.post("/api/research", response_model=ResearchResponse)
async def start_research(request: ResearchRequest, http_request: Request) -> ResearchResponse:
    """Start a new research pipeline and return a session ID with SSE stream URL."""
    if not LLM_API_KEY:
        logger.warning(
            "server: refusing research request — LLM_API_KEY not set query_length=%d",
            len(request.query),
        )
        raise HTTPException(status_code=503, detail="LLM_API_KEY is not configured")

    session_id = str(uuid.uuid4())
    logger.info(
        "server: incoming research request session_id=%s query_length=%d",
        session_id, len(request.query),
    )

    session = ResearchSession(
        session_id=session_id,
        query=request.query,
        config=request.config,
        status=SessionStatus.pending,
        created_at=datetime.now(tz=timezone.utc),
    )

    queue: asyncio.Queue = asyncio.Queue()
    session_queues[session_id] = queue

    llm_client = get_llm_client()
    orchestrator = Orchestrator(llm_client)

    asyncio.create_task(orchestrator.run_pipeline(session, queue))

    base_url = str(http_request.base_url).rstrip("/")
    stream_url = f"{base_url}/api/research/{session_id}/stream"
    return ResearchResponse(session_id=session_id, stream_url=stream_url)


@app.post("/api/research/{session_id}/followup")
async def followup_research(session_id: str, request: FollowUpRequest):
    """Answer a follow-up question using the session's report and sources as context."""
    if not LLM_API_KEY:
        raise HTTPException(status_code=503, detail="LLM_API_KEY is not configured")

    session = await db.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id!r} not found")

    if not session.report:
        raise HTTPException(status_code=400, detail="Session has no report yet")

    # Build context from the session
    sources_text = "\n".join(
        f"- {s.title} ({s.venue}, {s.year}): {s.key_findings or s.abstract[:150] if s.abstract else 'N/A'}"
        for s in session.sources[:10]
    )

    system_prompt = (
        "You are a research assistant. The user has completed a research session "
        "and is asking follow-up questions. Answer concisely and accurately based "
        "on the research context provided. If the answer isn't in the context, say so."
    )

    context = (
        f"Original research query: {session.query}\n\n"
        f"Research report summary:\n{session.report[:2000]}\n\n"
        f"Key sources:\n{sources_text}"
    )

    user_message = f"Context:\n{context}\n\nQuestion: {request.question}"

    async def stream_answer():
        try:
            llm_client = get_llm_client()

            if LLM_PROVIDER in ("openai", "groq"):
                stream = await llm_client.chat.completions.create(
                    model=LLM_MODEL,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                    temperature=0.5,
                    max_tokens=800,
                    stream=True,
                )
                async for chunk in stream:
                    delta = chunk.choices[0].delta.content
                    if delta:
                        yield f"data: {json.dumps({'token': delta})}\n\n"

            elif LLM_PROVIDER == "anthropic":
                async with llm_client.messages.stream(
                    model=LLM_MODEL,
                    max_tokens=800,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_message}],
                ) as stream:
                    async for text in stream.text_stream:
                        yield f"data: {json.dumps({'token': text})}\n\n"

            yield f"data: {json.dumps({'done': True})}\n\n"

        except Exception as exc:
            logger.error("followup: error session_id=%s: %s", session_id, exc)
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"

    return StreamingResponse(
        stream_answer(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/research/{session_id}/stream")
async def stream_research(session_id: str):
    """Stream SSE events for a research session."""
    if session_id not in session_queues:
        raise HTTPException(status_code=404, detail=f"Session {session_id!r} not found")

    queue = session_queues[session_id]

    async def event_generator():
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    event_type = event["type"]
                    event_data = json.dumps(event["data"])
                    yield f"event: {event_type}\ndata: {event_data}\n\n"

                    if event_type in ("pipeline_complete", "pipeline_error"):
                        break
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            session_queues.pop(session_id, None)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
