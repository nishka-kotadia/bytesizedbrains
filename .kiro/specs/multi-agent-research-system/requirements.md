# Requirements Document

## Introduction

The Multi-Agent Research Intelligence System is a Python backend that powers the existing ResearchAI React frontend (`Frontend/index.html`). When a user submits a research query, the backend orchestrates a pipeline of specialized AI agents using the OpenClaw framework to decompose the query, search arXiv and GitHub, analyze retrieved content, and synthesize a structured research report. The backend exposes a REST + Server-Sent Events (SSE) API so the frontend can stream real-time pipeline progress and receive the final report.

## Glossary

- **Orchestrator**: The top-level OpenClaw agent that receives a research query, delegates sub-tasks to specialized agents, and assembles the final report.
- **Decomposer_Agent**: A specialized agent responsible for breaking a research query into focused sub-questions.
- **Planner_Agent**: A specialized agent that converts sub-questions into a prioritized search strategy.
- **Search_Agent**: A specialized agent that executes searches against arXiv and GitHub APIs.
- **Analyzer_Agent**: A specialized agent that reads, scores, and extracts key findings from retrieved sources.
- **Synthesizer_Agent**: A specialized agent that combines analyzed findings into a structured Markdown report.
- **Pipeline**: The ordered sequence of agent steps: decompose → plan → search → browse → analyze → synthesize.
- **Source**: A single arXiv paper or GitHub repository returned by the Search_Agent.
- **Report**: The final Markdown document produced by the Synthesizer_Agent.
- **SSE**: Server-Sent Events — a unidirectional HTTP streaming protocol used to push pipeline progress events to the frontend.
- **Research_Session**: A single end-to-end execution of the Pipeline for one query, identified by a unique session ID.
- **Config**: User-supplied parameters controlling research depth, source types, maximum source count, and output format.

---

## Requirements

### Requirement 1: REST API Entry Point

**User Story:** As a frontend developer, I want a single HTTP endpoint to submit a research query and configuration, so that the backend can begin a Research_Session and return a session ID for tracking.

#### Acceptance Criteria

1. THE API_Server SHALL expose a `POST /api/research` endpoint that accepts a JSON body containing a non-empty `query` string and an optional `config` object.
2. WHEN a valid `POST /api/research` request is received, THE API_Server SHALL respond with HTTP 200 and a JSON body containing a unique `session_id` string and a `stream_url` pointing to the SSE endpoint for that session.
3. IF the `query` field is absent or empty, THEN THE API_Server SHALL respond with HTTP 422 and a JSON error body describing the validation failure.
4. IF the `query` string exceeds 2000 characters, THEN THE API_Server SHALL respond with HTTP 422 and a JSON error body indicating the length limit.
5. THE API_Server SHALL accept CORS requests from any origin so that the frontend served from a file or different port can call the API.

---

### Requirement 2: Real-Time Pipeline Progress Streaming

**User Story:** As a frontend user, I want to see each agent step update in real time as the pipeline runs, so that I can follow the research progress without waiting for the full report.

#### Acceptance Criteria

1. THE API_Server SHALL expose a `GET /api/research/{session_id}/stream` SSE endpoint that streams pipeline events for the given session.
2. WHEN the Orchestrator starts a Pipeline step, THE API_Server SHALL emit an SSE event of type `step_start` containing the step name, step index (0–5), and a human-readable label.
3. WHEN the Orchestrator completes a Pipeline step, THE API_Server SHALL emit an SSE event of type `step_complete` containing the step name, step index, and a brief summary string.
4. WHEN the Search_Agent discovers a Source, THE API_Server SHALL emit an SSE event of type `source_found` containing the source title, authors, venue, year, relevance score (0–100), and source type (`paper` or `repo`).
5. WHEN the Pipeline completes successfully, THE API_Server SHALL emit an SSE event of type `pipeline_complete` containing the full Report text and a list of all Sources.
6. IF the Pipeline encounters an unrecoverable error, THEN THE API_Server SHALL emit an SSE event of type `pipeline_error` containing an error message, then close the SSE stream.
7. WHILE a Research_Session is active, THE API_Server SHALL emit an SSE keepalive comment every 15 seconds to prevent proxy timeouts.

---

### Requirement 3: Query Decomposition

**User Story:** As a researcher, I want the system to break my broad query into focused sub-questions, so that each aspect of the topic is investigated thoroughly.

