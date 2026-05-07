# PRISM: OpenClaw-Powered Multi-Agent Research Intelligence System

**Build Structured Knowledge. Detect Research Gaps. Generate Innovation Ideas.**

PRISM is an advanced multi-agent research system that uses the OpenClaw framework to orchestrate intelligent agents for conducting comprehensive research, analyzing findings, detecting gaps in knowledge, and generating actionable research ideas.

---

## 🎯 Core Capabilities

### 1. **Structured Research Relationships** ✅
- Knowledge graph representation of all sources
- Typed relationships (cites, extends, contradicts, etc.)
- Semantic similarity via embeddings
- Confidence scoring on connections

### 2. **Research Gap Detection** ✅
- **Structural gaps**: Identifies isolated research areas
- **Semantic gaps**: Detects disconnected knowledge clusters
- **Intersection gaps**: Finds unexplored topic combinations
- **Severity scoring**: Prioritizes gaps by importance

### 3. **Actionable Research Ideas** ✅
- **Gap-based ideation**: Generates ideas from identified gaps
- **Intersection synthesis**: Combines topics in novel ways
- **Trend analysis**: Identifies emerging research directions
- **Multi-factor ranking**: Scores by impact, feasibility, and novelty
- **Concrete next steps**: Provides actionable roadmap

### 4. **OpenClaw Framework Integration** ✅
- Edge + Cloud execution model
- Intelligent routing (local vs. remote execution)
- Agent registry and discovery
- Protocol marshaling and fallback strategies

---

## 🏗️ Architecture Overview

```
User Interface (React UI / Node.js CLI)
         ↓
FastAPI Gateway (REST + SSE)
         ↓
OpenClaw ProtocolAdapter (Edge/Cloud Routing)
         ↓
7-Agent Pipeline:
  1. Decomposer    → Break query into sub-questions
  2. Planner       → Create research strategy
  3. Search        → Find sources (arXiv + GitHub)
  4. Analyzer      → Extract key findings
  5. GraphBuilder  → Create knowledge graph with embeddings
  6. GapDetector   → Identify research gaps
  7. IdeaGenerator → Generate research ideas
  8. Synthesizer   → Produce final report
         ↓
Knowledge Execution Layer:
  - Embeddings Service (OpenAI or HuggingFace)
  - Knowledge Graph Store (JSON or Neo4j)
  - SQLite Persistence
  - arXiv & GitHub APIs
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Node.js 22+
- OpenAI API key (or Anthropic for Claude)

### Setup Backend

```bash
# Clone and navigate to backend
cd Backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export OPENAI_API_KEY=sk-...
export ANTHROPIC_API_KEY=sk-ant-...  # optional

# Run server
python main.py
```

Server starts on `http://localhost:8000`

### Setup CLI

```bash
cd CLI
npm install
npm start
```

### Setup Frontend

```bash
# Serve Frontend
cd Frontend
python -m http.server 3000
# or use any static server
```

Open `http://localhost:3000` in your browser.

---

## 📖 Usage Examples

### CLI - Interactive Research

```bash
research
> Enter research query: "What are the latest advances in multi-agent reasoning?"
> Depth [Standard]: deep
> Include papers [Y/n]: y
> Include code [Y/n]: y

[Decomposing query...]
[Planning research strategy...]
[Searching sources...]
[Analyzing findings...]
[Building knowledge graph...]
[Detecting research gaps...]
[Generating research ideas...]
[Synthesizing report...]

=== RESEARCH COMPLETE ===
Found 45 sources across 8 research areas
Identified 12 knowledge gaps
Generated 5 actionable research ideas
```

### API - Python Example

