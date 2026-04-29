import { ConfigBlock } from "@/components/agent-view/overview/config-block";
import { IdentityBlock } from "@/components/agent-view/overview/identity-block";
import { IOFieldPreview } from "@/components/agent-view/overview/io-field-preview";
import { IOHero } from "@/components/agent-view/overview/io-hero";
import { MetricsValueTable } from "@/components/agent-view/overview/metrics-value-table";
import { ReproducibilityBlock } from "@/components/agent-view/overview/reproducibility-block";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mockUseAgentMeta = vi.fn();
const mockUseAgentGroup = vi.fn();
const mockUseAgentGroupMetrics = vi.fn();

vi.mock("@/hooks/use-runs", () => ({
  useAgentMeta: () => mockUseAgentMeta(),
  useAgentGroup: () => mockUseAgentGroup(),
  useAgentGroupMetrics: () => mockUseAgentGroupMetrics(),
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
  script: "examples/01_agent.py",
  event_counts: {},
  event_total: 2,
  duration_ms: 100,
  generations: [],
  iterations: [],
  rounds: [],
  candidates: [],
  batches: [],
  prompt_tokens: 0,
  completion_tokens: 0,
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
};

describe("Agent overview sparse states", () => {
  beforeEach(() => {
    mockUseAgentMeta.mockReset();
    mockUseAgentGroup.mockReset();
    mockUseAgentGroupMetrics.mockReset();
    mockUseAgentGroupMetrics.mockReturnValue({ data: undefined });
  });

  it("does not render blank hashes as valid chip values", () => {
    render(
      <ReproducibilityBlock
        dataInvocations={{
          agent_path: "Root",
          invocations: [
            {
              id: "Root:0",
              started_at: 1,
              status: "ok",
              hash_content: "abc123",
              hash_model: "",
              hash_config: "—",
            },
          ],
        }}
      />,
    );

    // hash_content chip is present and shows a value
    expect(screen.getByLabelText("hash_content hash")).toBeTruthy();
    // blank/empty hash chips render with "—" placeholder, not a real hash
    const modelChip = screen.getByLabelText("hash_model hash");
    expect(modelChip.textContent).toContain("—");
  });

  it("shows single-invocation metrics with custom values", () => {
    mockUseAgentGroup.mockReturnValue({
      data: {
        runs: [
          {
            ...summary,
            run_id: "run-0",
            duration_ms: 80,
            cost: { cost_usd: 0.002, prompt_tokens: 1, completion_tokens: 1 },
          },
          {
            ...summary,
            run_id: "run-1",
            duration_ms: 100,
            cost: { cost_usd: 0.004, prompt_tokens: 1, completion_tokens: 1 },
          },
        ],
      },
    });

    render(
      <MetricsValueTable
        dataSummary={{
          ...summary,
          duration_ms: 100,
          prompt_tokens: 12,
          completion_tokens: 8,
          cost: { prompt_tokens: 12, completion_tokens: 8, cost_usd: 0.004 },
          metrics: { exact_match: 1 },
        }}
        hashContent="abc123"
      />,
    );

    expect(screen.getByText("latency_ms")).toBeTruthy();
    expect(screen.getByText("exact_match")).toBeTruthy();
    expect(screen.getByText("12")).toBeTruthy();
  });

  it("shows composite configuration as leaf-owned instead of missing", () => {
    mockUseAgentMeta.mockReturnValue({
      data: {
        kind: "composite",
        config: null,
      },
    });

    render(<ConfigBlock dataSummary={summary} runId="run-1" />);

    expect(screen.getByText("lives on leaf agents")).toBeTruthy();
  });

  it("hides empty role and task rows for composites", () => {
    mockUseAgentMeta.mockReturnValue({
      data: {
        agent_path: "Root",
        class_name: "Root",
        kind: "composite",
        hash_content: "abc123",
        role: "",
        task: null,
        rules: [],
        examples: [],
        forward_in_overridden: false,
        forward_out_overridden: false,
      },
    });

    render(<IdentityBlock dataSummary={summary} runId="run-1" />);

    // The Field wrapper renders the label; without a role or task, it should
    // never show "role" or "task" as a label.
    expect(screen.queryByText("role")).toBeNull();
    expect(screen.queryByText("task")).toBeNull();
  });

  it("can expand long IO values without truncating them", () => {
    const long = `start-${"x".repeat(140)}-end`;
    render(<IOFieldPreview label="Output" data={{ answer: long }} />);

    expect(screen.getByText("show full")).toBeTruthy();
    fireEvent.click(screen.getByText("show full"));
    expect(screen.getByText((text) => text.includes("-end"))).toBeTruthy();
  });

  it("renders invocation IO values expanded without preview controls", () => {
    const long = `start-${"x".repeat(140)}-end`;

    const view = render(
      <IOHero
        dataInvocations={{
          agent_path: "Root",
          invocations: [
            {
              id: "Root:0",
              started_at: 1,
              status: "ok",
              input: { question: long },
              output: { answer: long },
            },
          ],
        }}
      />,
    );

    expect(within(view.container).queryByText("show full")).toBeNull();
    expect(within(view.container).queryByText("preview")).toBeNull();
    expect(within(view.container).queryByText("Copy as JSON")).toBeNull();
    expect(within(view.container).queryByLabelText(/collapse input/i)).toBeNull();
    expect(within(view.container).getByText("Input")).toBeTruthy();
    expect(within(view.container).getByText("Output")).toBeTruthy();
    expect(
      within(view.container).getAllByText((text) => text.includes("-end")).length,
    ).toBeGreaterThan(0);
  });
});