#### Acceptance Criteria

1. WHEN the Orchestrator receives a research query, THE Decomposer_Agent SHALL generate between 3 and 7 sub-questions that together cover the key dimensions of the query.
2. THE Decomposer_Agent SHALL return sub-questions as a structured list, each sub-question being a complete interrogative sentence of no more than 200 characters.
3. IF the Decomposer_Agent fails to produce at least 3 sub-questions after two attempts, THEN THE Orchestrator SHALL proceed with the original query as a single sub-question and log a warning.

---

### Requirement 4: Research Planning

**User Story:** As a researcher, I want the system to build a search strategy from the sub-questions, so that searches are targeted and avoid redundant queries.

#### Acceptance Criteria

1. WHEN the Decomposer_Agent produces sub-questions, THE Planner_Agent SHALL generate a search plan containing one or more search tasks per sub-question, each task specifying a target source (`arxiv` or `github`) and a search query string.
2. THE Planner_Agent SHALL deduplicate semantically equivalent search tasks so that the total number of search tasks does not exceed `config.maxSources * 2`.
3. THE Planner_Agent SHALL prioritize search tasks by estimated relevance, ordering higher-priority tasks first.

---

### Requirement 5: arXiv Paper Search and Retrieval

**User Story:** As a researcher, I want the system to search arXiv for relevant academic papers, so that the report is grounded in peer-reviewed research.

#### Acceptance Criteria

1. WHEN the Search_Agent executes an `arxiv` search task, THE Search_Agent SHALL query the arXiv API using the task's query string and retrieve up to `config.maxSources` results per task.
2. THE Search_Agent SHALL extract the following fields from each arXiv result: paper ID, title, authors (comma-separated), abstract, publication date, and arXiv URL.
3. THE Search_Agent SHALL assign a relevance score between 0 and 100 to each arXiv result based on semantic similarity to the original research query.
4. IF the arXiv API returns an HTTP error or times out after 10 seconds, THEN THE Search_Agent SHALL retry the request once and, if the retry also fails, log the error and continue with any results already retrieved.
5. WHERE `config.sources.papers` is `false`, THE Search_Agent SHALL skip all `arxiv` search tasks.

---

### Requirement 6: GitHub Repository Search and Retrieval

**User Story:** As a researcher, I want the system to search GitHub for relevant repositories and code, so that the report includes practical implementations alongside theory.

#### Acceptance Criteria

1. WHEN the Search_Agent executes a `github` search task, THE Search_Agent SHALL query the GitHub Search API using the task's query string and retrieve up to 10 repositories per task.
2. THE Search_Agent SHALL extract the following fields from each GitHub result: repository full name, description, primary language, star count, last updated date, and repository URL.
3. THE Search_Agent SHALL assign a relevance score between 0 and 100 to each GitHub result based on semantic similarity to the original research query.
4. IF the GitHub API returns an HTTP 403 (rate limit) response, THEN THE Search_Agent SHALL wait 60 seconds and retry once before logging the error and continuing.
5. IF the GitHub API returns any other HTTP error or times out after 10 seconds, THEN THE Search_Agent SHALL log the error and continue with any results already retrieved.
6. WHERE `config.sources.papers` is `true` and `config.sources.web` is `false`, THE Search_Agent SHALL skip all `github` search tasks.

---

### Requirement 7: Source Deduplication and Ranking

**User Story:** As a researcher, I want the system to remove duplicate sources and surface the most relevant ones, so that the report is concise and high-quality.

#### Acceptance Criteria

1. WHEN the Search_Agent has collected all Sources, THE Analyzer_Agent SHALL deduplicate Sources by comparing normalized titles, removing any Source whose normalized title matches an already-retained Source.
2. THE Analyzer_Agent SHALL rank the deduplicated Sources by relevance score in descending order.
3. THE Analyzer_Agent SHALL retain at most `config.maxSources` Sources after ranking.
4. THE Analyzer_Agent SHALL extract a 2–4 sentence key-findings summary from each retained Source's abstract or description.

---

### Requirement 8: Report Synthesis

**User Story:** As a researcher, I want the system to produce a structured Markdown report from the analyzed sources, so that I receive a coherent, citable research summary.

#### Acceptance Criteria