```python
import asyncio
import aiohttp
from Backend.models.config import Config, DepthLevel

async def research():
    async with aiohttp.ClientSession() as session:
        # Start research
        response = await session.post(
            'http://localhost:8000/api/research',
            json={
                "query": "Multi-agent systems and reasoning",
                "config": {
                    "depth": "Standard",
                    "maxSources": 20,
                    "format": "Markdown"
                }
            }
        )
        data = await response.json()
        session_id = data['session_id']
        
        # Stream progress
        async with session.get(
            f'http://localhost:8000/api/research/{session_id}/stream'
        ) as stream:
            async for line in stream.content:
                if line:
                    event = json.loads(line.decode())
                    print(f"[{event['type']}] {event.get('data', {})}")

asyncio.run(research())
```

### TypeScript API Client

```typescript
import { PrismAPIClient, ResearchSession } from './CLI/src/api-client';

const client = new PrismAPIClient('http://localhost:8000');

// Start research
const response = await client.startResearch({
  query: 'Knowledge graphs in AI systems',
  config: PrismAPIClient.createDefaultConfig(),
});

// Stream progress
const session = new ResearchSession(client, response.session_id);

await session.watchProgress(
  (event) => {
    console.log(`[${event.type}]`, event.data);
    
    if (event.type === 'pipeline_complete') {
      console.log('Research completed!');
      console.log('Gaps:', event.data.gaps);
      console.log('Ideas:', event.data.ideas);
    }
  },
  (error) => console.error('Error:', error)
);

// Get final result
const result = await session.getResult();
```

---

## 📊 Output Structure

### Research Session Response

```json
{
  "session_id": "sess_123abc",
  "query": "Multi-agent reasoning",
  "status": "complete",
  "report": "# Research Report\n...",
  "sources": [
    {
      "id": "2024.01234",
      "type": "paper",
      "title": "Collaborative Reasoning in Multi-Agent Systems",
      "authors": "Smith et al.",
      "venue": "arXiv",
      "year": 2024,
      "relevance": 95,
      "embedding": [0.123, -0.456, ...],
      "key_findings": "Proposes novel consensus mechanism..."
    }
  ],
  "gaps": [
    {
      "gap_id": "gap_1",
      "title": "Multi-agent reasoning over temporal data",
      "description": "Current systems don't handle temporal reasoning...",
      "severity_score": 0.85,
      "missing_intersections": ["temporal", "reasoning", "agents"]
    }
  ],
  "ideas": [
    {
      "idea_id": "idea_1",
      "title": "Temporal Reasoning Framework for Multi-Agent Systems",
      "description": "Extend current systems with temporal reasoning...",
      "hypothesis": "Adding temporal constraints improves coordination",
      "impact_score": 0.9,
      "feasibility_score": 0.7,
      "novelty_score": 0.85,
      "next_steps": [
        "Survey temporal reasoning literature",
        "Design constraint propagation algorithm",
        "Implement prototype"
      ]
    }
  ],
  "knowledge_graph": {
    "nodes": {...},
    "edges": {...},
    "gaps": {...},
    "ideas": {...}
  }
}
```

---

## 🔧 Configuration

### OpenClaw Configuration
Edit `Backend/config/openclaw_config.yaml`:

```yaml
agents:
  gap_detector:
    type: "cloud"          # Execute on cloud
    model: "gpt-4-turbo"   # LLM to use
    timeout: 45            # Max execution time
    
knowledge_graph:
  backend: "json"          # Switch to "neo4j" for production
  
embeddings:
  provider: "openai"       # Or "huggingface"
  model: "text-embedding-3-small"
  dimension: 1536
```

### Environment Variables

```bash
# Required
OPENAI_API_KEY=sk-...

# Optional
ANTHROPIC_API_KEY=sk-ant-...
RESEARCH_API_URL=http://localhost:8000
```

---

## 📁 Project Structure

