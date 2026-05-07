# Implementation Plan: Multi-Agent Research Intelligence System

## Overview

Build the complete Python backend in `Backend/` and update `Frontend/index.html` to connect to the real API. The pipeline follows: Decomposer → Planner → Search → Analyzer → Synthesizer, coordinated by an Orchestrator and exposed via FastAPI with SSE streaming. Tasks are ordered by dependency so each step builds on the previous one.

## Tasks

- [x] 1. Project scaffolding and environment setup
  - Create `Backend/` directory structure matching the design: `api/`, `agents/`, `db/`, `models/` with `__init__.py` in each
  - Create `Backend/requirements.txt` with pinned versions: `fastapi==0.111.0`, `uvicorn[standard]==0.29.0`, `pydantic==2.7.1`, `sqlalchemy[asyncio]==2.0.30`, `aiosqlite==0.20.0`, `httpx==0.27.0`, `arxiv==2.1.0`, `python-dotenv==1.0.1`, `hypothesis==6.100.1`, `pytest==8.2.0`, `pytest-asyncio==0.23.6`, `openai==1.30.1`, `anthropic==0.26.0`
  - Create `Backend/.env.example` with `LLM_PROVIDER=openai`, `LLM_MODEL=gpt-4o-mini`, `LLM_API_KEY=your-key-here`
  - Create `Backend/main.py` as the uvicorn entry point that imports and runs the FastAPI app
  - _Requirements: 11.1_

- [x] 2. Pydantic data models
  - [x] 2.1 Implement `models/config.py` with `DepthLevel`, `OutputFormat`, `SourceTypes`, and `Config` Pydantic models exactly as specified in the design
    - Include field validators and defaults
    - _Requirements: 9.1, 11.1_

  - [x] 2.2 Implement `models/source.py` with `SourceType` and `Source` Pydantic models
    - Include all fields: `id`, `type`, `title`, `authors`, `venue`, `year`, `url`, `abstract`, `relevance`, `key_findings`
    - _Requirements: 5.2, 6.2, 7.4_

  - [x] 2.3 Implement `models/search.py` with `SearchTarget` and `SearchTask` Pydantic models
    - Include `sub_question`, `target`, `query`, `priority` fields
    - _Requirements: 4.1_

  - [x] 2.4 Implement `models/session.py` with `SessionStatus` and `ResearchSession` Pydantic models
    - Include all fields: `session_id`, `query`, `config`, `status`, `sources`, `report`, `error_msg`, `created_at`, `completed_at`
    - _Requirements: 10.1_

  - [x] 2.5 Implement `models/events.py` with Pydantic models for all SSE event payloads: `StepStartEvent`, `StepCompleteEvent`, `SourceFoundEvent`, `PipelineCompleteEvent`, `PipelineErrorEvent`
    - Also add `ResearchRequest`, `ResearchResponse`, `SessionSummary`, `HealthResponse` API models
    - _Requirements: 1.1, 1.2, 2.2, 2.3, 2.4, 2.5, 2.6_

  - [x] 2.6 Write property tests for data model validation
    - **Property 2: Invalid queries are always rejected**
    - **Validates: Requirements 1.3, 1.4**
    - Use `hypothesis` `st.text()` strategies to generate empty strings, whitespace-only strings, and strings > 2000 chars; assert `ResearchRequest` raises `ValidationError` for each

