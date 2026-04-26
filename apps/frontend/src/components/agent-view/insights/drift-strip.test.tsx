import { DriftStrip } from "@/components/agent-view/insights/drift-strip";
import type { RunInvocation, RunSummary } from "@/lib/types";
import { useUIStore } from "@/stores/ui";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

const summary: RunSummary = {
  run_id: "run-1",
  started_at: 100,
  last_event_at: 105,
  state: "running",
  has_graph: true,
  is_algorithm: false,
  algorithm_path: null,
  algorithm_kinds: [],
  root_agent_path: "Root",
  script: null,
  event_counts: {},
  event_total: 3,
  duration_ms: 1000,
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

function makeInvocation(id: string, hashPrompt: string, hashInput = "input-a"): RunInvocation {
  return {
    id,
    started_at: 100,
    finished_at: 101,
    latency_ms: 1000,
    prompt_tokens: 10,
    completion_tokens: 5,
    cost_usd: 0.01,
    hash_model: "m1",
    hash_prompt: hashPrompt,
    hash_graph: "g1",
    hash_input: hashInput,
    hash_output_schema: "o1",
    hash_config: "c1",
    hash_content: "k1",
    status: "ok",
    error: null,
    langfuse_url: null,
    script: null,
    backend: null,
    model: null,
    renderer: null,
    input: { question: "q" },
    output: null,
  };
}

describe("DriftStrip", () => {
  beforeEach(() => useUIStore.setState({ drawer: null }));

  it("shows caption stats", () => {
    render(
      <DriftStrip
        rootPath="Root"
        summary={summary}
        invocations={[makeInvocation("i1", "h1"), makeInvocation("i2", "h2"), makeInvocation("i3", "h2")]}
      />,
    );
    expect(screen.getByText(/3 invocations/i)).toBeTruthy();
    expect(screen.getByText(/2 unique prompts/i)).toBeTruthy();
  });

  it("opens prompts drawer on transition marker click", () => {
    const { container } = render(
      <DriftStrip
        rootPath="Root"
        summary={summary}
        invocations={[makeInvocation("i1", "h1"), makeInvocation("i2", "h2"), makeInvocation("i3", "h2")]}
      />,
    );
    const marker = container.querySelector("line");
    expect(marker).not.toBeNull();
    if (!marker) return;
    fireEvent.click(marker);
    expect(useUIStore.getState().drawer).toEqual({
      kind: "prompts",
      payload: { agentPath: "Root", focus: "i2" },
    });
  });
});
