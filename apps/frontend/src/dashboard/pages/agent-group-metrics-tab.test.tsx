import { AgentGroupMetricsTab } from "@/dashboard/pages/AgentGroupMetricsTab";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mockUseAgentGroup = vi.fn();
const mockUseAgentGroupMetrics = vi.fn();

vi.mock("@/hooks/use-runs", () => ({
  useAgentGroup: () => mockUseAgentGroup(),
  useAgentGroupMetrics: () => mockUseAgentGroupMetrics(),
}));

const baseRun = (id: string, startedAt: number) => ({
  run_id: id,
  started_at: startedAt,
  last_event_at: startedAt + 1000,
  state: "ended" as const,
  has_graph: false,
  is_algorithm: false,
  algorithm_path: null,
  algorithm_kinds: [],
  root_agent_path: "research_analyst",
  script: "example.py",
  event_counts: {},
  event_total: 1,
  duration_ms: 500 + startedAt,
  generations: [],
  iterations: [],
  rounds: [],
  candidates: [],
  batches: [],
  prompt_tokens: 100 + startedAt,
  completion_tokens: 50,
  metrics: {},
  notes_markdown: "",
  hash_content: "abc123",
  hash_model: null,
  hash_prompt: null,
  hash_graph: null,
  hash_input: null,
  hash_output_schema: null,
  hash_config: null,
  backend: null,
  model: null,
  sampling: {},
  error: null,
  algorithm_terminal_score: null,
  synthetic: false,
  parent_run_id: null,
  algorithm_class: null,
  cost: { prompt_tokens: 100, completion_tokens: 50, cost_usd: 0.001 + startedAt * 0.0001 },
});

const baseGroup = (runs: ReturnType<typeof baseRun>[]) => ({
  hash_content: "abc123",
  class_name: "ResearchAnalyst",
  root_agent_path: "research_analyst",
  count: runs.length,
  running: 0,
  errors: 0,
  last_seen: 9000,
  first_seen: 1000,
  latencies: runs.map((r) => r.duration_ms),
  prompt_tokens: 100,
  completion_tokens: 50,
  cost_usd: 0.001,
  is_trainer: false,
  notes_markdown_count: 0,
  runs,
});

function renderTab(hashContent = "abc123") {
  return render(
    <MemoryRouter initialEntries={[`/agents/${hashContent}/metrics`]}>
      <Routes>
        <Route path="/agents/:hashContent/metrics" element={<AgentGroupMetricsTab />} />
      </Routes>
    </MemoryRouter>,
  );
}

afterEach(cleanup);

describe("AgentGroupMetricsTab", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseAgentGroupMetrics.mockReturnValue({ data: null });
  });

  it("N=1: renders metric cards without relationship charts", () => {
    const runs = [baseRun("r1", 1000)];
    mockUseAgentGroup.mockReturnValue({ data: baseGroup(runs) });

    renderTab();

    expect(screen.queryByText("Cost vs latency")).toBeNull();
    expect(screen.getByText("Latency")).toBeTruthy();
    expect(screen.getByText("Prompt tokens")).toBeTruthy();
    expect(screen.getByText("Output schema validation")).toBeTruthy();
    expect(screen.getAllByText("built-in").length).toBeGreaterThan(0);
  });

  it("N=3: renders relationship charts and metric cards", () => {
    const runs = [baseRun("r1", 1000), baseRun("r2", 2000), baseRun("r3", 3000)];
    mockUseAgentGroup.mockReturnValue({ data: baseGroup(runs) });

    renderTab();

    expect(screen.getAllByText("Cost vs latency").length).toBeGreaterThan(0);
    expect(screen.getByText("Tokens vs latency")).toBeTruthy();
    expect(screen.getByText("Latency")).toBeTruthy();
    expect(screen.getByText("Prompt tokens")).toBeTruthy();
    expect(screen.getAllByText("built-in").length).toBeGreaterThan(0);
  });

  it("N=8: renders series-capable metric cards with stats", () => {
    const runs = Array.from({ length: 8 }, (_, i) => baseRun(`r${i + 1}`, 1000 + i * 100)).map(
      (r, i) => ({ ...r, duration_ms: 400 + i * 80 }),
    );
    mockUseAgentGroup.mockReturnValue({ data: baseGroup(runs) });

    renderTab();

    expect(screen.getAllByText("Cost vs latency").length).toBeGreaterThan(0);
    expect(screen.getAllByText("p50").length).toBeGreaterThan(0);
    expect(screen.getAllByText("min").length).toBeGreaterThan(0);
    expect(screen.getAllByText("max").length).toBeGreaterThan(0);
  });

  it("N=8: keeps constant metrics visible as cards", () => {
    const runs = Array.from({ length: 8 }, (_, i) => baseRun(`r${i + 1}`, 1000 + i * 100)).map(
      (r) => ({ ...r, duration_ms: 400 }),
    );
    mockUseAgentGroup.mockReturnValue({ data: baseGroup(runs) });

    renderTab();

    expect(screen.getByText("Latency")).toBeTruthy();
    expect(screen.getAllByText("constant across invocations").length).toBeGreaterThan(0);
    expect(screen.getAllByText("built-in").length).toBeGreaterThan(0);
  });
});
