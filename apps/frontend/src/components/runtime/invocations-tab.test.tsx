import {
  InvocationsTab,
  resolveAlgorithmColumns,
} from "@/components/runtime/invocations-tab";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

function makeClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 0, gcTime: 0 } },
  });
}

function renderTab(ui: ReactNode) {
  return render(
    <QueryClientProvider client={makeClient()}>
      <MemoryRouter initialEntries={["/algorithms/parent-run"]}>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

function makeChild(overrides: Record<string, unknown>) {
  return {
    run_id: "child-1",
    started_at: 10,
    last_event_at: 20,
    state: "ended",
    has_graph: true,
    is_algorithm: false,
    algorithm_path: null,
    algorithm_kinds: [],
    root_agent_path: "Root.Leaf",
    script: null,
    event_counts: { start: 1, end: 1 },
    event_total: 2,
    duration_ms: 1000,
    generations: [],
    iterations: [],
    rounds: [],
    candidates: [],
    batches: [],
    prompt_tokens: 12,
    completion_tokens: 8,
    error: null,
    algorithm_terminal_score: null,
    synthetic: true,
    parent_run_id: "parent-run",
    algorithm_class: null,
    hash_content: "hash-child",
    cost: { prompt_tokens: 12, completion_tokens: 8, cost_usd: 0.02 },
    metrics: { score: 0.82 },
    metadata: {},
    ...overrides,
  };
}

function mockFetch({
  runId,
  algorithmClass,
  child,
}: {
  runId: string;
  algorithmClass: string;
  child: Record<string, unknown>;
}) {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    if (url.endsWith(`/runs/${runId}/summary`)) {
      return new Response(
        JSON.stringify({
          run_id: runId,
          started_at: 1,
          last_event_at: 2,
          state: "ended",
          has_graph: true,
          is_algorithm: true,
          algorithm_path: algorithmClass,
          algorithm_kinds: [],
          root_agent_path: null,
          script: null,
          event_counts: {},
          event_total: 1,
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
          algorithm_class: algorithmClass,
        }),
        { status: 200, headers: { "content-type": "application/json" } },
      );
    }
    if (url.endsWith(`/runs/${runId}/children`)) {
      return new Response(JSON.stringify([child]), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }
    return new Response("not found", { status: 404 });
  });
}

beforeEach(() => {
  window.localStorage.clear();
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("<InvocationsTab />", () => {
  it("resolves descriptors for all algorithm classes and falls back to default", () => {
    expect(resolveAlgorithmColumns("Sweep").algorithmClass).toBe("Sweep");
    expect(resolveAlgorithmColumns("Beam").algorithmClass).toBe("Beam");
    expect(resolveAlgorithmColumns("Debate").algorithmClass).toBe("Debate");
    expect(resolveAlgorithmColumns("EvoGradient").algorithmClass).toBe("EvoGradient");
    expect(resolveAlgorithmColumns("Trainer").algorithmClass).toBe("Trainer");
    expect(resolveAlgorithmColumns("OPRO").algorithmClass).toBe("OPRO");
    expect(resolveAlgorithmColumns("SelfRefine").algorithmClass).toBe("SelfRefine");
    expect(resolveAlgorithmColumns("AutoResearcher").algorithmClass).toBe("AutoResearcher");
    expect(resolveAlgorithmColumns("TalkerReasoner").algorithmClass).toBe("TalkerReasoner");
    expect(resolveAlgorithmColumns("Verifier").algorithmClass).toBe("Verifier");
    expect(resolveAlgorithmColumns("Unknown").algorithmClass).toBe("__default__");
    expect(resolveAlgorithmColumns("BeamSearch").algorithmClass).toBe("Beam");
  });

  it("adds a langfuse column to every algorithm-specific descriptor", () => {
    const classes = [
      "Sweep",
      "Beam",
      "Debate",
      "EvoGradient",
      "Trainer",
      "OPRO",
      "SelfRefine",
      "AutoResearcher",
      "TalkerReasoner",
      "Verifier",
    ];
    for (const algorithmClass of classes) {
      const descriptor = resolveAlgorithmColumns(algorithmClass);
      expect(descriptor.columns.some((column) => column.id === "langfuse")).toBe(true);
    }
  });

  it.each([
    {
      algorithmClass: "Sweep",
      runId: "run-sweep",
      header: "Cell",
      value: "3",
      child: makeChild({
        metadata: { cell_index: 3, algorithm_axis_values: { lr: 0.15 } },
      }),
    },
    {
      algorithmClass: "Beam",
      runId: "run-beam",
      header: "Candidate",
      value: "5",
      child: makeChild({
        metadata: { iter_index: 2, candidate_index: 5 },
      }),
    },
    {
      algorithmClass: "Debate",
      runId: "run-debate",
      header: "Claim",
      value: "new claim",
      child: makeChild({
        metadata: { round_index: 1, speaker: "pro", claim: "new claim" },
      }),
    },
    {
      algorithmClass: "EvoGradient",
      runId: "run-evo",
      header: "Operator",
      value: "mutate",
      child: makeChild({
        metadata: { gen_index: 4, individual_id: "i-2", operator: "mutate" },
      }),
    },
    {
      algorithmClass: "Trainer",
      runId: "run-trainer",
      header: "Phase",
      value: "train",
      child: makeChild({
        metadata: { epoch: 7, batch_index: 12, phase: "train" },
        metrics: { train_loss: 0.33, val_loss: 0.41, lr: 0.0005 },
      }),
    },
    {
      algorithmClass: "OPRO",
      runId: "run-opro",
      header: "Prompt",
      value: "prompt b",
      child: makeChild({
        metadata: { iter_index: 8, role: "proposer", prompt: "prompt b" },
      }),
    },
    {
      algorithmClass: "SelfRefine",
      runId: "run-self",
      header: "Stop reason",
      value: "continue",
      child: makeChild({
        metadata: {
          iter_index: 4,
          phase: "reflect",
          stop_reason: "continue",
          response: "better answer",
        },
      }),
    },
    {
      algorithmClass: "AutoResearcher",
      runId: "run-auto",
      header: "Attempt",
      value: "search",
      child: makeChild({
        metadata: { attempt_index: 2, phase: "search", query: "gene editing" },
      }),
    },
    {
      algorithmClass: "TalkerReasoner",
      runId: "run-talker",
      header: "Router",
      value: "delegate",
      child: makeChild({
        metadata: { turn: 6, router_choice: "delegate", target_node: "node-b" },
      }),
    },
    {
      algorithmClass: "Verifier",
      runId: "run-verifier",
      header: "Accepted",
      value: "accepted",
      child: makeChild({
        metadata: { iter_index: 5, candidate_text: "candidate v2", accepted: true },
      }),
    },
  ])(
    "renders class-specific columns and fields for $algorithmClass",
    async ({ algorithmClass, runId, header, value, child }) => {
      mockFetch({ runId, algorithmClass, child });
      renderTab(<InvocationsTab runId={runId} />);

      expect((await screen.findAllByRole("button", { name: new RegExp(header, "i") })).length).toBeGreaterThan(0);
      expect((await screen.findAllByText(new RegExp(value, "i"))).length).toBeGreaterThan(0);
    },
  );

  it("uses default columns when the algorithm class is unknown", async () => {
    const runId = "run-unknown";
    mockFetch({
      runId,
      algorithmClass: "Unknown",
      child: makeChild({ metrics: { score: 0.42 } }),
    });
    renderTab(<InvocationsTab runId={runId} />);

    expect(await screen.findByRole("button", { name: /Started/i })).toBeTruthy();
    expect(await screen.findByRole("button", { name: /Duration/i })).toBeTruthy();
    expect(await screen.findByText("0.420")).toBeTruthy();
  });

  it("respects the algorithmClass prop override", async () => {
    const runId = "run-override";
    mockFetch({
      runId,
      algorithmClass: "Unknown",
      child: makeChild({ metadata: { cell_index: 9 } }),
    });
    renderTab(<InvocationsTab runId={runId} algorithmClass="Sweep" />);

    expect((await screen.findAllByRole("button", { name: /Cell/i })).length).toBeGreaterThan(0);
    expect(await screen.findByText("9")).toBeTruthy();
  });
});
