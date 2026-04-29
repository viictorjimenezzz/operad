import { AgentGroupOverviewTab } from "@/dashboard/pages/AgentGroupOverviewTab";
import { dashboardApi } from "@/lib/api/dashboard";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mockUseAgentGroup = vi.fn();
const mockUseAgentMeta = vi.fn();
const mockAgentPrompts = vi.mocked(dashboardApi.agentPrompts);
const mockRunInvocations = vi.mocked(dashboardApi.runInvocations);
const mockAgentGroupReproducibility = vi.mocked(dashboardApi.agentGroupReproducibility);

vi.mock("@/hooks/use-runs", () => ({
  useAgentGroup: () => mockUseAgentGroup(),
  useAgentMeta: () => mockUseAgentMeta(),
}));

vi.mock("@/lib/api/dashboard", () => ({
  dashboardApi: {
    agentPrompts: vi.fn(),
    runInvocations: vi.fn(),
    agentGroupReproducibility: vi.fn(),
  },
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
  hash_prompt: "prompt-hash",
  hash_graph: null,
  hash_input: "input-hash",
  hash_output_schema: "output-schema-hash",
  hash_config: null,
  backend: "gemini",
  model: "gemini-2.5-flash",
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
  backends: ["gemini"],
  models: ["gemini-2.5-flash"],
  is_trainer: false,
  notes_markdown_count: 0,
};

const meta = {
  agent_path: "research_analyst",
  class_name: "ResearchAnalyst",
  kind: "leaf" as const,
  hash_content: "abc123def456",
  role: "Invariant system prompt.",
  task: "Answer the question.",
  rules: ["Stay concise."],
  examples: [],
  config: {
    backend: "gemini",
    model: "gemini-2.5-flash",
    sampling: { temperature: 0, max_tokens: 1024 },
    resilience: { timeout: 180, max_retries: 2 },
    io: { renderer: "xml" },
    runtime: {},
  },
  input_schema: {
    key: "__main__.Question",
    name: "Question",
    fields: [
      {
        name: "question",
        type: "str",
        description: "Question text to answer.",
        required: true,
        has_default: false,
        default: null,
        enum_values: null,
        system: false,
      },
    ],
  },
  output_schema: {
    key: "__main__.Answer",
    name: "Answer",
    fields: [
      {
        name: "answer",
        type: "str",
        description: "Final answer body.",
        required: true,
        has_default: false,
        default: null,
        enum_values: null,
        system: false,
      },
    ],
  },
  forward_in_overridden: false,
  forward_out_overridden: false,
  forward_in_doc: null,
  forward_out_doc: null,
  trainable_paths: ["role", "task"],
  langfuse_search_url: null,
};

function renderTab(hashContent = "abc123def456") {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[`/agents/${hashContent}/overview`]}>
        <Routes>
          <Route path="/agents/:hashContent/overview" element={<AgentGroupOverviewTab />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(cleanup);

describe("AgentGroupOverviewTab", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseAgentMeta.mockReturnValue({ data: meta });
    mockAgentPrompts.mockResolvedValue({
      agent_path: "research_analyst",
      renderer: "xml",
      entries: [
        {
          invocation_id: "research_analyst:0",
          started_at: 1000,
          hash_prompt: "prompt-hash",
          system: "<role>Invariant system prompt.</role>",
          user: "<input><question>latest invocation secret</question></input>",
          replayed: true,
        },
      ],
    });
    mockRunInvocations.mockResolvedValue({
      agent_path: "research_analyst",
      invocations: [
        {
          id: "research_analyst:0",
          started_at: 1000,
          finished_at: null,
          latency_ms: null,
          prompt_tokens: null,
          completion_tokens: null,
          cost_usd: null,
          hash_model: null,
          hash_prompt: null,
          hash_graph: null,
          hash_input: null,
          hash_output_schema: null,
          hash_config: null,
          hash_content: null,
          status: "ok",
          error: null,
          langfuse_url: null,
          script: null,
          backend: null,
          model: null,
          renderer: null,
          config: null,
          prompt_system: null,
          prompt_user: null,
          input: { question: "latest invocation secret" },
          output: { answer: "final answer" },
        },
      ],
    });
    mockAgentGroupReproducibility.mockResolvedValue({
      hash_content: "abc123def456",
      count: 1,
      hashes: {
        hash_content: "abc123def456",
        hash_model: null,
        hash_prompt_template: "prompt-template-hash",
        hash_input_schema: "input-schema-hash",
        hash_output_schema: "output-schema-hash",
        hash_graph: null,
        hash_config: null,
      },
    });
  });

  it("multi-run overview renders identity and KPI content", () => {
    const runs = [
      { ...baseRun, run_id: "run-1", started_at: 1000 },
      { ...baseRun, run_id: "run-2", started_at: 2000 },
      { ...baseRun, run_id: "run-3", started_at: 3000 },
    ];
    mockUseAgentGroup.mockReturnValue({
      data: { ...baseGroup, count: 3, runs },
    });

    renderTab();

    expect(screen.getByText("ResearchAnalyst")).toBeTruthy();
    expect(screen.getAllByText("runs").length).toBeGreaterThan(0);
    expect(screen.getAllByText("ok").length).toBeGreaterThan(0);
    expect(screen.getByText("CONTRACT")).toBeTruthy();
    expect(screen.getByText("SYSTEM PROMPT · XML")).toBeTruthy();
    expect(screen.getByText("REPRODUCIBILITY")).toBeTruthy();
  });

  it("renders input/output schema fields and latest invocation values", async () => {
    mockUseAgentGroup.mockReturnValue({
      data: { ...baseGroup, runs: [baseRun] },
    });

    renderTab();

    expect(screen.getByText("Question")).toBeTruthy();
    expect(screen.getAllByText("question").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Question text to answer.").length).toBeGreaterThan(0);
    expect(screen.getByText("Answer")).toBeTruthy();
    expect(screen.getByText("answer")).toBeTruthy();
    expect(screen.getByText("Final answer body.")).toBeTruthy();
    await waitFor(() => expect(screen.getByText("latest invocation secret")).toBeTruthy());
  });

  it("renders a field/value prompt view instead of raw prompt XML", async () => {
    mockUseAgentGroup.mockReturnValue({
      data: { ...baseGroup, runs: [baseRun] },
    });

    renderTab();

    await waitFor(() => expect(mockAgentPrompts).toHaveBeenCalled());
    await waitFor(() => expect(mockRunInvocations).toHaveBeenCalled());
    const text = document.body.textContent ?? "";
    expect(text).toContain("Invariant system prompt.");
    expect(text).toContain("latest invocation secret");
    expect(text).not.toContain("<input><question>");
  });
});
