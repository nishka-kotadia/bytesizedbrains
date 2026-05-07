#!/usr/bin/env node

/**
 * ResearchAI — Transcript-based CLI
 *
 * Requires Node.js >= 22 (uses built-in readline/promises, fetch, and
 * EventSource via the eventsource npm package).
 *
 * Usage:
 *   node bin/research.js [query]          # run a single query
 *   node bin/research.js                  # interactive mode
 *   node bin/research.js --history        # list past sessions
 *   node bin/research.js --session <id>   # retrieve a past session
 *   node bin/research.js --help           # show help
 *
 * Environment:
 *   RESEARCH_API_URL   Base URL of the backend (default: http://localhost:8000)
 */

import { createInterface } from "node:readline/promises";
import { stdin as input, stdout as output, argv, exit } from "node:process";
import EventSource from "eventsource";

// ─── Node version guard ───────────────────────────────────────────────────────
const [major] = process.versions.node.split(".").map(Number);
if (major < 22) {
  console.error(
    `\x1b[31mError:\x1b[0m ResearchAI CLI requires Node.js >= 22. ` +
      `You are running ${process.version}.`
  );
  exit(1);
}

// ─── Config ───────────────────────────────────────────────────────────────────
const API_BASE = process.env.RESEARCH_API_URL ?? "http://localhost:8000";

// ─── ANSI helpers ─────────────────────────────────────────────────────────────
const c = {
  reset:   "\x1b[0m",
  bold:    "\x1b[1m",
  faint:   "\x1b[2m",
  cyan:    "\x1b[36m",
  green:   "\x1b[32m",
  yellow:  "\x1b[33m",
  red:     "\x1b[31m",
  magenta: "\x1b[35m",
  blue:    "\x1b[34m",
  white:   "\x1b[37m",
  gray:    "\x1b[90m",
};

const fmt = {
  header:  (s) => `${c.bold}${c.cyan}${s}${c.reset}`,
  step:    (s) => `${c.bold}${c.blue}${s}${c.reset}`,
  done:    (s) => `${c.green}✔${c.reset} ${s}`,
  source:  (s) => `${c.magenta}◆${c.reset} ${s}`,
  error:   (s) => `${c.red}✖ ${s}${c.reset}`,
  label:   (s) => `${c.bold}${c.white}${s}${c.reset}`,
  dim:     (s) => `${c.faint}${s}${c.reset}`,
  section: (s) => `\n${c.bold}${c.yellow}── ${s} ──${c.reset}`,
};

// ─── Transcript class ─────────────────────────────────────────────────────────
/**
 * Transcript accumulates all pipeline events and renders them to stdout.
 * Each event is printed immediately (live streaming) and also stored so
 * the full transcript can be replayed or saved.
 */
class Transcript {
  #lines = [];

