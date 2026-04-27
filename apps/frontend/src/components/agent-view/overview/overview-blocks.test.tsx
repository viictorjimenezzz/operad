import { ConfigBlock } from "@/components/agent-view/overview/config-block";
import { CostLatencyBlock } from "@/components/agent-view/overview/cost-latency-block";
import { IdentityBlock } from "@/components/agent-view/overview/identity-block";
import { IOFieldPreview } from "@/components/agent-view/overview/io-field-preview";
import { ReproducibilityBlock } from "@/components/agent-view/overview/reproducibility-block";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mockUseAgentMeta = vi.fn();

vi.mock("@/hooks/use-runs", () => ({
  useAgentMeta: () => mockUseAgentMeta(),
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
  error: null,
  algorithm_terminal_score: null,
  synthetic: false,
  parent_run_id: null,
  algorithm_class: null,
};

describe("Agent overview sparse states", () => {
  beforeEach(() => {
    mockUseAgentMeta.mockReset();
  });

  it("does not count blank hashes as reproducibility stability", () => {
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

    expect(screen.getByText(/1 baseline hash/)).toBeTruthy();
  });

  it("shows single-invocation latency while marking missing usage unavailable", () => {
    render(
      <CostLatencyBlock
        dataInvocations={{
          agent_path: "Root",
          invocations: [
            {
              id: "Root:0",
              started_at: 1,
              latency_ms: 42,
              prompt_tokens: null,
              completion_tokens: null,
              cost_usd: null,
              status: "ok",
            },
          ],
        }}
      />,
    );

    expect(screen.getByText("42ms")).toBeTruthy();
    expect(screen.getAllByText("unavailable").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("needs 2+")).toBeTruthy();
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
});