- [x] 3. SQLite database layer
  - [x] 3.1 Implement `db/models.py` with SQLAlchemy ORM `ResearchSessionORM` table definition
    - Columns: `session_id` (PK), `query`, `config_json`, `status`, `sources_json`, `report`, `error_msg`, `created_at`, `completed_at`
    - _Requirements: 10.1_

  - [x] 3.2 Implement `db/database.py` with async SQLAlchemy engine, session factory, and `init_db()` function
    - Use `aiosqlite` driver with `research.db` path configurable via `DATABASE_URL` env var
    - Implement `save_session(session: ResearchSession)`, `get_session(session_id: str) -> ResearchSession | None`, `list_sessions() -> list[SessionSummary]`, `delete_session(session_id: str) -> bool`
    - `list_sessions` must order by `completed_at` descending
    - _Requirements: 10.1, 10.2, 10.3, 10.5_

  - [x] 3.3 Write property tests for session persistence round-trip
    - **Property 14: Session persistence round-trip**
    - **Validates: Requirements 10.1, 10.3**
    - Generate arbitrary `ResearchSession` objects with `hypothesis`, save and retrieve, assert field equality

  - [x] 3.4 Write property tests for history ordering
    - **Property 15: History is ordered by completion time descending**
    - **Validates: Requirements 10.2**
    - Insert sessions with arbitrary `completed_at` timestamps, assert `list_sessions()` returns them in descending order

  - [x] 3.5 Write property tests for deleted session retrieval
    - **Property 16: Deleted sessions are not retrievable**
    - **Validates: Requirements 10.5**
    - Save a session, delete it, assert `get_session()` returns `None` and API returns HTTP 404

- [x] 4. LLM provider factory
  - Implement `api/llm.py` with `get_llm_plugin()` factory function
  - Read `LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY` from environment via `python-dotenv`
  - Return the appropriate OpenClaw plugin instance for `openai` or `anthropic`
  - Raise `RuntimeError` at import time if `LLM_API_KEY` is not set
  - _Requirements: 11.1, 11.2, 11.3, 11.4_

- [x] 5. FastAPI server — core setup and health endpoint
  - [x] 5.1 Implement `api/server.py` with FastAPI app instance, `CORSMiddleware(allow_origins=["*"])`, and `lifespan` handler that calls `init_db()` on startup
    - Initialize the session queue registry as `dict[str, asyncio.Queue]`
    - _Requirements: 1.5, 12.1_

  - [x] 5.2 Implement `GET /api/health` route returning `HealthResponse` with `status="ok"`, version, `LLM_PROVIDER`, and `LLM_MODEL`
    - _Requirements: 12.1_

  - [x] 5.3 Implement `GET /api/history` route that calls `db.list_sessions()` and returns the array ordered by most recent first
    - _Requirements: 10.2_

  - [x] 5.4 Implement `GET /api/history/{session_id}` route that calls `db.get_session()` and returns the full record or HTTP 404
    - _Requirements: 10.3, 10.4_

  - [x] 5.5 Implement `DELETE /api/history/{session_id}` route that calls `db.delete_session()` and returns HTTP 204 or HTTP 404
    - _Requirements: 10.5_

- [x] 6. Checkpoint — verify server skeleton
  - Ensure all tests pass, ask the user if questions arise.
  - Smoke test: `GET /api/health` returns 200 with correct shape; CORS headers present; SQLite initializes without errors

- [x] 7. Decomposer Agent
  - [x] 7.1 Implement `agents/decomposer.py` with `DecomposerAgent` class
    - `decompose(query: str) -> list[str]` method calls the LLM via OpenClaw to generate 3–7 sub-questions
    - Validate each sub-question is ≤ 200 characters; retry once if fewer than 3 are returned
    - Fall back to `[query]` after two failed attempts and log a warning
    - _Requirements: 3.1, 3.2, 3.3_

  - [x] 7.2 Write property tests for Decomposer sub-question bounds
    - **Property 5: Decomposer sub-question count is bounded**
    - **Validates: Requirements 3.1, 3.2**
    - Use `hypothesis` to generate valid query strings; mock the LLM; assert output list length is in [3, 7] and each item ≤ 200 chars

