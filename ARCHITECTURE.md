# PRISM - OpenClaw Integrated Research Intelligence System

## Architecture Overview

PRISM is a multi-agent research intelligence system built on the **OpenClaw framework** (Edge + Cloud variant) with integrated knowledge graph, embeddings, and gap detection capabilities.

### Layer Stack

```
┌─────────────────────────────────────────────────────────┐
│ 1. Communication Layer                                   │
│    - React UI (Frontend/)                                │
│    - Node.js CLI (CLI/bin/research.js)                   │
│    - FastAPI REST + SSE streaming                        │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ 2. Adapter Layer (OpenClaw)                              │
│    - ProtocolAdapter (adapters/openclaw_adapter.py)     │
│    - Agent registry & message marshaling                 │
│    - Edge/Cloud routing logic                            │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ 3. Gateway Layer                                         │
│    - FastAPI Server (api/server.py)                      │
│    - REST endpoints + SSE streaming                      │
│    - CORS + middleware                                   │
│    - Session management                                  │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ 4. PI Engine (Multi-Agent Loop)                          │
│    - Decomposer Agent (agents/decomposer.py)             │
│    - Planner Agent (agents/planner.py)                   │
│    - Search Agent (agents/search.py)                     │
│    - Analyzer Agent (agents/analyzer.py)                 │
│    - Gap Detector Agent (agents/gap_detector.py)         │
│    - Idea Generator Agent (agents/idea_generator.py)     │
│    - Synthesizer Agent (agents/synthesizer.py)           │
│    - Orchestrator (agents/orchestrator.py)               │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ 5. Execution Layer                                       │
│    - Knowledge Graph (models/graph.py)                   │
│    - Embeddings Service (knowledge_graph/embeddings.py)  │
│    - Graph Store (knowledge_graph/graph_store.py)        │
│    - arXiv API integration                               │
│    - GitHub API integration                              │
│    - SQLite persistence (db/database.py)                 │
└─────────────────────────────────────────────────────────┘
```

---

## Component Details

### 1. Communication Layer

#### Frontend (React)
- **File**: `Frontend/index.html`
- **Framework**: React 18 + Babel
- **Styling**: Tailwind CSS
- **Features**: Research UI, progress tracking, results visualization

#### CLI (Node.js)
- **File**: `CLI/bin/research.js`
- **Runtime**: Node.js 22+
- **Dependencies**: eventsource (SSE support)
- **Features**: Interactive mode, history, session retrieval

#### API Server (FastAPI)
- **File**: `Backend/api/server.py`
- **Port**: 8000 (configurable)
- **Endpoints**:
  - `POST /api/research` - Start research session
  - `GET /api/research/{session_id}/stream` - SSE progress streaming
  - `GET /api/history` - Research history
  - `GET /api/history/{session_id}` - Session details
  - `DELETE /api/history/{session_id}` - Delete session
  - `GET /api/health` - System health

---

### 2. Adapter Layer (OpenClaw)

#### ProtocolAdapter
- **File**: `Backend/adapters/openclaw_adapter.py`
- **Responsibility**: 
  - Agent registration and discovery
  - Message protocol handling (JSON serialization)
  - Edge/Cloud execution routing
  - Fallback strategies for agent failures

#### Configuration
- **File**: `Backend/config/openclaw_config.yaml`
- **Defines**:
  - Agent execution modes (edge/cloud)
  - LLM provider configuration
  - Knowledge graph backend selection
  - Embeddings provider & caching
  - API integration registry

---

### 3. Gateway Layer

#### FastAPI Server
- **File**: `Backend/api/server.py`
- **Features**:
  - REST API for research initiation
  - SSE streaming for real-time progress
  - Session management
  - CORS middleware
  - Health checks

#### Session Management
- Per-session asyncio queues for event streaming
- 300-second timeout enforcement
- Depth-based source limiting
- SQLite persistence

---

### 4. PI Engine (7-Agent Pipeline)

#### Agent Execution Flow
```
1. Decomposer (Edge)
   └─ Breaks query into sub-questions
   
2. Planner (Edge)
   └─ Creates search strategy
   
3. Search Agent (Edge)
   ├─ Searches arXiv
   ├─ Searches GitHub
   └─ Generates embeddings for each source
   
4. Analyzer (Cloud)
   └─ Cross-references findings
   
5. Graph Builder (Orchestrator)
   ├─ Creates nodes from sources
   ├─ Builds semantic edges (embeddings)
   └─ Extracts keywords
   
6. Gap Detector (Cloud)
   ├─ Finds structural gaps
   ├─ Detects semantic clusters
   └─ Identifies missing intersections
   
7. Idea Generator (Cloud)
   ├─ Generates gap-based ideas
   ├─ Explores intersections
   └─ Ranks by impact/feasibility/novelty
   
8. Synthesizer (Edge)
   └─ Generates final report
```

#### Individual Agents

