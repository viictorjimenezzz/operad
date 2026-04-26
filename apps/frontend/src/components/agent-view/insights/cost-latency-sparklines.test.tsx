import { CostLatencySparklines } from "@/components/agent-view/insights/cost-latency-sparklines";
import type { RunInvocation } from "@/lib/types";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

function makeInvocation(
  id: string,
  latencyMs: number,
  costUsd: number,
  tokens: number,
): RunInvocation {
  return {
    id,
    started_at: 100,
    finished_at: 101,
    latency_ms: latencyMs,
    prompt_tokens: tokens / 2,
    completion_tokens: tokens / 2,
    cost_usd: costUsd,
    hash_model: "m",
    hash_prompt: "p",
    hash_graph: "g",
    hash_input: "i",
    hash_output_schema: "o",
    hash_config: "c",
    hash_content: "k",
    status: "ok",
    error: null,
    langfuse_url: null,
    script: null,
    backend: null,
    model: null,
    renderer: null,
  };
}

describe("CostLatencySparklines", () => {
  it("renders empty state when fewer than 2 points", () => {
    render(<CostLatencySparklines invocations={[makeInvocation("i1", 10, 0.001, 20)]} />);
    expect(screen.getByText(/not enough data/i)).toBeTruthy();
  });

  it("renders totals for normal series", () => {
    render(
      <CostLatencySparklines
        invocations={[makeInvocation("i1", 1000, 0.1, 200), makeInvocation("i2", 3000, 0.2, 100)]}
      />,
    );
    expect(screen.getByText(/total cost:/i)).toBeTruthy();
    expect(screen.getByText(/300 tokens/i)).toBeTruthy();
  });
});
