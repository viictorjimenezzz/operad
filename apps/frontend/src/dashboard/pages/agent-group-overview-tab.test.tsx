import { AgentGroupOverviewTab } from "@/dashboard/pages/AgentGroupOverviewTab";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mockUseAgentGroup = vi.fn();
const mockUseAgentMeta = vi.fn();
const mockUsePatchRunNotes = vi.fn();

vi.mock("@/hooks/use-runs", () => ({
  useAgentGroup: () => mockUseAgentGroup(),
  useAgentMeta: () => mockUseAgentMeta(),
  usePatchRunNotes: () => mockUsePatchRunNotes(),
}));

const baseRun = {
  run_id: "run-1",
  started_at: 1000,
  last_event_at: 2000,
  state: "ended" as const,
  has_graph: false,
  is_algorithm: false,
  algorithm_path: null,
  algorithm_kinds: [],
  root_agent_path: "research_analyst",
  script: "example.py",
  event_counts: {},
  event_total: 1,
  duration_ms: 500,
  generations: [],
  iterations: [],
  rounds: [],
  candidates: [],
  batches: [],
  prompt_tokens: 100,
  completion_tokens: 50,
  metrics: {},
  notes_markdown: "",
  hash_content: "abc123def456",
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
  cost: { prompt_tokens: 100, completion_tokens: 50, cost_usd: 0.001 },
};

const baseGroup = {
  hash_content: "abc123def456",
  class_name: "ResearchAnalyst",
  root_agent_path: "research_analyst",
  count: 1,
  running: 0,
  errors: 0,
  last_seen: 2000,
  first_seen: 1000,
  latencies: [500],
  prompt_tokens: 100,
  completion_tokens: 50,
  cost_usd: 0.001,
  is_trainer: false,
  notes_markdown_count: 0,
};

function renderTab(hashContent = "abc123def456") {
  return render(
    <MemoryRouter initialEntries={[`/agents/${hashContent}/overview`]}>
      <Routes>
        <Route path="/agents/:hashContent/overview" element={<AgentGroupOverviewTab />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("AgentGroupOverviewTab", () => {
  beforeEach(() => {
    mockUseAgentMeta.mockReturnValue({ data: null });
    mockUsePatchRunNotes.mockReturnValue({ mutateAsync: vi.fn() });
  });

  it("N=1: does not render a Latency x invocation panel", () => {
    mockUseAgentGroup.mockReturnValue({
      data: { ...baseGroup, runs: [baseRun] },
    });

    renderTab();

    expect(screen.queryByText("Latency x invocation")).toBeNull();
    expect(screen.queryByText("Recent runs")).toBeNull();
  });

  it("N=1: renders activity strip metrics", () => {
    mockUseAgentGroup.mockReturnValue({
      data: { ...baseGroup, runs: [baseRun] },
    });

    renderTab();

    expect(screen.getAllByText("runs").length).toBeGreaterThan(0);
    expect(screen.getAllByText("ok").length).toBeGreaterThan(0);
    expect(screen.getAllByText("p50").length).toBeGreaterThan(0);
  });

  it("N=3: renders Invocation series panel and no Recent runs", () => {
    const runs = [
      { ...baseRun, run_id: "run-1", started_at: 1000 },
      { ...baseRun, run_id: "run-2", started_at: 2000 },
      { ...baseRun, run_id: "run-3", started_at: 3000 },
    ];
    mockUseAgentGroup.mockReturnValue({
      data: { ...baseGroup, count: 3, runs },
    });

    renderTab();

    expect(screen.getByText("Invocation series")).toBeTruthy();
    expect(screen.queryByText("Recent runs")).toBeNull();
    expect(screen.queryByText("Latency x invocation")).toBeNull();
  });

  it("N=3: renders metric toggle buttons", () => {
    const runs = [
      { ...baseRun, run_id: "run-1", started_at: 1000 },
      { ...baseRun, run_id: "run-2", started_at: 2000 },
      { ...baseRun, run_id: "run-3", started_at: 3000 },
    ];
    mockUseAgentGroup.mockReturnValue({
      data: { ...baseGroup, count: 3, runs },
    });

    renderTab();

    const buttons = screen.getAllByRole("button");
    const names = buttons.map((b) => b.textContent?.trim());
    expect(names).toContain("latency");
    expect(names).toContain("cost");
    expect(names).toContain("tokens");
  });
});
