import { AgentsTab } from "@/components/agent-view/page-shell/agents-tab";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

function makeClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 0, gcTime: 0 } },
  });
}

function LocationProbe() {
  const location = useLocation();
  return <div data-testid="location">{location.pathname}</div>;
}

function renderTab(ui: ReactNode) {
  return render(
    <QueryClientProvider client={makeClient()}>
      <MemoryRouter initialEntries={["/algorithms/parent-run"]}>
        {ui}
        <LocationProbe />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function child(runId: string, hash: string, agent: string) {
  return {
    run_id: runId,
    started_at: 10,
    last_event_at: 11,
    state: "ended",
    has_graph: true,
    is_algorithm: false,
    algorithm_path: null,
    algorithm_kinds: [],
    root_agent_path: `Root.${agent}`,
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
    hash_content: hash,
    metrics: { score: 0.75 },
    metadata: { algorithm_axis_values: { lr: 0.1, model: "small" } },
    cost: { prompt_tokens: 12, completion_tokens: 8, cost_usd: 0.02 },
  };
}

beforeEach(() => {
  vi.useRealTimers();
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("<AgentsTab />", () => {
  it("fetches child runs, renders a RunTable, and navigates rows to the agent run", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify([child("child-1", "hash-a", "Planner")]), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );

    renderTab(<AgentsTab runId="parent-run" />);

    expect(await screen.findByText("Planner")).toBeTruthy();
    expect(screen.getByText("hash-a")).toBeTruthy();
    fireEvent.click(screen.getByText("Planner"));

    await waitFor(() => {
      expect(screen.getByTestId("location").textContent).toBe("/agents/hash-a/runs/child-1");
    });
  });

  it("supports flat mode and algorithm-specific extra columns", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify([child("cell-1", "hash-cell", "Reasoner")]), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );

    renderTab(
      <AgentsTab runId="parent-run" groupBy="none" extraColumns={["axisValues", "score"]} />,
    );

    expect(await screen.findByText("lr=0.1, model=small")).toBeTruthy();
    expect(screen.getByText("0.750")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /hash-cell/ })).toBeNull();
  });

  it("uses the universal empty state copy when there are no synthetic children", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify([]), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );

    renderTab(<AgentsTab runId="parent-run" />);

    expect(await screen.findByText("no agent invocations yet")).toBeTruthy();
  });

  it("renders Beam event invocations as a flat RunTable", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ run_id: "parent-run", agents: [] }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );

    renderTab(
      <AgentsTab
        runId="parent-run"
        mode="invocations"
        dataEvents={[
          {
            type: "agent_event",
            run_id: "parent-run",
            agent_path: "Reasoner",
            kind: "end",
            input: { goal: "x" },
            output: {
              response: { answer: "candidate" },
              latency_ms: 123,
              prompt_tokens: 10,
              completion_tokens: 5,
              cost_usd: 0.01,
              backend: "gemini",
              model: "gemini-2.5-flash",
              hash_prompt: "prompt-hash",
            },
            started_at: 10,
            finished_at: 11,
            metadata: {
              invoke_id: "inv-1",
              class_name: "Reasoner",
              hash_content: "hash-reasoner",
            },
          },
        ]}
        dataAgentsSummary={{
          run_id: "parent-run",
          agents: [{ agent_path: "Reasoner", langfuse_url: "https://langfuse.test/trace/parent" }],
        }}
      />,
    );

    expect(screen.getByText("1 agent invocation")).toBeTruthy();
    expect(screen.getByText("Reasoner")).toBeTruthy();
    expect(screen.getByText("gemini")).toBeTruthy();
    expect(screen.getByText("gemini-2.5-flash")).toBeTruthy();
    expect(screen.getByText("prompt-hash")).toBeTruthy();
    expect(screen.getByRole("link", { name: "open" }).getAttribute("href")).toBe(
      "https://langfuse.test/trace/parent",
    );
    fireEvent.click(screen.getByText("Reasoner"));

    await waitFor(() => {
      expect(screen.getByTestId("location").textContent).toBe(
        "/agents/hash-reasoner/runs/parent-run",
      );
    });
  });
});
