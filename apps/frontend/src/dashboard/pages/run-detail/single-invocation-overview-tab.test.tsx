import { ActivityStrip } from "@/components/agent-view/overview/run-status-strip";
import { AgentRunDetailLayout } from "@/dashboard/pages/run-detail/AgentRunDetailLayout";
import { SingleInvocationOverviewTab } from "@/dashboard/pages/run-detail/SingleInvocationOverviewTab";
import { cleanup, render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const hookMocks = vi.hoisted(() => ({
  useAgentMeta: vi.fn(),
  useDrift: vi.fn(),
  useRunEvents: vi.fn(),
  useRunSummary: vi.fn(),
  useRunInvocations: vi.fn(),
}));

vi.mock("@/hooks/use-runs", () => ({
  useAgentMeta: hookMocks.useAgentMeta,
  useDrift: hookMocks.useDrift,
  useRunEvents: hookMocks.useRunEvents,
  useRunSummary: hookMocks.useRunSummary,
  useRunInvocations: hookMocks.useRunInvocations,
}));

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
      config: {
        backend: "llamacpp",
        model: "test-model",
        sampling: { temperature: 0 },
        io: { renderer: "xml" },
      },
      prompt_system: "system prompt for this invocation",
      prompt_user: "user prompt for this invocation",
      input: { text: "hello" },
      output: { value: "world" },
    },
  ],
};

afterEach(cleanup);

describe("ActivityStrip", () => {
  beforeEach(() => {
    hookMocks.useRunSummary.mockReset();
    hookMocks.useRunInvocations.mockReset();
  });

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
    expect(link.closest("a")?.getAttribute("href")).toBe("https://langfuse.example.com/trace/123");
  });
});

describe("SingleInvocationOverviewTab", () => {
  beforeEach(() => {
    hookMocks.useAgentMeta.mockReturnValue({ data: { hash_content: "abc123" } });
    hookMocks.useDrift.mockReturnValue({ data: [] });
    hookMocks.useRunEvents.mockReturnValue({ data: { events: [] } });
    hookMocks.useRunSummary.mockReturnValue({ isLoading: false, data: summary });
    hookMocks.useRunInvocations.mockReturnValue({ isLoading: false, data: invocations });
  });

  it("shows invocation values, prompt, and runtime config without instance sections", () => {
    render(
      <MemoryRouter initialEntries={["/agents/abc123/runs/run-1"]}>
        <Routes>
          <Route
            path="/agents/:hashContent/runs/:runId"
            element={<SingleInvocationOverviewTab />}
          />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByText((text) => text.includes("hello"))).toBeTruthy();
    expect(screen.getByText((text) => text.includes("world"))).toBeTruthy();
    expect(screen.getByText("system prompt for this invocation")).toBeTruthy();
    expect(screen.getByText("user prompt for this invocation")).toBeTruthy();
    expect(screen.getByText((text) => text.includes("test-model"))).toBeTruthy();
    expect(screen.queryByRole("button", { name: "role" })).toBeNull();
    expect(screen.queryByRole("button", { name: "task" })).toBeNull();
    expect(screen.queryByText("structure")).toBeNull();
  });

  it("renders invocation tabs without a graph tab", () => {
    render(
      <MemoryRouter initialEntries={["/agents/abc123/runs/run-1"]}>
        <Routes>
          <Route path="/agents/:hashContent/runs/:runId" element={<AgentRunDetailLayout />}>
            <Route index element={<div>overview body</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    const sections = screen.getByRole("navigation", { name: /agent invocation path/i });
    expect(within(sections).getByText("Agents")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Overview" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "History" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Metrics" })).toBeTruthy();
    expect(screen.queryByRole("link", { name: "Graph" })).toBeNull();
    expect(screen.queryByText("langfuse")).toBeNull();
    expect(screen.queryByText("duration")).toBeNull();
  });
});
