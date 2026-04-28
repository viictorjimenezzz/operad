import { DefinitionPanel } from "@/components/agent-view/overview/definition-section";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mockUseAgentMeta = vi.fn();
const mutateAsync = vi.fn();

vi.mock("@/hooks/use-runs", () => ({
  useAgentMeta: () => mockUseAgentMeta(),
  usePatchRunNotes: () => ({ mutateAsync }),
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
  root_agent_path: "Root.Reasoner",
  script: null,
  event_counts: {},
  event_total: 2,
  duration_ms: 100,
  generations: [],
  iterations: [],
  rounds: [],
  candidates: [],
  batches: [],
  prompt_tokens: 1,
  completion_tokens: 2,
  error: null,
  algorithm_terminal_score: null,
  synthetic: false,
  parent_run_id: null,
  algorithm_class: null,
  notes_markdown: "initial note",
};

const metaData = {
  agent_path: "Root.Reasoner",
  class_name: "Reasoner",
  kind: "leaf",
  hash_content: "abc123",
  role: "Science explainer",
  task: "Answer clearly",
  rules: ["Be concise"],
  examples: [{ input: { text: "why" }, output: { text: "because" } }],
  config: {
    backend: "openai",
    model: "gpt-4o-mini",
    sampling: { temperature: 0.4 },
    resilience: {},
    io: {},
    runtime: {},
  },
  input_schema: null,
  output_schema: null,
  forward_in_overridden: false,
  forward_out_overridden: false,
  trainable_paths: [],
};

describe("DefinitionPanel", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    mutateAsync.mockReset();
    mockUseAgentMeta.mockReturnValue({ data: metaData });
  });

  it("renders tab strip with role, task, rules, examples, config, notes tabs", () => {
    render(
      <MemoryRouter>
        <DefinitionPanel
          dataSummary={summary}
          dataInvocations={{ agent_path: "Root.Reasoner", invocations: [] }}
          runId="run-1"
        />
      </MemoryRouter>,
    );

    expect(screen.getByText("role")).toBeTruthy();
    expect(screen.getByText("task")).toBeTruthy();
    expect(screen.getByText("rules (1)")).toBeTruthy();
    expect(screen.getByText("examples (1)")).toBeTruthy();
    expect(screen.getByText("config")).toBeTruthy();
    expect(screen.getByText("notes")).toBeTruthy();
  });

  it("shows role content by default and switches to task tab", () => {
    render(
      <MemoryRouter>
        <DefinitionPanel
          dataSummary={summary}
          dataInvocations={{ agent_path: "Root.Reasoner", invocations: [] }}
          runId="run-1"
        />
      </MemoryRouter>,
    );

    expect(screen.getAllByText("Science explainer").length).toBeGreaterThan(0);

    fireEvent.click(screen.getByText("task"));
    expect(screen.getAllByText("Answer clearly").length).toBeGreaterThan(0);
    // role content is no longer visible after switching
    expect(screen.queryByText("Science explainer")).toBeNull();
  });

  it("renders rules list when rules tab is active", () => {
    render(
      <MemoryRouter>
        <DefinitionPanel
          dataSummary={summary}
          dataInvocations={{ agent_path: "Root.Reasoner", invocations: [] }}
          runId="run-1"
        />
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByText("rules (1)"));
    expect(screen.getByText("Be concise")).toBeTruthy();
  });

  it("does not render IdentityBlock JSON dump", () => {
    render(
      <MemoryRouter>
        <DefinitionPanel
          dataSummary={summary}
          dataInvocations={{ agent_path: "Root.Reasoner", invocations: [] }}
          runId="run-1"
        />
      </MemoryRouter>,
    );

    expect(screen.queryByText("Identity")).toBeNull();
    expect(screen.queryByText("Backend & sampling")).toBeNull();
  });
});