1. WHEN the Analyzer_Agent has produced ranked Sources with key-findings summaries, THE Synthesizer_Agent SHALL generate a Report in Markdown format.
2. THE Report SHALL contain the following sections in order: Executive Summary, Key Findings (with sub-sections per major theme), Research Gaps, and Conclusion.
3. THE Report SHALL cite each Source used by including the source title and URL as an inline Markdown link at the point of use.
4. THE Report SHALL be between 400 and 3000 words.
5. WHERE `config.format` is `Plain Text`, THE Synthesizer_Agent SHALL strip all Markdown formatting from the Report before returning it.
6. WHERE `config.format` is `Structured JSON`, THE Synthesizer_Agent SHALL return the Report as a JSON object with keys `executive_summary`, `key_findings`, `research_gaps`, `conclusion`, and `sources`.
7. IF the Synthesizer_Agent fails to produce a Report after two attempts, THEN THE Orchestrator SHALL return a partial Report containing only the Executive Summary and a list of Sources.

---

### Requirement 9: Research Depth Configuration

**User Story:** As a researcher, I want to control how deeply the system researches a topic, so that I can trade off speed against thoroughness.

#### Acceptance Criteria

1. THE Config SHALL support three depth levels: `Quick`, `Standard`, and `Deep`.
2. WHERE `config.depth` is `Quick`, THE Orchestrator SHALL limit the Pipeline to at most 10 total Sources and instruct the Synthesizer_Agent to produce a Report of 400–800 words.
3. WHERE `config.depth` is `Standard`, THE Orchestrator SHALL limit the Pipeline to at most 20 total Sources and instruct the Synthesizer_Agent to produce a Report of 800–1500 words.
4. WHERE `config.depth` is `Deep`, THE Orchestrator SHALL limit the Pipeline to at most 50 total Sources and instruct the Synthesizer_Agent to produce a Report of 1500–3000 words.

---

### Requirement 10: Research Session History

**User Story:** As a researcher, I want the backend to persist completed Research_Sessions, so that I can retrieve past reports without re-running the pipeline.

#### Acceptance Criteria

1. WHEN a Pipeline completes successfully, THE API_Server SHALL persist the Research_Session record including session ID, query, Config, list of Sources, Report text, and completion timestamp to a local SQLite database.
2. THE API_Server SHALL expose a `GET /api/history` endpoint that returns a JSON array of past Research_Session summaries (session ID, query, completion timestamp) ordered by most recent first.
3. THE API_Server SHALL expose a `GET /api/history/{session_id}` endpoint that returns the full Research_Session record including Sources and Report for the given session ID.
4. IF no Research_Session exists for the given session ID, THEN THE API_Server SHALL respond with HTTP 404 and a JSON error body.
5. THE API_Server SHALL expose a `DELETE /api/history/{session_id}` endpoint that removes the specified Research_Session record and responds with HTTP 204.

---

### Requirement 11: LLM Provider Configuration

**User Story:** As a developer deploying the system, I want to configure which LLM provider and model the agents use, so that I can use the API key and model I already have access to.

#### Acceptance Criteria

1. THE API_Server SHALL read LLM provider settings from environment variables: `LLM_PROVIDER` (default `openai`), `LLM_MODEL` (default `gpt-4o-mini`), and `LLM_API_KEY`.
2. IF `LLM_API_KEY` is not set at startup, THEN THE API_Server SHALL log a warning and refuse to process research requests, returning HTTP 503 with a descriptive error message.
3. THE API_Server SHALL support at minimum the `openai` provider and the `anthropic` provider as values for `LLM_PROVIDER`.
4. THE Orchestrator SHALL pass the configured LLM provider and model to all agents via the OpenClaw plugin system so that no agent hard-codes a provider.

---

### Requirement 12: Health and Observability

**User Story:** As a developer operating the system, I want a health endpoint and structured logs, so that I can monitor the service and diagnose failures.

#### Acceptance Criteria

1. THE API_Server SHALL expose a `GET /api/health` endpoint that returns HTTP 200 with a JSON body containing `status: "ok"`, the current software version, and the configured `LLM_PROVIDER` and `LLM_MODEL`.
2. THE API_Server SHALL emit structured JSON log lines to stdout for every Pipeline step start, step completion, source discovery, and error event.
3. WHEN a Research_Session takes longer than 120 seconds, THE Orchestrator SHALL cancel the session, emit a `pipeline_error` SSE event with a timeout message, and log the timeout.