  #emit(line) {
    this.#lines.push(line);
    console.log(line);
  }

  banner(query) {
    this.#emit("");
    this.#emit(fmt.header("╔══════════════════════════════════════════════════╗"));
    this.#emit(fmt.header("║          ResearchAI — Autonomous Research        ║"));
    this.#emit(fmt.header("╚══════════════════════════════════════════════════╝"));
    this.#emit("");
    this.#emit(`${fmt.label("Query:")} ${query}`);
    this.#emit(fmt.dim(`API:   ${API_BASE}`));
    this.#emit("");
  }

  stepStart(stepIndex, stepName, label) {
    this.#emit(
      `${fmt.dim(`[${stepIndex + 1}/5]`)} ${fmt.step("▶")} ${label}`
    );
  }

  stepComplete(stepIndex, stepName, summary) {
    this.#emit(`       ${fmt.done(summary)}`);
  }

  sourceFound(source) {
    const relevanceColor =
      source.relevance >= 90
        ? c.green
        : source.relevance >= 75
        ? c.yellow
        : c.gray;
    const rel = `${relevanceColor}${source.relevance}%${c.reset}`;
    const typeTag =
      source.type === "paper"
        ? `${c.cyan}[paper]${c.reset}`
        : `${c.magenta}[repo]${c.reset}`;
    this.#emit(
      `       ${fmt.source(`${typeTag} ${source.title} ${fmt.dim(`(${source.venue}, ${source.year})`)} ${rel}`)}`
    );
  }

  pipelineComplete(report, sources, gaps = [], ideas = [], graph = null) {
    this.#emit("");
    this.#emit(fmt.section("RESEARCH REPORT"));
    this.#emit("");

    // Render Markdown-ish report to terminal
    const reportText =
      typeof report === "string" ? report : JSON.stringify(report, null, 2);
    for (const line of reportText.split("\n")) {
      if (line.startsWith("## ")) {
        this.#emit(`\n${c.bold}${c.cyan}${line.slice(3).toUpperCase()}${c.reset}`);
      } else if (line.startsWith("### ")) {
        this.#emit(`\n${c.bold}${line.slice(4)}${c.reset}`);
      } else if (line.startsWith("- ")) {
        this.#emit(`  ${c.yellow}•${c.reset} ${line.slice(2)}`);
      } else if (line.trim() === "") {
        this.#emit("");
      } else {
        this.#emit(`  ${line}`);
      }
    }

    this.#emit("");
    this.#emit(fmt.section(`SOURCES (${sources.length})`));
    for (const [i, src] of sources.entries()) {
      this.#emit(
        `  ${fmt.dim(`${i + 1}.`)} ${c.bold}${src.title}${c.reset} ` +
          `${fmt.dim(`— ${src.authors} (${src.year})`)} ` +
          `${c.cyan}${src.url}${c.reset}`
      );
    }

    // Knowledge Graph stats
    if (graph) {
      this.#emit("");
      this.#emit(fmt.section("KNOWLEDGE GRAPH"));
      this.#emit(`  ${fmt.label("Nodes:")} ${graph.statistics?.node_count ?? 0}  ${fmt.label("Edges:")} ${graph.statistics?.edge_count ?? 0}  ${fmt.label("Gaps:")} ${graph.statistics?.gap_count ?? 0}  ${fmt.label("Ideas:")} ${graph.statistics?.idea_count ?? 0}`);
    }

    // Research Gaps
    if (gaps && gaps.length > 0) {
      this.#emit("");
      this.#emit(fmt.section(`RESEARCH GAPS (${gaps.length})`));
      for (const [i, gap] of gaps.entries()) {
        const sev = gap.severity_score >= 0.7 ? c.red : gap.severity_score >= 0.4 ? c.yellow : c.gray;
        this.#emit(`  ${fmt.dim(`${i + 1}.`)} ${c.bold}${gap.title}${c.reset} ${sev}[severity: ${(gap.severity_score * 100).toFixed(0)}%]${c.reset}`);
        this.#emit(`     ${fmt.dim(gap.description)}`);
      }
    }

    // Research Ideas
    if (ideas && ideas.length > 0) {
      this.#emit("");
      this.#emit(fmt.section(`ACTIONABLE IDEAS (${ideas.length})`));
      for (const [i, idea] of ideas.entries()) {
        const impact = `${c.green}impact:${(idea.impact_score * 100).toFixed(0)}%${c.reset}`;
        const novelty = `${c.cyan}novelty:${(idea.novelty_score * 100).toFixed(0)}%${c.reset}`;
        const feasibility = `${c.yellow}feasibility:${(idea.feasibility_score * 100).toFixed(0)}%${c.reset}`;
        this.#emit(`  ${fmt.dim(`${i + 1}.`)} ${c.bold}${idea.title}${c.reset}  ${impact}  ${novelty}  ${feasibility}`);
        this.#emit(`     ${fmt.dim(idea.description)}`);
        if (idea.hypothesis) {
          this.#emit(`     ${c.magenta}Hypothesis:${c.reset} ${fmt.dim(idea.hypothesis)}`);
        }
        if (idea.next_steps && idea.next_steps.length > 0) {
          this.#emit(`     ${c.bold}Next steps:${c.reset}`);
          for (const step of idea.next_steps) {
            this.#emit(`       ${c.yellow}→${c.reset} ${step}`);
          }
        }
      }
    }

    this.#emit("");
    this.#emit(fmt.done("Research complete."));
    this.#emit("");
  }

  pipelineError(message) {
    this.#emit("");
    this.#emit(fmt.error(`Pipeline error: ${message}`));
    this.#emit("");
  }

  /** Return the full transcript as a plain-text string (ANSI stripped). */
  toPlainText() {
    // Strip ANSI escape codes
    return this.#lines
      .map((l) => l.replace(/\x1b\[[0-9;]*m/g, ""))
      .join("\n");
  }
}