```
Prism/
├── Backend/
│   ├── agents/
│   │   ├── decomposer.py        # Query decomposition
│   │   ├── planner.py           # Research planning
│   │   ├── search.py            # Source discovery (arXiv/GitHub)
│   │   ├── analyzer.py          # Finding analysis
│   │   ├── gap_detector.py       # Gap detection
│   │   ├── idea_generator.py     # Idea generation
│   │   ├── synthesizer.py        # Report synthesis
│   │   └── orchestrator.py       # Pipeline orchestration
│   ├── adapters/
│   │   └── openclaw_adapter.py   # OpenClaw protocol adapter
│   ├── knowledge_graph/
│   │   ├── embeddings.py         # Embedding generation & storage
│   │   └── graph_store.py        # Graph persistence
│   ├── api/
│   │   ├── server.py             # FastAPI server
│   │   ├── llm.py                # LLM provider abstraction
│   │   └── logging_config.py
│   ├── db/
│   │   ├── database.py           # SQLite operations
│   │   └── models.py             # ORM models
│   ├── models/
│   │   ├── config.py             # Configuration models
│   │   ├── events.py             # SSE event schemas
│   │   ├── graph.py              # Knowledge graph models
│   │   ├── session.py            # Research session models
│   │   └── source.py             # Source/paper models
│   ├── config/
│   │   └── openclaw_config.yaml   # OpenClaw configuration
│   ├── requirements.txt
│   └── main.py
├── CLI/
│   ├── bin/
│   │   └── research.js           # CLI entry point
│   ├── src/
│   │   ├── types.ts              # TypeScript type definitions
│   │   └── api-client.ts         # Type-safe API client
│   ├── package.json
│   └── README.md
├── Frontend/
│   └── index.html                # React UI
├── ARCHITECTURE.md               # Detailed architecture docs
└── README.md                     # This file
```

---

## 🧠 How It Works

### Research Pipeline

1. **Decomposition** (Agent 1)
   - User query → Sub-questions
   - "Advances in multi-agent reasoning?" → 
     - "What are current multi-agent architectures?"
     - "How do agents communicate?"
     - "What are reasoning paradigms?"

2. **Planning** (Agent 2)
   - Sub-questions → Search strategy
   - Creates targeted search tasks

3. **Search** (Agent 3)
   - Executes arXiv and GitHub searches
   - Generates embeddings for each source
   - Streams `source_found` events

4. **Analysis** (Agent 4)
   - Extracts key findings from sources
   - Identifies relationships

5. **Graph Building** (Orchestrator)
   - Creates graph nodes from sources
   - Builds semantic edges using embeddings
   - Extracts keywords

6. **Gap Detection** (Agent 5)
   - Finds structural gaps (isolated nodes)
   - Detects semantic gaps (disconnected clusters)
   - Identifies intersection gaps (LLM reasoning)

7. **Idea Generation** (Agent 6)
   - Converts gaps into research ideas
   - Explores novel intersections
   - Analyzes emerging trends
   - Ranks by impact/feasibility/novelty

8. **Synthesis** (Agent 7)
   - Generates final report
   - Compiles findings, gaps, and ideas

### Knowledge Graph Example

```
Node: Paper A (2024)
├─ Embedding: [0.5, -0.3, ...]
├─ Keywords: ["agents", "reasoning"]
└─ Edges:
   ├─ CITES → Paper B (confidence: 0.9)
   ├─ EXTENDS → Paper C (confidence: 0.75)
   └─ RELATED → Paper D (confidence: 0.65, semantic similarity)

Gap: "Temporal reasoning in multi-agent systems"
├─ Severity: 0.85
├─ Affected nodes: [A, B, C]
└─ Missing intersection: temporal + agents + reasoning

Idea: "Temporal Reasoning Framework"
├─ Impact: 0.9
├─ Feasibility: 0.7
├─ Novelty: 0.85
├─ Supporting gaps: ["Temporal reasoning in multi-agent systems"]
└─ Next steps: ["Survey temporal reasoning", "Design algorithm", "Prototype"]
```

---

## 🔌 OpenClaw Integration

### Agent Registration

Agents are registered with execution modes:

```python
# Edge execution (local, fast)
- Decomposer
- Planner
- Search
- Synthesizer

# Cloud execution (powerful, slower)
- Analyzer
- Gap Detector
- Idea Generator
```

### Message Protocol

All agent communication uses standardized OpenClaw protocol:

