# CLASH OF THE CLAWS
## MS Ramaiah Institute Of Technology
### Byte Sized Brains — *AI that finds what research is missing*

**Team Members:**
- Kotadia Nishka Ankitkumar
- Nidhi C A
- Kaninika Sardar
- Chiranth R Rao

| Tech Management, SRI-B

---

## Slide 2 — Problem Statement

**Why we selected this theme:**
Researchers face information overload – thousands of papers and no clear guidance on what's not done yet.

**What problem we are solving:**
Millions of papers exist, manual review is slow and often misses connections. Existing tools (search engines, ChatGPT) list facts but don't tell us what's missing.

**People facing this:**
Students and R&D teams waste time picking topics.

**Why Is It Important:**
The rapid growth of AI research has made it difficult to identify meaningful and unique innovation opportunities. Our system reduces research time by automatically detecting unexplored gaps and generating actionable project ideas for students, researchers, and organizations.

---

## Slide 3 — Current Solutions & Gaps

| Existing Solutions | What is Missing / Broken | Opportunity |
|---|---|---|
| Semantic Scholar, Elicit – paper search & summarization | No autonomous gap detection or innovation guidance | AI systems that identify unexplored research opportunities |
| ResearchRabbit, Connected Papers – citation & relationship visualization | No intelligent reasoning across papers | Multi-agent reasoning for cross-paper synthesis |
| Scite.ai, Consensus – evidence & citation analysis | Cannot suggest novel project/research ideas | AI-assisted idea generation for researchers and students |
| SciSpace, Perplexity AI – AI-based explanations & answers | Focus on information retrieval, not research direction | Transforming research tools from search engines into innovation discovery systems |

---

## Slide 4 — Our Solution

**What we built:**
We built an OpenClaw-inspired multi-agent AI platform that analyzes research papers, detects unexplored gaps, and generates innovative project ideas.

**Core Idea — The system uses multiple AI agents working together:**
- **Research Agent** fetches papers
- **Summarizer Agent** extracts key concepts
- **Gap Detection Agent** identifies unexplored areas
- **Idea Generator Agent** creates project ideas

**Key Features:**
- Multi-agent AI workflow
- Research analysis using arXiv API
- Automated gap detection
- AI-generated innovation ideas
- Real-time agent workflow visualization

---

## Slide 5 — Demo / Product Walkthrough

**Screen / Flow:**
1. User enters a research topic (e.g. *"Multi-Agent AI in Healthcare"*)
2. Research Agent fetches relevant papers and sources from arXiv
3. AI agents analyze concepts, trends, and relationships between papers
4. Gap Detection Agent identifies underexplored or missing research areas
5. Idea Generator Agent produces innovative project ideas and explanations
6. Final dashboard displays insights, gaps, knowledge graph, and AI-generated ideas

**How User Interacts:**
- User searches using natural language queries
- Live multi-agent workflow is visualized step-by-step
- Users can explore papers, detected gaps, and connected research domains
- Interactive knowledge graph shows relationships between concepts and papers
- Final research report can be viewed, copied, or downloaded instantly

**Key Moments:**
- Query transforms into structured research analysis in minutes
- Knowledge Graph visualizes hidden relationships across research areas
- Gap Detection highlights unexplored opportunities and missing links
- AI generates innovative, actionable project ideas with reasoning
- Final report combines insights, gaps, sources, and future directions in one place

---

## Slide 6 — Tech & Architecture

**Tech Stack:**

| Layer | Technology |
|---|---|
| Frontend | React 18, D3.js, Tailwind CSS |
| Backend | Python, FastAPI, SQLite |
| Streaming | Server-Sent Events (SSE) |
| CLI | Node.js, TypeScript |
| Deployment | Docker, Nginx |

**AI Usage:**
- **Model:** GPT-4o / Claude 3.5 (via OpenAI & Anthropic APIs)
- **Embeddings:** OpenAI `text-embedding-3-small` → falls back to HuggingFace `all-MiniLM-L6-v2` (runs fully local, no API key needed)
- **Framework:** Custom OpenClaw multi-agent orchestration — routes each agent to Edge (fast, local) or Cloud (powerful, async) execution based on task complexity

**System Flow:**
```
User Query
    ↓
Decomposer   →  breaks query into sub-questions
    ↓
Planner      →  builds targeted search strategy
    ↓
Search Agent →  hits arXiv + GitHub APIs in parallel
    ↓
Analyzer     →  deduplicates, ranks, extracts findings
    ↓
Graph Builder→  nodes + keyword/semantic edges
    ↓
Gap Detector →  finds unexplored research areas
    ↓
Idea Generator → scores ideas by impact · feasibility · novelty
    ↓
Synthesizer  →  final markdown report
```

---

## Slide 7 — Impact & Use Cases

**Real Life Scenarios:**

- **Academic Research:** Helps students and researchers quickly identify unique research ideas and unexplored topics, reducing time spent on literature review.
- **Tech Company R&D:** Assists organizations in discovering emerging AI trends and hidden innovation opportunities for smarter R&D decisions.
- **Interdisciplinary Research:** Detects missing links between domains like healthcare, cybersecurity, and AI to encourage breakthrough research.
- **Student Projects & Hackathons:** Suggests innovative and feasible project ideas based on current research gaps and trends.

**Scale Potential:**
- Expandable to domains like healthcare, robotics, finance, and cybersecurity
- Useful for universities, research labs, startups, and tech companies
- Can integrate with platforms like arXiv, GitHub, and Google Scholar
- Potential to evolve into an AI-powered research intelligence and innovation assistant

---

## Slide 8 — Differentiation

**Why Our Solution Stands Out:**
- Goes beyond paper search and summarization by identifying unexplored research gaps and innovation opportunities
- Uses a multi-agent AI workflow where specialized agents collaboratively analyze, connect, and reason over research data
- Combines research analysis, relationship mapping, gap detection, and idea generation into one intelligent platform

**Strong MOAT 1 — Autonomous Research Gap Discovery**

Our platform continuously analyzes relationships between papers, concepts, and domains to detect underexplored opportunities and missing research connections. This transforms research from passive information consumption into active innovation discovery.

**Strong MOAT 2 — OpenClaw-Inspired Multi-Agent Intelligence**

Instead of relying on a single AI response, multiple specialized agents collaborate through a shared orchestration pipeline for:
- Research analysis
- Relationship mapping
- Gap detection
- Idea generation

This creates deeper reasoning, more structured outputs, and a scalable research intelligence system that is difficult to replicate using traditional chatbot approaches.

---

## Slide 9 — Demo Link

- **GitHub Repo:** https://github.com/Nishka-kotadia/bytesizedbrains
- **Demo Video:** https://youtu.be/rVe3hUxbCJ8
- **Document Submitted:** https://docs.google.com/document/d/16ycUz44yu1JcO8KV4v_vRTKW1qv7_Idta3h94KF_ew/edit?usp=sharing
