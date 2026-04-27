import { OPROHistoryTab, buildOPROSteps } from "@/components/algorithms/opro/opro-history-tab";
import type { RunSummary } from "@/lib/types";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

afterEach(cleanup);

describe("OPROHistoryTab", () => {
  it("pairs propose and evaluate events into step cards", () => {
    render(
      <MemoryRouter initialEntries={["/opro/opro-run?step=2"]}>
        <OPROHistoryTab dataEvents={events} dataChildren={children} />
      </MemoryRouter>,
    );

    expect(screen.getByText("step 1")).toBeTruthy();
    expect(screen.getByText("step 2")).toBeTruthy();
    expect(screen.getByText("accepted")).toBeTruthy();
    expect(screen.getByText("rejected")).toBeTruthy();
    expect(screen.getByText(/second candidate/)).toBeTruthy();
    expect(screen.getAllByText("Open proposer invocation")).toHaveLength(2);
    expect(screen.getAllByText("Open evaluator invocation")).toHaveLength(2);
  });

  it("exposes inferred proposer and evaluator children", () => {
    const steps = buildOPROSteps(undefined, events, children);

    expect(steps).toHaveLength(2);
    expect(steps[0]?.proposerRun?.run_id).toBe("proposer-1");
    expect(steps[0]?.evaluatorRun?.run_id).toBe("evaluator-1");
    expect(steps[1]?.accepted).toBe(false);
  });
});

const events = {
  run_id: "opro-run",
  events: [
    iteration("propose", 1, { candidate_value: "first candidate", history_size: 0 }, 1),
    iteration(
      "evaluate",
      1,
      { candidate_value: "first candidate", score: 0.51, accepted: true },
      2,
    ),
    iteration("propose", 2, { candidate_value: "second candidate", history_size: 1 }, 3),
    iteration(
      "evaluate",
      2,
      { candidate_value: "second candidate", score: 0.42, accepted: false },
      4,
    ),
  ],
};

const children: RunSummary[] = [
  child("proposer-1", 1.1),
  child("evaluator-1", 1.2),
  child("proposer-2", 3.1),
  child("evaluator-2", 3.2),
];

function iteration(
  phase: "propose" | "evaluate",
  step: number,
  extra: Record<string, unknown>,
  t: number,
) {
  return {
    type: "algo_event",
    run_id: "opro-run",
    algorithm_path: "OPRO",
    kind: "iteration",
    payload: {
      iter_index: step,
      step_index: step,
      phase,
      param_path: "rules",
      ...extra,
    },
    started_at: t,
    finished_at: phase === "evaluate" ? t : null,
    metadata: {},
  };
}

function child(runId: string, t: number): RunSummary {
  return {
    run_id: runId,
    started_at: t,
    last_event_at: t,
    state: "ended",
    has_graph: false,
    is_algorithm: false,
    algorithm_path: null,
    algorithm_kinds: [],
    root_agent_path: "OptimizerAgent",
    script: null,
    event_counts: {},
    event_total: 1,
    duration_ms: 10,
    generations: [],
    iterations: [],
    rounds: [],
    candidates: [],
    batches: [],
    prompt_tokens: 0,
    completion_tokens: 0,
    error: null,
    algorithm_terminal_score: null,
    synthetic: true,
    parent_run_id: "opro-run",
    algorithm_class: null,
    cost: { prompt_tokens: 0, completion_tokens: 0, cost_usd: 0.001 },
  };
}