```json
{
  "message_id": "msg_123",
  "timestamp": 1704067200.0,
  "agent_id": "decomposer",
  "capability": "decompose",
  "payload": {
    "query": "Research question..."
  },
  "metadata": {
    "version": "1.0",
    "protocol": "openclaw"
  }
}
```

---

## 📈 Performance Characteristics

| Component | Edge | Cloud |
|-----------|------|-------|
| **Latency** | <2s | 5-30s |
| **Cost** | Low | Medium |
| **Parallelizable** | Limited | Yes |
| **Best For** | Decompose, Plan, Search, Synthesize | Analyze, Gap Detection, Ideas |

### Depth Level Configuration

| Depth | Sources | Time | Cost |
|-------|---------|------|------|
| Quick | 10 | 1-2 min | Low |
| Standard | 20 | 3-5 min | Medium |
| Deep | 50 | 10-15 min | High |

---

## 🔐 Security & Privacy

- API keys stored in environment variables
- No data logged by default
- Sessions stored locally (SQLite)
- Graph data saved as JSON
- CORS configured for specified origins

---

## 🐛 Troubleshooting

### OpenAI API Key Error
```
Error: Invalid API key provided
Solution: export OPENAI_API_KEY=sk-...
```

### Embeddings Cost High
```
Solution: Switch to HuggingFace
In openclaw_config.yaml:
  embeddings:
    provider: "huggingface"
```

### Graph Building Slow
```
Solution: Reduce maxSources or switch to shallow depth
Or: Parallel gap detection and idea generation on cloud
```

---

## 📚 Advanced Usage

### Neo4j Backend (Production)

```bash
# Start Neo4j
docker run -d -p 7687:7687 -p 7474:7474 neo4j

# Update config
knowledge_graph:
  backend: "neo4j"
  uri: "bolt://localhost:7687"
```

### Custom Embeddings Provider

Implement `EmbeddingProvider` interface:

```python
class CustomEmbeddingProvider(EmbeddingProvider):
    async def embed(self, texts: List[str]) -> List[List[float]]:
        # Your implementation
        pass
```

### Extending Agents

Create custom agent:

```python
class CustomAgent:
    def __init__(self, llm_client):
        self.llm_client = llm_client
    
    async def execute(self, input_data):
        # Your logic
        return output_data
```

---

## 🚦 Status & Roadmap

### ✅ Completed
- [x] 7-agent pipeline
- [x] OpenClaw integration
- [x] Knowledge graph (JSON + Neo4j)
- [x] Embeddings service
- [x] Gap detection
- [x] Idea generation
- [x] TypeScript support
- [x] REST API + SSE

### 🔄 In Progress
- [ ] WebSocket support for real-time conversations
- [ ] Bot chat interface
- [ ] 3D graph visualization
- [ ] Distributed execution

### 📋 Planned
- [ ] Custom data source adapters
- [ ] Advanced graph analytics
- [ ] Research trend forecasting
- [ ] Multi-turn refinement
- [ ] Export to various formats

---

## 💡 Key Innovations

1. **Intelligent Gap Detection**: Uses clustering, embeddings, and LLM reasoning
2. **Ranked Idea Generation**: Multi-factor scoring (impact, feasibility, novelty)
3. **OpenClaw Integration**: Enterprise-grade agent coordination
4. **Knowledge Graph**: Semantic relationship mapping
5. **Edge+Cloud Model**: Balanced cost and performance

---

## 📞 Support

- **Documentation**: See `ARCHITECTURE.md`
- **Issues**: Check logs in `Backend/logs/`
- **API Reference**: Available at `http://localhost:8000/docs` (Swagger UI)

---

## 📝 License

[Your License Here]

---

## 🙏 Acknowledgments

Built with:
- **OpenClaw**: Multi-agent orchestration framework
- **FastAPI**: Modern Python web framework
- **OpenAI**: Leading LLM provider
- **arXiv & GitHub**: Research source APIs

---

**Version**: 1.0.0  
**Last Updated**: May 5, 2026  
**Status**: Production-Ready

Happy researching! 🚀