// ─── API helpers ──────────────────────────────────────────────────────────────
async function checkHealth() {
  const res = await fetch(`${API_BASE}/api/health`);
  if (!res.ok) throw new Error(`Health check failed: HTTP ${res.status}`);
  return res.json();
}

async function startResearch(query, config = {}) {
  const body = {
    query,
    config: {
      depth: config.depth ?? "Standard",
      sources: config.sources ?? { papers: true, web: true, patents: false, news: false },
      maxSources: config.maxSources ?? 20,
      format: config.format ?? "Markdown",
    },
  };

  const res = await fetch(`${API_BASE}/api/research`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? `HTTP ${res.status}`);
  }

  return res.json(); // { session_id, stream_url }
}

async function getHistory() {
  const res = await fetch(`${API_BASE}/api/history`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function getSession(sessionId) {
  const res = await fetch(`${API_BASE}/api/history/${sessionId}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

// ─── Stream pipeline events ───────────────────────────────────────────────────
function streamPipeline(streamUrl, transcript) {
  return new Promise((resolve, reject) => {
    const es = new EventSource(streamUrl);

    es.addEventListener("step_start", (e) => {
      const d = JSON.parse(e.data);
      transcript.stepStart(d.step_index, d.step_name, d.label);
    });

    es.addEventListener("step_complete", (e) => {
      const d = JSON.parse(e.data);
      transcript.stepComplete(d.step_index, d.step_name, d.summary);
    });

    es.addEventListener("source_found", (e) => {
      const d = JSON.parse(e.data);
      transcript.sourceFound(d);
    });

    es.addEventListener("pipeline_complete", (e) => {
      const d = JSON.parse(e.data);
      es.close();
      transcript.pipelineComplete(d.report, d.sources ?? [], d.gaps ?? [], d.ideas ?? [], d.knowledge_graph ?? null);
      resolve({ report: d.report, sources: d.sources ?? [], gaps: d.gaps ?? [], ideas: d.ideas ?? [] });
    });

    es.addEventListener("pipeline_error", (e) => {
      const d = JSON.parse(e.data);
      es.close();
      transcript.pipelineError(d.error);
      reject(new Error(d.error));
    });

    es.onerror = () => {
      es.close();
      const msg = "Connection to research server lost.";
      transcript.pipelineError(msg);
      reject(new Error(msg));
    };
  });
}

// ─── Config prompt ────────────────────────────────────────────────────────────
async function promptConfig(rl) {
  console.log(fmt.dim("\nConfiguration (press Enter to accept defaults):"));

  const depthInput = await rl.question(
    `  Depth ${fmt.dim("[Quick / Standard / Deep]")} (Standard): `
  );
  const depth = ["Quick", "Standard", "Deep"].includes(depthInput.trim())
    ? depthInput.trim()
    : "Standard";

  const maxInput = await rl.question(
    `  Max sources ${fmt.dim("[5-50]")} (20): `
  );
  const maxSources = Math.min(50, Math.max(5, parseInt(maxInput) || 20));

  const formatInput = await rl.question(
    `  Output format ${fmt.dim("[Markdown / Plain Text / Structured JSON]")} (Markdown): `
  );
  const format = ["Markdown", "Plain Text", "Structured JSON"].includes(
    formatInput.trim()
  )
    ? formatInput.trim()
    : "Markdown";

  console.log("");
  return { depth, maxSources, format };
}

// ─── Commands ─────────────────────────────────────────────────────────────────
async function cmdResearch(query, config) {
  const transcript = new Transcript();
  transcript.banner(query);

  // Health check
  try {
    const health = await checkHealth();
    console.log(
      fmt.dim(
        `Backend: ${health.status} | ${health.llm_provider}/${health.llm_model} | v${health.version}`
      )
    );
    console.log("");
  } catch {
    console.error(fmt.error("Cannot reach backend at " + API_BASE));
    console.error(fmt.dim("Start the backend with: python Backend/main.py"));
    exit(1);
  }

  const { session_id, stream_url } = await startResearch(query, config);
  console.log(fmt.dim(`Session: ${session_id}`));
  console.log("");

  await streamPipeline(stream_url, transcript);
}

async function cmdHistory() {
  const sessions = await getHistory();
  if (sessions.length === 0) {
    console.log(fmt.dim("No research history found."));
    return;
  }
  console.log(fmt.header("\nResearch History"));
  console.log(fmt.dim("─".repeat(60)));
  for (const s of sessions) {
    const date = new Date(s.completed_at).toLocaleString();
    console.log(
      `  ${c.cyan}${s.session_id.slice(0, 8)}…${c.reset}  ` +
        `${c.bold}${s.query}${c.reset}  ${fmt.dim(date)}`
    );
  }
  console.log("");
}

async function cmdSession(sessionId) {
  const session = await getSession(sessionId);
  const transcript = new Transcript();
  transcript.banner(session.query);
  transcript.pipelineComplete(
    session.report ?? "(no report)",
    session.sources ?? [],
    session.gaps ?? [],
    session.ideas ?? [],
    session.knowledge_graph ?? null
  );
}

function cmdHelp() {
  console.log(`
${fmt.header("ResearchAI CLI")} — Transcript-based research assistant

${fmt.label("Usage:")}
  node bin/research.js [query]           Run a research query
  node bin/research.js                   Interactive mode (prompts for query)
  node bin/research.js --history         List past research sessions
  node bin/research.js --session <id>    Retrieve and display a past session
  node bin/research.js --help            Show this help

${fmt.label("Options:")}
  --depth <Quick|Standard|Deep>          Research depth (default: Standard)
  --max-sources <n>                      Max sources 5-50 (default: 20)
  --format <Markdown|Plain Text|JSON>    Output format (default: Markdown)
  --no-config                            Skip config prompts, use defaults

${fmt.label("Environment:")}
  RESEARCH_API_URL   Backend base URL (default: http://localhost:8000)

${fmt.label("Examples:")}
  node bin/research.js "transformer attention mechanisms"
  node bin/research.js --depth Deep --max-sources 50 "CRISPR therapeutics"
  node bin/research.js --history
  node bin/research.js --session abc12345
`);
}

// ─── Argument parser ──────────────────────────────────────────────────────────
function parseArgs(args) {
  const result = {
    command: "research",
    query: null,
    config: {},
    interactive: false,
    noConfig: false,
  };

  const positional = [];
  let i = 0;
  while (i < args.length) {
    const a = args[i];
    if (a === "--help" || a === "-h") {
      result.command = "help";
    } else if (a === "--history") {
      result.command = "history";
    } else if (a === "--session") {
      result.command = "session";
      result.sessionId = args[++i];
    } else if (a === "--depth") {
      result.config.depth = args[++i];
    } else if (a === "--max-sources") {
      result.config.maxSources = parseInt(args[++i]);
    } else if (a === "--format") {
      result.config.format = args[++i];
    } else if (a === "--no-config") {
      result.noConfig = true;
    } else if (!a.startsWith("--")) {
      positional.push(a);
    }
    i++;
  }

  if (positional.length > 0) {
    result.query = positional.join(" ");
  } else if (result.command === "research") {
    result.interactive = true;
  }

  return result;
}

// ─── Main ─────────────────────────────────────────────────────────────────────
async function main() {
  const args = parseArgs(argv.slice(2));

  if (args.command === "help") {
    cmdHelp();
    return;
  }

  if (args.command === "history") {
    await cmdHistory();
    return;
  }

  if (args.command === "session") {
    if (!args.sessionId) {
      console.error(fmt.error("--session requires a session ID argument."));
      exit(1);
    }
    await cmdSession(args.sessionId);
    return;
  }

  // Research command
  let query = args.query;
  let config = { ...args.config };

  const rl = createInterface({ input, output });

  try {
    if (args.interactive) {
      console.log(fmt.header("\nResearchAI — Transcript CLI"));
      console.log(fmt.dim("Type your research query below. Ctrl+C to exit.\n"));
      query = await rl.question(`${fmt.label("Research query:")} `);
      if (!query.trim()) {
        console.log(fmt.dim("No query entered. Exiting."));
        return;
      }
      query = query.trim();
    }

    if (!args.noConfig && Object.keys(config).length === 0) {
      config = await promptConfig(rl);
    }
  } finally {
    rl.close();
  }

  await cmdResearch(query, config);
}

main().catch((err) => {
  console.error(fmt.error(err.message));
  exit(1);
});
