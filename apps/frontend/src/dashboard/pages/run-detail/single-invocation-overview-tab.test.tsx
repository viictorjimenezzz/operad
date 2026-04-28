import { ActivityStrip } from "@/components/agent-view/overview/run-status-strip";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

const summary = {
  run_id: "run-1",
  started_at: 1,
  last_event_at: 2,
  state: "ended",
  has_graph: true,
  is_algorithm: false,
  algorithm_path: null,
  algorithm_kinds: [],
  root_agent_path: "Root",
  script: null,
  event_counts: {},
  event_total: 2,
  duration_ms: 1420,
  generations: [],
  iterations: [],
  rounds: [],
  candidates: [],
  batches: [],
  prompt_tokens: 312,
  completion_tokens: 198,
  cost: { prompt_tokens: 312, completion_tokens: 198, cost_usd: 0.0042 },
  error: null,
  algorithm_terminal_score: null,
  synthetic: false,
  parent_run_id: null,
  algorithm_class: null,
  notes_markdown: "",
};

const invocations = {
  agent_path: "Root",
  invocations: [
    {
      id: "Root:0",
      started_at: 1,
      status: "ok",
      latency_ms: 1420,
      prompt_tokens: 312,
      completion_tokens: 198,
      cost_usd: 0.0042,
      hash_content: "abc123",
    },
  ],
};

describe("ActivityStrip", () => {
  it("renders state pill, duration, tokens, and cost", () => {
    render(
      <MemoryRouter>
        <ActivityStrip dataSummary={summary} dataInvocations={invocations} runId="run-1" />
      </MemoryRouter>,
    );

    expect(screen.getByText("ended")).toBeTruthy();
    expect(screen.getByText("1.4s")).toBeTruthy();
    expect(screen.getByText("510")).toBeTruthy();
    expect(screen.getByText("$0.0042")).toBeTruthy();
  });

  it("does not render Replay or Cassette replay buttons", () => {
    render(
      <MemoryRouter>
        <ActivityStrip dataSummary={summary} dataInvocations={invocations} runId="run-1" />
      </MemoryRouter>,
    );

    expect(screen.queryByText("Replay")).toBeNull();
    expect(screen.queryByText("Cassette replay")).toBeNull();
  });

  it("renders langfuse link when langfuse_url is present", () => {
    const invocationsWithLangfuse = {
      ...invocations,
      invocations: [
        { ...invocations.invocations[0], langfuse_url: "https://langfuse.example.com/trace/123" },
      ],
    };

    render(
      <MemoryRouter>
        <ActivityStrip
          dataSummary={summary}
          dataInvocations={invocationsWithLangfuse}
          runId="run-1"
        />
      </MemoryRouter>,
    );

    const link = screen.getByText("langfuse");
    expect(link).toBeTruthy();
    expect(link.closest("a")?.getAttribute("href")).toBe(
      "https://langfuse.example.com/trace/123",
    );
  });
});
