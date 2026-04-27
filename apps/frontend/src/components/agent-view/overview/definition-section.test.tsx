import { DefinitionSection } from "@/components/agent-view/overview/definition-section";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
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
};

describe("DefinitionSection", () => {
  beforeEach(() => {
    mockUseAgentMeta.mockReturnValue({
      data: {
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
      },
    });
  });

  it("opens from the section hash and renders flat sub-blocks", () => {
    render(
      <MemoryRouter initialEntries={["/agents/abc/runs/run-1#section=definition"]}>
        <DefinitionSection
          dataSummary={summary}
          dataInvocations={{
            agent_path: "Root.Reasoner",
            invocations: [
              {
                id: "Root.Reasoner:0",
                started_at: 1,
                status: "ok",
                backend: "openai",
                model: "gpt-4o-mini",
              },
            ],
          }}
          runId="run-1"
        />
      </MemoryRouter>,
    );

    expect(screen.getByText("Reasoner · openai/gpt-4o-mini · temp 0.4")).toBeTruthy();
    expect(screen.getByText("Identity")).toBeTruthy();
    expect(screen.getByText("Backend & sampling")).toBeTruthy();
    expect(screen.getByText("Configuration")).toBeTruthy();
    expect(document.querySelectorAll(".rounded-lg.border.border-border.bg-bg-1").length).toBe(1);
  });
});
