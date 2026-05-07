/**
 * TypeScript API Client for PRISM research system.
 * Provides type-safe communication with the FastAPI backend.
 */

import type {
  ResearchRequest,
  ResearchResponse,
  Session,
  SSEEvent,
  DepthLevel,
  OutputFormat,
  SourceConfig,
} from "./types";

export class PrismAPIClient {
  private baseUrl: string;

  constructor(baseUrl: string = "http://localhost:8000") {
    this.baseUrl = baseUrl;
  }

  /**
   * Start a research session with a query and configuration.
   */
  async startResearch(request: ResearchRequest): Promise<ResearchResponse> {
    const response = await fetch(`${this.baseUrl}/api/research`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      throw new Error(`API error: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Stream research progress via Server-Sent Events.
   */
  streamResearchProgress(
    sessionId: string,
    onEvent: (event: SSEEvent) => void,
    onError: (error: Error) => void
  ): EventSource {
    const eventSource = new EventSource(
      `${this.baseUrl}/api/research/${sessionId}/stream`
    );

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        onEvent(data);
      } catch (error) {
        onError(
          error instanceof Error
            ? error
            : new Error("Failed to parse event")
        );
      }
    };

    eventSource.onerror = (error) => {
      onError(new Error("SSE connection error"));
      eventSource.close();
    };

    return eventSource;
  }

  /**
   * Get research history (past sessions).
   */
  async getHistory(limit: number = 10): Promise<Session[]> {
    const response = await fetch(
      `${this.baseUrl}/api/history?limit=${limit}`
    );

    if (!response.ok) {
      throw new Error(`API error: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Get a specific research session by ID.
   */
  async getSession(sessionId: string): Promise<Session> {
    const response = await fetch(
      `${this.baseUrl}/api/history/${sessionId}`
    );

    if (!response.ok) {
      throw new Error(`API error: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Delete a research session.
   */
  async deleteSession(sessionId: string): Promise<void> {
    const response = await fetch(
      `${this.baseUrl}/api/history/${sessionId}`,
      {
        method: "DELETE",
      }
    );

    if (!response.ok) {
      throw new Error(`API error: ${response.statusText}`);
    }
  }

  /**
   * Get system health status.
   */
  async getHealth(): Promise<{
    status: string;
    version: string;
    llm_provider: string;
    llm_model: string;
  }> {
    const response = await fetch(`${this.baseUrl}/api/health`);

    if (!response.ok) {
      throw new Error(`API error: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Create a default research configuration.
   */
  static createDefaultConfig() {
    return {
      depth: "Standard" as DepthLevel,
      sources: {
        papers: true,
        web: true,
        patents: false,
        news: false,
      } as SourceConfig,
      maxSources: 20,
      format: "Markdown" as OutputFormat,
    };
  }
}

/**
 * Create a session-specific API client helper.
 */
export class ResearchSession {
  private client: PrismAPIClient;
  private sessionId: string;
  private eventSource?: EventSource;

  constructor(client: PrismAPIClient, sessionId: string) {
    this.client = client;
    this.sessionId = sessionId;
  }

  /**
   * Stream progress and return final result.
   */
  async watchProgress(
    onEvent: (event: SSEEvent) => void,
    onError: (error: Error) => void
  ): Promise<void> {
    return new Promise((resolve, reject) => {
      this.eventSource = this.client.streamResearchProgress(
        this.sessionId,
        (event) => {
          onEvent(event);
          if (
            event.type === "pipeline_complete" ||
            event.type === "pipeline_error"
          ) {
            resolve();
          }
        },
        (error) => {
          onError(error);
          reject(error);
        }
      );
    });
  }

  /**
   * Stop streaming.
   */
  stopWatching(): void {
    if (this.eventSource) {
      this.eventSource.close();
    }
  }

  /**
   * Get final session result.
   */
  async getResult(): Promise<Session> {
    return this.client.getSession(this.sessionId);
  }
}
