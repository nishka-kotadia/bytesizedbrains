# 🔬 Prism — Multi-Agent Research Intelligence System

> Turn any research question into a structured report, knowledge graph, gap analysis, and actionable ideas — in minutes.

---

## 🚩 Problem

Research is broken for anyone moving fast.

- **Too much noise** — thousands of papers, repos, and articles with no way to see how they connect
- **No gap visibility** — you don't know what *hasn't* been explored until you've read everything
- **Manual synthesis** — copy-pasting findings across tabs, losing context, missing relationships
- **Ideas stay shallow** — without a map of existing work, new ideas lack grounding or novelty scoring

Researchers, engineers, and students waste hours just *orienting* themselves before doing any real thinking.

---

## ✅ Solution

Prism is an autonomous multi-agent system that does the heavy lifting for you.

You type a question. Prism runs a pipeline of 8 specialized AI agents that search, analyze, map relationships, detect gaps, and generate scored research ideas — all streamed live to your browser.

**What you get:**
- 📄 A structured research report (markdown, ready to share)
- 🔗 An interactive knowledge graph showing how sources relate
- 🕳️ Research gaps — areas nobody has explored yet
- 💡 Novel ideas scored by impact, feasibility, and novelty
- 📚 Ranked source list with key findings per paper/repo

---

## 🏗️ Architecture

```
User Query
    ↓
Decomposer   →  breaks query into focused sub-questions
Planner      →  builds a targeted search strategy
Search       →  hits arXiv + GitHub APIs concurrently
Analyzer     →  deduplicates, ranks, extracts key findings
GraphBuilder →  creates nodes + semantic/keyword edges
GapDetector  →  finds unexplored intersections
IdeaGenerator→  generates ideas scored by impact · feasibility · novelty
Synthesizer  →  writes the final report
    ↓
React UI  ·  D3 Knowledge Graph  ·  SSE Live Streaming
```

All agents are orchestrated via **OpenClaw** — a protocol adapter that routes each agent to edge (fast, local) or cloud (powerful) execution based on task complexity.

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, D3.js, Tailwind CSS |
| Backend | Python, FastAPI, SQLite |
| Streaming | Server-Sent Events (SSE) |
| AI Models | GPT-4o / Claude 3.5 (OpenAI & Anthropic APIs) |
| Embeddings | OpenAI `text-embedding-3-small` or HuggingFace `all-MiniLM-L6-v2` (local fallback) |
| Agent Framework | OpenClaw SDK |
| CLI | Node.js, TypeScript |
| Deployment | Docker, Nginx |

---

## ⚙️ Setup

### Prerequisites

- Python 3.10+
- Node.js 18+
- An OpenAI **or** Anthropic API key (at least one required)

---

### 1. Clone the repo

```bash
git clone https://github.com/Nishka-kotadia/bytesizedbrains.git
cd bytesizedbrains
```

---

### 2. Backend setup

```bash
cd Backend

# Create and activate virtual environment
python -m venv venv

# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
```

Edit `.env` and fill in your credentials:

```env
LLM_PROVIDER=openai          # openai | anthropic | groq
LLM_MODEL=gpt-4o-mini        # or claude-3-5-sonnet-20241022
LLM_API_KEY=sk-...           # your API key
```

Start the backend:

```bash
python main.py
```

Server runs at `http://localhost:8000`
Swagger docs at `http://localhost:8000/docs`

---

### 3. Frontend setup

```bash
cd Frontend
python -m http.server 3000
```

Open `http://localhost:3000` in your browser.

---

### 4. CLI setup (optional)

```bash
cd CLI
npm install
npm start
```

---

### 5. Docker (all-in-one)

```bash
docker-compose up --build
```

- Frontend → `http://localhost:3000`
- Backend → `http://localhost:8000`

---

## 🚀 Usage

### Web UI

1. Open `http://localhost:3000`
2. Type your research question in the search bar
3. Choose depth: **Quick** (1–2 min) · **Standard** (3–5 min) · **Deep** (10–15 min)
4. Hit **Search** and watch the agents work in real time
5. Explore your results across 5 tabs:
   - **Report** — full synthesized markdown report
   - **Sources** — ranked papers and repos with key findings
   - **Gaps** — unexplored research areas with severity scores
   - **Ideas** — novel directions scored by impact, feasibility, novelty
   - **Knowledge Graph** — interactive D3 graph, drag nodes, zoom, click to open sources

---

### API

Start a research session:

```bash
curl -X POST http://localhost:8000/api/research \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Multi-agent reasoning in LLMs",
    "config": {
      "depth": "Standard",
      "maxSources": 20,
      "format": "Markdown",
      "sources": { "papers": true, "web": true }
    }
  }'
```

Stream live progress:

```bash
curl http://localhost:8000/api/research/{session_id}/stream
```

---

### CLI

```bash
research
# Enter your query when prompted
# Follow the interactive prompts for depth and source types
```

---

## 📁 Project Structure

```
Prism/
├── Backend/
│   ├── agents/          # 8 pipeline agents
│   ├── api/             # FastAPI server + LLM abstraction
│   ├── knowledge_graph/ # Embeddings + graph storage
│   ├── models/          # Pydantic data models
│   ├── db/              # SQLite persistence
│   ├── adapters/        # OpenClaw protocol adapter
│   ├── config/          # Agent + embedding config
│   ├── requirements.txt
│   └── main.py
├── Frontend/
│   └── index.html       # React + D3 single-page app
├── CLI/
│   ├── src/             # TypeScript API client
│   └── bin/research.js  # CLI entry point
├── docker-compose.yml
└── README.md
```

---

## 🔑 Environment Variables

| Variable | Required | Description |
|---|---|---|
| `LLM_PROVIDER` | ✅ | `openai`, `anthropic`, or `groq` |
| `LLM_MODEL` | ✅ | e.g. `gpt-4o-mini`, `claude-3-5-sonnet-20241022` |
| `LLM_API_KEY` | ✅ | Your API key for the chosen provider |

> **No embeddings API key?** Prism automatically falls back to HuggingFace `all-MiniLM-L6-v2` which runs fully locally — no key needed.

---

## 🐛 Troubleshooting

**Backend won't start**
→ Make sure `.env` exists and `LLM_API_KEY` is set

**0 edges in knowledge graph**
→ Normal on first run if embeddings are slow to load — keyword-overlap edges are built as fallback automatically

**arXiv returns no results**
→ Try a more specific query; arXiv rate-limits aggressive searches

**GitHub search empty**
→ GitHub's unauthenticated API has a low rate limit — wait 60s and retry

---

## 📝 License

MIT
