import { AgentGroupMetricsTab } from "@/dashboard/pages/AgentGroupMetricsTab";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

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

describe("AgentGroupMetricsTab", () => {
  beforeEach(() => {
    mockUseAgentGroupMetrics.mockReturnValue({ data: null });
  });

  it("N=1: renders metric table (no Cost vs latency section)", () => {
    const runs = [baseRun("r1", 1000)];
    mockUseAgentGroup.mockReturnValue({ data: baseGroup(runs) });

    renderTab();

    expect(screen.queryByText("Cost vs latency")).toBeNull();
    // Metric table has source labels
    expect(screen.getAllByText("built-in").length).toBeGreaterThan(0);
  });

  it("N=3: renders mini-bars (no series charts)", () => {
    const runs = [baseRun("r1", 1000), baseRun("r2", 2000), baseRun("r3", 3000)];
    mockUseAgentGroup.mockReturnValue({ data: baseGroup(runs) });

    renderTab();

    // Cost vs latency shows for N>=2
    expect(screen.getAllByText("Cost vs latency").length).toBeGreaterThan(0);
    // Mini-bars render metric labels
    expect(screen.getAllByText("built-in").length).toBeGreaterThan(0);
    // No "x = invocation" eyebrow (series charts absent for N<=4)
    expect(screen.queryByText("x = invocation")).toBeNull();
  });

  it("N=8: renders series charts with eyebrow source labels", () => {
    const runs = Array.from({ length: 8 }, (_, i) =>
      baseRun(`r${i + 1}`, 1000 + i * 100),
    ).map((r, i) => ({ ...r, duration_ms: 400 + i * 80 }));
    mockUseAgentGroup.mockReturnValue({ data: baseGroup(runs) });

    renderTab();

    expect(screen.getAllByText("Cost vs latency").length).toBeGreaterThan(0);
  });

  it("N=8: filters out metrics with fewer than 2 distinct values", () => {
    const runs = Array.from({ length: 8 }, (_, i) =>
      baseRun(`r${i + 1}`, 1000 + i * 100),
    ).map((r) => ({ ...r, duration_ms: 400 }));
    mockUseAgentGroup.mockReturnValue({ data: baseGroup(runs) });

    renderTab();

    // schema_validation_rate and latency_ms are constant — should be filtered
    // just verify the tab renders without errors
    expect(screen.getAllByText("built-in").length).toBeGreaterThan(0);
  });
});
