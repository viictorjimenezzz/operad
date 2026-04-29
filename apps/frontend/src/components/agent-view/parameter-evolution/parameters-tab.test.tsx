import { ParametersTab } from "@/components/agent-view/parameter-evolution/parameters-tab";
import type { AgentGraphResponse, AgentParametersResponse, RunSummary } from "@/lib/types";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("ParametersTab", () => {
  it("renders run-scope structure and opens gradient context in the drawer", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/runs/run-1/agent_graph") return jsonResponse(graph);
      if (url === "/runs/run-1/agent/Root.leaf/parameters") return jsonResponse(parameters);
      if (url === "/runs/run-1/parameter-evolution/Root.leaf.role") {
        return jsonResponse({
          path: "Root.leaf.role",
          type: "text",
          points: [
            {
              run_id: "run-1",
              started_at: 10,
              value: "old role",
              hash: "aaa111",
              gradient: null,
              source_tape_step: null,
              langfuse_url: null,
              metric_snapshot: null,
            },
            {
              run_id: "run-1",
              started_at: 20,
              value: "new role",
              hash: "bbb222",
              gradient: {
                message: "tighten role wording",
                severity: "high",
                target_paths: ["Root.leaf.role"],
              },
              source_tape_step: { epoch: 1, batch: 2, iter: 3, optimizer_step: 4 },
              langfuse_url: "http://langfuse/trace/run-1",
              metric_snapshot: { train_loss: 0.4 },
            },
          ],
        });
      }
      throw new Error(`unexpected fetch ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithProviders(
      <MemoryRouter initialEntries={["/algorithms/run-1?tab=parameters"]}>
        <ParametersTab runId="run-1" scope="run" />
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByText("trainable params")).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: /Leaf leaf/ }));
    fireEvent.click(screen.getByRole("button", { name: /role old role/ }));

    expect(await screen.findByRole("dialog")).toBeTruthy();
    expect(await screen.findByText("tighten role wording")).toBeTruthy();
    expect(screen.getByText("optimizer_step")).toBeTruthy();
  });

  it("renders group-scope history and uses the group gradient fallback copy", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/agents/hash-1") {
        return jsonResponse({
          hash_content: "hash-1",
          class_name: "Root",
          root_agent_path: "Root",
          count: 2,
          running: 0,
          errors: 0,
          last_seen: 20,
          first_seen: 10,
          is_trainer: true,
          runs: [runSummary("run-0", 10), runSummary("run-1", 20)],
        });
      }
      if (url === "/api/agents/hash-1/parameters") {
        return jsonResponse({
          hash_content: "hash-1",
          paths: ["Root.leaf.role"],
          series: [
            {
              run_id: "run-0",
              started_at: 10,
              values: { "Root.leaf.role": { value: "old role", hash: "aaa111" } },
            },
            {
              run_id: "run-1",
              started_at: 20,
              values: { "Root.leaf.role": { value: "new role", hash: "bbb222" } },
            },
          ],
        });
      }
      if (url === "/runs/run-1/agent_graph") return jsonResponse(graph);
      if (url === "/runs/run-1/agent/Root.leaf/parameters") return jsonResponse(parameters);
      throw new Error(`unexpected fetch ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithProviders(
      <MemoryRouter initialEntries={["/agents/hash-1/training"]}>
        <ParametersTab hashContent="hash-1" scope="group" />
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByText("trainable params")).toBeTruthy());
    expect(screen.getByRole("button", { name: /role old role/ })).toBeTruthy();
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(await screen.findByText("open a run for gradient context")).toBeTruthy();
    expect(screen.getByText(/aggregates across 2 invocations/)).toBeTruthy();
  });
});

function renderWithProviders(children: ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={client}>{children}</QueryClientProvider>);
}

function jsonResponse(body: unknown) {
  return {
    ok: true,
    status: 200,
    statusText: "OK",
    json: async () => body,
  } as Response;
}

const graph: AgentGraphResponse = {
  root: "Root",
  nodes: [node("Root", "Root", "composite", null), node("Root.leaf", "Leaf", "leaf", "Root")],
  edges: [],
};

const parameters: AgentParametersResponse = {
  agent_path: "Root.leaf",
  parameters: [
    {
      path: "role",
      type: "TextParameter",
      value: "old role",
      requires_grad: true,
      grad: null,
      constraint: null,
    },
  ],
};

function node(
  path: string,
  class_name: string,
  kind: "leaf" | "composite",
  parent_path: string | null,
) {
  return {
    path,
    class_name,
    kind,
    parent_path,
    input: "Input",
    output: "Output",
    input_label: "Input",
    output_label: "Output",
  };
}

function runSummary(run_id: string, started_at: number): RunSummary {
  return {
    run_id,
    started_at,
    last_event_at: started_at,
    state: "ended",
    has_graph: true,
    is_algorithm: false,
    algorithm_path: null,
    algorithm_kinds: [],
    root_agent_path: "Root",
    script: null,
    event_counts: {},
    event_total: 0,
    duration_ms: 0,
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
}