- [x] 8. Planner Agent
  - [x] 8.1 Implement `agents/planner.py` with `PlannerAgent` class
    - `plan(sub_questions: list[str], config: Config) -> list[SearchTask]` method calls the LLM to generate `SearchTask` objects
    - Deduplicate semantically equivalent tasks; cap total at `config.maxSources * 2`
    - Sort tasks by `priority` descending before returning
    - _Requirements: 4.1, 4.2, 4.3_

  - [x] 8.2 Write property tests for Planner task count bound
    - **Property 6: Planner task count respects the config bound**
    - **Validates: Requirements 4.2**
    - Generate arbitrary sub-question lists and `Config` objects; mock LLM; assert `len(tasks) <= config.maxSources * 2`

  - [x] 8.3 Write property tests for Planner task ordering
    - **Property 7: Planner tasks are ordered by priority descending**
    - **Validates: Requirements 4.3**
    - Generate arbitrary sub-question lists; mock LLM; assert `tasks[i].priority >= tasks[i+1].priority` for all `i`

- [x] 9. Search Agent — arXiv
  - [x] 9.1 Implement `agents/search.py` with `SearchAgent` class and `_search_arxiv(task: SearchTask, config: Config) -> list[Source]` method
    - Query the `arxiv` library with the task's query string; retrieve up to `config.maxSources` results
    - Extract `id`, `title`, `authors`, `abstract`, `published`, `entry_id` fields; map to `Source` with `type=paper`
    - Assign relevance score 0–100 via cosine similarity on LLM embeddings against the original query
    - Retry once on HTTP error or 10-second timeout; log and continue on second failure
    - Skip if `config.sources.papers` is `False`
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

  - [x] 9.2 Write property tests for relevance score range (arXiv)
    - **Property 8: Source relevance scores are always in range**
    - **Validates: Requirements 5.3, 6.3**
    - Generate arbitrary arXiv-shaped result dicts; assert the scoring function returns an integer in [0, 100]

- [x] 10. Search Agent — GitHub
  - [x] 10.1 Implement `_search_github(task: SearchTask, config: Config) -> list[Source]` method on `SearchAgent`
    - Query GitHub Search API via `httpx`; retrieve up to 10 repositories per task
    - Extract `full_name`, `description`, `language`, `stargazers_count`, `updated_at`, `html_url`; map to `Source` with `type=repo`
    - Assign relevance score 0–100 via cosine similarity on LLM embeddings
    - On HTTP 403: wait 60 s, retry once; on other errors or timeout: log and continue
    - Skip if `config.sources.web` is `False` (when `papers=True` and `web=False`)
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

  - [x] 10.2 Implement `search(tasks: list[SearchTask], config: Config, queue: asyncio.Queue) -> list[Source]` orchestration method on `SearchAgent`
    - Iterate tasks, dispatch to `_search_arxiv` or `_search_github` based on `task.target`
    - Push a `source_found` SSE event to `queue` for each discovered source
    - Return the combined flat list of all sources
    - _Requirements: 2.4, 5.1, 6.1_

  - [x] 10.3 Write property tests for SSE source_found event structure
    - **Property 3: SSE source_found events are structurally valid**
    - **Validates: Requirements 2.4, 5.3, 6.3**
    - Generate arbitrary `Source` objects; serialize to `source_found` event dict; assert all required fields are present, `year > 0`, `relevance` in [0, 100], `type` in `{"paper", "repo"}`

- [x] 11. Analyzer Agent
  - [x] 11.1 Implement `agents/analyzer.py` with `AnalyzerAgent` class
    - `analyze(sources: list[Source], config: Config) -> list[Source]` method
    - Deduplicate by normalized title: lowercase, strip punctuation, remove duplicates keeping first occurrence
    - Sort deduplicated list by `relevance` descending
    - Truncate to `config.maxSources`
    - Call LLM to generate a 2–4 sentence `key_findings` summary for each retained source
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

  - [x] 11.2 Write property tests for source deduplication
    - **Property 9: Source deduplication removes all title duplicates**
    - **Validates: Requirements 7.1**
    - Generate lists of `Source` objects with intentional title duplicates (same normalized form); assert output has no two entries with the same normalized title

  - [x] 11.3 Write property tests for Analyzer sort order
    - **Property 10: Analyzer output is sorted by relevance descending**
    - **Validates: Requirements 7.2**
    - Generate arbitrary `Source` lists; run deduplication + sort; assert `sources[i].relevance >= sources[i+1].relevance` for all `i`

  - [x] 11.4 Write property tests for Analyzer maxSources bound
    - **Property 11: Analyzer output respects the maxSources bound**
    - **Validates: Requirements 7.3**
    - Generate arbitrary `Source` lists and `Config` objects; assert `len(result) <= config.maxSources`