**Decomposer Agent** (`agents/decomposer.py`)
- Input: Research query
- Output: List of sub-questions
- Model: GPT-4-turbo
- Mode: Edge (local execution)

**Planner Agent** (`agents/planner.py`)
- Input: Sub-questions, config
- Output: List of SearchTasks
- Model: GPT-4-turbo
- Mode: Edge

**Search Agent** (`agents/search.py`)
- Input: SearchTasks, config
- Output: List of Sources with embeddings
- Integrations: arXiv API, GitHub API
- Embeddings: OpenAI text-embedding-3-small (1536-dim)
- Mode: Edge

**Analyzer Agent** (`agents/analyzer.py`)
- Input: Sources
- Output: Analyzed sources with key_findings
- Model: Claude 3 Sonnet
- Mode: Cloud

**Gap Detector Agent** (`agents/gap_detector.py`)
- Input: Knowledge graph, original query
- Output: List of ResearchGap objects
- Strategies:
  - Structural gap detection (node degree analysis)
  - Semantic gap detection (clustering + cross-cluster edges)
  - Intersection gap detection (LLM reasoning)
- Mode: Cloud

**Idea Generator Agent** (`agents/idea_generator.py`)
- Input: Graph, gaps, query
- Output: List of ranked ResearchIdea objects
- Generation strategies:
  - Gap-based ideas (from identified gaps)
  - Intersection ideas (novel topic combinations)
  - Trend-based ideas (emerging research directions)
- Scoring: Impact (50%) + Novelty (30%) + Feasibility (20%)
- Mode: Cloud

**Synthesizer Agent** (`agents/synthesizer.py`)
- Input: Analyzed sources, config
- Output: Final research report (Markdown/JSON/Plain text)
- Mode: Edge

---

### 5. Execution Layer

#### Knowledge Graph
- **Models**: `Backend/models/graph.py`
- **Components**:
  - `GraphNode`: Represents a research source
    - Fields: title, authors, venue, year, embedding, relevance
    - Embeddings: 1536-dimensional vectors
  - `GraphEdge`: Relationship between sources
    - Types: cites, extends, contradicts, complements, builds_upon, refutes, related
    - Confidence score (0-1)
    - Evidence list
  - `ResearchGap`: Identified gap
    - Severity score
    - Affected nodes
    - Missing intersections
  - `ResearchIdea`: Generated research idea
    - Impact, feasibility, novelty scores
    - Hypothesis and next steps

#### Embeddings Service
- **File**: `Backend/knowledge_graph/embeddings.py`
- **Providers**:
  - OpenAI (text-embedding-3-small, 1536-dim, production)
  - HuggingFace (sentence-transformers, open-source)
- **Features**:
  - Batch processing
  - Caching (JSON-based)
  - Cosine & Euclidean similarity computation
  - Cost optimization

#### Graph Store
- **File**: `Backend/knowledge_graph/graph_store.py`
- **Backends**:
  - JSON (lightweight, local, development)
  - Neo4j (production, full-featured, distributed)
- **Operations**:
  - Persist/load nodes and edges
  - Semantic similarity queries
  - Graph traversal

#### API Integrations

**arXiv API**
- Endpoint: `https://arxiv.org/api/query`
- Rate limit: 3000 req/5min
- Returns: Papers with title, authors, abstract, year
- Timeout: 10 seconds per request

**GitHub API**
- Endpoint: `https://api.github.com/search/repositories`
- Rate limit: 30 req/min (authenticated)
- Returns: Repositories with description, language, stars
- Timeout: 10 seconds per request

#### Database
- **Type**: SQLite (async)
- **ORM**: SQLAlchemy 2.0
- **Schema**: `Backend/db/models.py`
- **Tables**:
  - `research_sessions`: Query, config, status, sources, report, created_at, completed_at

---

## Data Flow

### Research Session Lifecycle

```
1. Client → POST /api/research
   ├─ Create ResearchRequest (query + config)
   └─ Return ResearchResponse (session_id + stream_url)

2. Orchestrator → Run Pipeline
   ├─ Decompose → Sub-questions
   ├─ Plan → Search tasks
   ├─ Search → Sources with embeddings
   │  └─ STREAM: source_found events
   ├─ Analyze → Key findings
   ├─ Build Graph → Knowledge graph
   │  ├─ Create nodes
   │  ├─ Create semantic edges
   │  └─ Extract keywords
   ├─ Detect Gaps → Research gaps
   ├─ Generate Ideas → Actionable ideas
   ├─ Synthesize → Final report
   └─ Persist → SQLite + JSON graph

3. Client → GET /api/research/{session_id}/stream (SSE)
   └─ Receive events:
      ├─ step_start
      ├─ source_found
      ├─ step_complete
      ├─ pipeline_complete (includes gaps, ideas, graph)
      └─ pipeline_error (if failed)
```

---

## Configuration

