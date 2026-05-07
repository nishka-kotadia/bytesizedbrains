# ResearchAI CLI

A transcript-based command-line interface for the Multi-Agent Research Intelligence System.

## Requirements

- **Node.js >= 22** (enforced at runtime; `.nvmrc` pins to 22)
- The Python backend running at `http://localhost:8000`

## Setup

```bash
cd CLI
node --version   # must be >= 22
npm install
```

## Usage

### Interactive mode (prompts for query and config)
```bash
node bin/research.js
```

### Single query with defaults
```bash
node bin/research.js "transformer attention mechanisms"
```

### Single query with custom config
```bash
node bin/research.js --depth Deep --max-sources 50 "CRISPR gene editing therapeutics"
```

### Skip config prompts (use defaults)
```bash
node bin/research.js --no-config "quantum computing error correction"
```

### List past research sessions
```bash
node bin/research.js --history
```

### Retrieve and display a past session
```bash
node bin/research.js --session <session-id>
```

### Help
```bash
node bin/research.js --help
```

## Options

| Flag | Description | Default |
|---|---|---|
| `--depth` | `Quick`, `Standard`, or `Deep` | `Standard` |
| `--max-sources` | Number of sources (5–50) | `20` |
| `--format` | `Markdown`, `Plain Text`, or `Structured JSON` | `Markdown` |
| `--no-config` | Skip config prompts | — |
| `--history` | List past sessions | — |
| `--session <id>` | Display a past session | — |

## Environment

| Variable | Description | Default |
|---|---|---|
| `RESEARCH_API_URL` | Backend base URL | `http://localhost:8000` |

## How it works

The CLI streams real-time pipeline events from the backend via Server-Sent Events (SSE) and prints a live **transcript** to the terminal:

```
[1/5] ▶ Decomposing query into sub-questions
       ✔ Generated 5 sub-question(s).
[2/5] ▶ Building research plan
       ✔ Created 8 search task(s).
[3/5] ▶ Searching academic databases & web
       ◆ [paper] Attention Is All You Need (arXiv, 2017) 94%
       ◆ [repo]  huggingface/transformers (GitHub, 2024) 87%
       ✔ Found 12 source(s).
[4/5] ▶ Analyzing and cross-referencing
       ✔ Analyzed 12 source(s).
[5/5] ▶ Synthesizing research report
       ✔ Research report synthesized.

── RESEARCH REPORT ──
...
```