- [x] 12. Checkpoint — verify agent pipeline up to Analyzer
  - Ensure all tests pass, ask the user if questions arise.
  - Unit test: mock LLM and APIs; run Decomposer → Planner → Search → Analyzer in sequence; verify each stage produces valid output

- [x] 13. Synthesizer Agent
  - [x] 13.1 Implement `agents/synthesizer.py` with `SynthesizerAgent` class
    - `synthesize(sources: list[Source], config: Config) -> str | dict` method calls the LLM to generate a structured Markdown report
    - Enforce word count bounds: Quick=400–800, Standard=800–1500, Deep=1500–3000
    - Include inline Markdown citation links `[title](url)` for each source used
    - Retry once on failure; return partial report (Executive Summary + sources list) after two failures
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.7_

  - [x] 13.2 Implement format transformations in `synthesize()`
    - `Plain Text`: strip all Markdown formatting before returning
    - `Structured JSON`: return dict with keys `executive_summary`, `key_findings`, `research_gaps`, `conclusion`, `sources`
    - `Markdown`: return as-is
    - _Requirements: 8.5, 8.6_

  - [x] 13.3 Write property tests for report section presence and order
    - **Property 12: Report contains all required sections in order**
    - **Validates: Requirements 8.2**
    - Generate arbitrary non-empty `Source` lists; mock LLM to return a report; assert headings "Executive Summary", "Key Findings", "Research Gaps", "Conclusion" appear in that order

  - [x] 13.4 Write property tests for report word count by depth
    - **Property 13: Report word count respects depth configuration**
    - **Validates: Requirements 8.4, 9.2, 9.3, 9.4**
    - For each `DepthLevel`, generate source lists and mock LLM; assert word count falls within the depth-specific bounds

- [x] 14. Orchestrator
  - [x] 14.1 Implement `agents/orchestrator.py` with `Orchestrator` class
    - `run_pipeline(session: ResearchSession, queue: asyncio.Queue)` async method
    - Push `step_start` event before each agent call and `step_complete` after, using the step index mapping from the design (indices 0–4)
    - Wrap the entire pipeline in `asyncio.wait_for(..., timeout=120)` and push `pipeline_error` with timeout message on `asyncio.TimeoutError`
    - On unrecoverable agent error, push `pipeline_error` and re-raise
    - On success, call `db.save_session()` then push `pipeline_complete` with report and sources
    - _Requirements: 2.2, 2.3, 2.5, 2.6, 12.2, 12.3_

  - [x] 14.2 Implement depth-based source limit enforcement in the Orchestrator
    - Pass `maxSources` override to agents based on `config.depth`: Quick=10, Standard=20, Deep=50
    - _Requirements: 9.2, 9.3, 9.4_

  - [x] 14.3 Write property tests for SSE step event structure
    - **Property 4: SSE step events are structurally valid**
    - **Validates: Requirements 2.2, 2.3**
    - Mock all agents; run orchestrator; collect all `step_start` and `step_complete` events from the queue; assert each has non-empty `step_name`, `step_index` in [0, 4], and non-empty `label`/`summary`