### OpenClaw Config
- **File**: `Backend/config/openclaw_config.yaml`
- **Key Sections**:
  - `agents`: Execution mode (edge/cloud), model, timeout
  - `protocols`: Message format, validation
  - `knowledge_graph`: Backend selection, max nodes/edges
  - `embeddings`: Provider, model, dimension, caching
  - `llm`: Provider configuration (OpenAI, Anthropic)
  - `edge`: Local caching, fallback strategy
  - `cloud`: Auto-scaling, region

### Environment Variables
- `OPENAI_API_KEY`: OpenAI API key
- `ANTHROPIC_API_KEY`: Anthropic (Claude) API key
- `RESEARCH_API_URL`: Backend URL (CLI default: http://localhost:8000)

---

## Key Features

### 1. Structured Relationships (Goal 1)
- ✅ Sources stored as graph nodes
- ✅ Relationships typed (cites, extends, etc.)
- ✅ Confidence scoring on edges
- ✅ Semantic similarity via embeddings

### 2. Gap Detection (Goal 2)
- ✅ Structural gaps (isolated nodes)
- ✅ Semantic gaps (disconnected clusters)
- ✅ Intersection gaps (LLM-identified)
- ✅ Severity scoring

### 3. Actionable Research Ideas (Goal 3)
- ✅ Gap-based idea generation
- ✅ Intersection-based ideas
- ✅ Trend-based ideas
- ✅ Impact/feasibility/novelty ranking
- ✅ Concrete next steps

### 4. OpenClaw Integration
- ✅ Agent registry
- ✅ Edge/Cloud execution routing
- ✅ Protocol marshaling
- ✅ Fallback strategies

### 5. TypeScript Support
- ✅ Full type definitions (CLI/src/types.ts)
- ✅ Type-safe API client (CLI/src/api-client.ts)
- ✅ tsconfig.json configuration

---

## Dependencies

### Python
```
fastapi==0.115.12            # Web framework
uvicorn==0.34.3              # ASGI server
pydantic==2.10.6             # Data validation
sqlalchemy==2.0.41           # ORM
aiosqlite==0.20.0            # Async SQLite
httpx==0.28.1                # HTTP client
arxiv==2.1.3                 # arXiv API
python-dotenv==1.1.0         # Environment variables
openai==1.82.1               # OpenAI API
anthropic==0.52.0            # Anthropic API
pyyaml==6.0.1                # YAML config
openclawai==0.2.0            # OpenClaw framework
sentence-transformers==3.0.1 # Embeddings (optional)
numpy==1.24.3                # Numerical computing
scikit-learn==1.3.2          # ML utilities
networkx==3.1                # Graph operations
neo4j==5.14.1                # Graph DB (optional)
```

### Node.js
```
eventsource==2.0.2           # SSE client
openclawai==0.2.0            # OpenClaw framework (TS)
typescript==5.3.3            # Type system
axios==1.6.5                 # HTTP client
@types/node==20.10.6         # Node types
```

---

## Installation & Setup

### Backend

```bash
cd Backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Server runs on `http://localhost:8000`

### CLI

```bash
cd CLI
npm install
npm start
# or with TypeScript
npm run dev
```

### Frontend

Open `Frontend/index.html` in a browser or serve with:
```bash
python -m http.server --directory Frontend 3000
```

---

## Advanced Configuration

### Switch to Neo4j Backend

1. Install Neo4j:
   ```bash
   docker run -d --name neo4j -p 7687:7687 -p 7474:7474 \
     -e NEO4J_AUTH=neo4j/password neo4j
   ```

2. Update `openclaw_config.yaml`:
   ```yaml
   knowledge_graph:
     backend: "neo4j"
     uri: "bolt://localhost:7687"
     auth: ["neo4j", "password"]
   ```

### Switch to HuggingFace Embeddings

Update `openclaw_config.yaml`:
```yaml
embeddings:
  provider: "huggingface"
  model: "all-MiniLM-L6-v2"  # Smaller, faster, free
  dimension: 384
```

### Enable WebSocket Support

(Coming in next phase)
```python
# Will support real-time bidirectional communication
# WebSocket endpoints for follow-up questions during research
```

---

## Testing

Run tests:
```bash
cd Backend
pytest tests/ -v
pytest tests/test_orchestrator.py -v  # Test specific agent
```

---

## Future Enhancements

1. **WebSocket Support**: Real-time multi-turn conversations
2. **Bot Interface**: Conversational UI for research assistance
3. **3D Visualization**: Three.js network graphs
4. **Distributed Execution**: Cloud-native deployment
5. **Custom Adapters**: Plug-and-play data source connectors
6. **Advanced Analytics**: Research trend forecasting

---

## Support & Contributing

For issues, feature requests, or contributions, see the project repository.

---

**Version**: 1.0.0  
**Last Updated**: May 5, 2026  
**Framework**: OpenClaw (Edge + Cloud)  
**Status**: Production-Ready
