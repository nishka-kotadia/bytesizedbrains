/**
 * Shared TypeScript types and interfaces for the PRISM research system.
 * Used across Frontend, CLI, and API communication.
 */

// ─── Research Domain Types ───────────────────────────────────────────────────

export enum DepthLevel {
  Quick = "Quick",
  Standard = "Standard",
  Deep = "Deep",
}

export enum OutputFormat {
  Markdown = "Markdown",
  PlainText = "Plain Text",
  StructuredJSON = "Structured JSON",
}

export interface SourceConfig {
  papers: boolean;
  web: boolean;
  patents: boolean;
  news: boolean;
}

export interface ResearchConfig {
  depth: DepthLevel;
  sources: SourceConfig;
  maxSources: number;
  format: OutputFormat;
}

// ─── Research Execution Types ────────────────────────────────────────────────

export interface ResearchRequest {
  query: string;
  config: ResearchConfig;
}

export interface ResearchResponse {
  session_id: string;
  stream_url: string;
}

// ─── Knowledge Graph Types ───────────────────────────────────────────────────

export interface GraphNode {
  node_id: string;
  title: string;
  authors: string;
  venue: string;
  year: number;
  source_type: "paper" | "repo";
  url: string;
  abstract?: string;
  embedding?: number[];
  relevance_score: number;
  importance_score: number;
  keywords: string[];
}

export enum RelationshipType {
  Cites = "cites",
  Extends = "extends",
  Contradicts = "contradicts",
  Complements = "complements",
  BuildsUpon = "builds_upon",
  Refutes = "refutes",
  Related = "related",
}

export interface GraphEdge {
  edge_id: string;
  source_node_id: string;
  target_node_id: string;
  relationship_type: RelationshipType;
  confidence_score: number;
  reason?: string;
  evidence: string[];
}

export interface KnowledgeGraph {
  graph_id: string;
  created_at: string;
  statistics: {
    node_count: number;
    edge_count: number;
    gap_count: number;
    idea_count: number;
  };
  nodes: Record<string, GraphNode>;
  edges: Record<string, GraphEdge>;
  gaps: Record<string, ResearchGap>;
  ideas: Record<string, ResearchIdea>;
}

// ─── Gap Detection Types ─────────────────────────────────────────────────────

export interface ResearchGap {
  gap_id: string;
  title: string;
  description: string;
  affected_nodes: string[];
  missing_intersections: Array<{ [key: string]: string }>;
  severity_score: number;
  discovered_at: string;
}

// ─── Idea Generation Types ───────────────────────────────────────────────────

export interface ResearchIdea {
  idea_id: string;
  title: string;
  description: string;
  hypothesis?: string;
  impact_score: number;
  feasibility_score: number;
  novelty_score: number;
  supporting_gaps: string[];
  related_nodes: string[];
  next_steps: string[];
  generated_at: string;
}

// ─── Source/Paper Types ──────────────────────────────────────────────────────

export interface Source {
  id: string;
  type: "paper" | "repo";
  title: string;
  authors: string;
  venue: string;
  year: number;
  url: string;
  abstract: string;
  relevance: number;
  key_findings?: string;
  embedding?: number[];
}

// ─── Session Types ───────────────────────────────────────────────────────────

export enum SessionStatus {
  Pending = "pending",
  Running = "running",
  Complete = "complete",
  Error = "error",
}

export interface Session {
  session_id: string;
  query: string;
  config: ResearchConfig;
  status: SessionStatus;
  sources: Source[];
  report?: string;
  gaps?: ResearchGap[];
  ideas?: ResearchIdea[];
  knowledge_graph?: KnowledgeGraph;
  error_msg?: string;
  created_at: string;
  completed_at?: string;
}

// ─── SSE Event Types ─────────────────────────────────────────────────────────

export type SSEEvent =
  | StepStartEvent
  | StepCompleteEvent
  | SourceFoundEvent
  | GapDetectedEvent
  | IdeaGeneratedEvent
  | PipelineCompleteEvent
  | PipelineErrorEvent;

export interface StepStartEvent {
  type: "step_start";
  data: {
    step_name: string;
    step_index: number;
    label: string;
  };
}

export interface StepCompleteEvent {
  type: "step_complete";
  data: {
    step_name: string;
    step_index: number;
    summary: string;
  };
}

export interface SourceFoundEvent {
  type: "source_found";
  data: {
    title: string;
    authors: string;
    venue: string;
    year: number;
    relevance: number;
    type: "paper" | "repo";
    url: string;
  };
}

export interface GapDetectedEvent {
  type: "gap_detected";
  data: ResearchGap;
}

export interface IdeaGeneratedEvent {
  type: "idea_generated";
  data: ResearchIdea;
}

export interface PipelineCompleteEvent {
  type: "pipeline_complete";
  data: {
    report: string;
    sources: Source[];
    gaps: ResearchGap[];
    ideas: ResearchIdea[];
    knowledge_graph: KnowledgeGraph;
  };
}

export interface PipelineErrorEvent {
  type: "pipeline_error";
  data: {
    error: string;
  };
}

// ─── OpenClaw Types ──────────────────────────────────────────────────────────

export enum ExecutionMode {
  Edge = "edge",
  Cloud = "cloud",
  Auto = "auto",
}

export enum AgentCapability {
  Decompose = "decompose",
  Plan = "plan",
  Search = "search",
  Analyze = "analyze",
  DetectGaps = "detect_gaps",
  GenerateIdeas = "generate_ideas",
  Synthesize = "synthesize",
}

export interface AgentStatus {
  agent_id: string;
  capability: AgentCapability;
  execution_mode: ExecutionMode;
  model: string;
  available: boolean;
}