- [x] 15. FastAPI server — research endpoint and SSE streaming
  - [x] 15.1 Implement `POST /api/research` route in `api/server.py`
    - Validate request body with `ResearchRequest` (Pydantic enforces `min_length=1`, `max_length=2000`)
    - Return HTTP 503 if `LLM_API_KEY` is not configured
    - Generate a UUID `session_id`, create a `ResearchSession` record, allocate an `asyncio.Queue` in the registry
    - Launch `orchestrator.run_pipeline()` as a background `asyncio.Task`
    - Return `ResearchResponse` with `session_id` and `stream_url`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 11.2_

  - [x] 15.2 Implement `GET /api/research/{session_id}/stream` SSE route
    - Return HTTP 404 if `session_id` not in queue registry
    - Open a `StreamingResponse` with `media_type="text/event-stream"`
    - Drain the session queue, formatting each event as `event: <type>\ndata: <json>\n\n`
    - Run a concurrent keepalive coroutine that writes `: keepalive\n\n` every 15 seconds
    - On `asyncio.CancelledError` (client disconnect), remove the queue entry and clean up
    - Close the stream after `pipeline_complete` or `pipeline_error` is forwarded
    - _Requirements: 2.1, 2.5, 2.6, 2.7_

  - [x] 15.3 Write property tests for unique session IDs
    - **Property 1: Valid queries always produce unique session IDs**
    - **Validates: Requirements 1.2**
    - Use `hypothesis` to generate pairs of valid query strings; call `POST /api/research` for each; assert the two `session_id` values are distinct

- [x] 16. Structured logging
  - Add structured JSON log emission to `api/server.py` and `agents/orchestrator.py`
  - Log events: pipeline step start, step completion, source discovery, errors, and timeouts
  - Use Python's `logging` module with a JSON formatter; emit to stdout
  - _Requirements: 12.2_

- [x] 17. Checkpoint — full backend integration test
  - Ensure all tests pass, ask the user if questions arise.
  - Run the full pytest suite (excluding integration tests gated by `INTEGRATION_TESTS=1`)
  - Verify smoke tests pass: health endpoint, CORS headers, DB init, config validation for all depth levels and both LLM providers

- [x] 18. Frontend integration — replace simulation with real API
  - [x] 18.1 Update `Frontend/index.html`: replace `runSimulation()` with `startResearch(query, config)`
    - `startResearch` sends `POST http://localhost:8000/api/research` with `{query, config}` body
    - On success, open `EventSource(stream_url)` and register listeners for `step_start`, `step_complete`, `source_found`, `pipeline_complete`, `pipeline_error`
    - Map `step_start` → set active step; `step_complete` → mark step done with summary; `source_found` → append to sources list; `pipeline_complete` → set report and transition to results view; `pipeline_error` → show error state
    - _Requirements: 1.1, 1.2, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

  - [x] 18.2 Update `Frontend/index.html`: replace hardcoded history state with real API calls
    - On component mount, fetch `GET http://localhost:8000/api/history` and populate history state
    - On delete, call `DELETE http://localhost:8000/api/history/{session_id}` then refresh history
    - On history item click, fetch `GET http://localhost:8000/api/history/{session_id}` and display the stored report and sources
    - _Requirements: 10.2, 10.3, 10.5_

  - [x] 18.3 Update `Frontend/index.html`: reduce `AGENT_STEPS` array from 6 to 5 entries matching the backend pipeline
    - Remove the "browse" step (index 3); update step labels to match the backend's step index mapping (decompose=0, plan=1, search=2, analyze=3, synthesize=4)
    - _Requirements: 2.2, 2.3_

  - [x] 18.4 Update `Frontend/index.html`: add error state rendering for `pipeline_error` events
    - Display the error message from the SSE event in the UI instead of leaving the pipeline in a loading state
    - _Requirements: 2.6_

- [x] 19. Final checkpoint — end-to-end verification
  - Ensure all tests pass, ask the user if questions arise.
  - Run the full pytest suite; verify all 16 property tests are present and passing
  - Confirm `Backend/main.py` starts without errors when `LLM_API_KEY` is set
  - Confirm `Frontend/index.html` opens in a browser and the submit button triggers a real API call (visible in browser network tab)

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at logical boundaries
- Property tests validate universal correctness properties using Hypothesis; unit tests cover specific examples and error conditions
- Integration tests (gated by `INTEGRATION_TESTS=1` env var) require real LLM and API credentials and are not part of the standard test run
- The OpenClaw framework is used for LLM provider injection; no agent hard-codes a provider name
