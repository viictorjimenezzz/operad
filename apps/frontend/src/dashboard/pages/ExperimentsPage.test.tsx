import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  ExperimentsPage,
  parseRunsParam,
  resolveComparisonRunIds,
  updateRunsSearch,
} from "./ExperimentsPage";

function renderPage(entry: string) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 0, gcTime: 0 } },
  });

  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[entry]}>{children}</MemoryRouter>
    </QueryClientProvider>
  );

  return render(
    <Routes>
      <Route path="/experiments" element={<ExperimentsPage />} />
    </Routes>,
    { wrapper },
  );
}

function summary(runId: string, hashPrompt: string) {
  return {
    run_id: runId,
    started_at: 1,
    last_event_at: 2,
    state: "ended",
    has_graph: true,
    is_algorithm: false,
    algorithm_path: null,
    algorithm_kinds: [],
    root_agent_path: "root.leaf",
    script: null,
    event_counts: {},
    event_total: 4,
    duration_ms: 1100,
    generations: [],
    iterations: [],
    rounds: [],
    candidates: [],
    batches: [],
    prompt_tokens: 12,
    completion_tokens: 9,
    error: null,
    algorithm_terminal_score: 0.7,
    synthetic: false,
    parent_run_id: null,
    algorithm_class: null,
    hash_content: `${runId}-content-hash`,
    hash_model: `${runId}-model-hash`,
    hash_prompt: hashPrompt,
    hash_input: `${runId}-input-hash`,
    hash_output_schema: `${runId}-output-hash`,
    hash_graph: `${runId}-graph-hash`,
    hash_config: `${runId}-config-hash`,
    cost: { prompt_tokens: 12, completion_tokens: 9, cost_usd: 0.02 },
    metrics: { best_score: 0.7 },
  };
}

beforeEach(() => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    const runMatch = url.match(/\/runs\/([^/]+)\/(summary|invocations|events\?limit=500|agent_graph)/);
    if (runMatch) {
      const runId = runMatch[1] ?? "run-a";
      const endpoint = runMatch[2];
      if (endpoint === "summary") {
        const hashPrompt = runId === "run-b" ? "run-b-prompt-changed-hash" : `${runId}-prompt-hash`;
        return json(summary(runId, hashPrompt));
      }
      if (endpoint === "invocations") {
        return json({
          agent_path: "root.leaf",
          invocations: [
            {
              id: `${runId}-inv-1`,
              started_at: 1,
              finished_at: 2,
              latency_ms: 123,
              prompt_tokens: 12,
              completion_tokens: 9,
              hash_model: null,
              hash_prompt: null,
              hash_graph: null,
              hash_input: null,
              hash_output_schema: null,
              hash_config: null,
              hash_content: `${runId}-content-hash`,
              status: "ok",
              error: null,
              langfuse_url: `https://langfuse.example/${runId}`,
              script: null,
              backend: null,
              model: null,
              renderer: null,
              input: { question: `input-${runId}` },
              output: { answer: `output-${runId}` },
            },
          ],
        });
      }
      if (endpoint === "events?limit=500") {
        const ops =
          runId === "run-b"
            ? [{ type: "AppendRule", path: "reasoner", rule: "Be concise." }]
            : [];
        return json({
          run_id: runId,
          events: [
            {
              type: "algo_event",
              run_id: runId,
              algorithm_path: "operad.algorithms.Sweep",
              kind: "gradient_applied",
              payload: { ops },
              started_at: 1,
              finished_at: 2,
              metadata: {},
            },
          ],
        });
      }
      if (endpoint === "agent_graph") {
        return json({
          root: "root.leaf",
          nodes: [
            {
              path: "root.leaf",
              class_name: "Reasoner",
              kind: "leaf",
              parent_path: null,
              input: "",
              output: "",
              input_label: "",
              output_label: "",
            },
          ],
          edges: [],
        });
      }
    }

    const parameterMatch = url.match(/\/runs\/([^/]+)\/agent\/([^/]+)\/parameters/);
    if (parameterMatch) {
      const runId = parameterMatch[1] ?? "run-a";
      return json({
        agent_path: decodeURIComponent(parameterMatch[2] ?? "root.leaf"),
        parameters: [
          {
            path: "role",
            type: "text",
            value: `role-${runId}`,
            requires_grad: true,
            grad: null,
            constraint: null,
          },
        ],
      });
    }

    return new Response("not found", { status: 404 });
  });
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("Experiments helpers", () => {
  it("parseRunsParam dedupes, preserves order, and skips empties", () => {
    expect(parseRunsParam("run-a,,run-b,run-a, run-c ")).toEqual(["run-a", "run-b", "run-c"]);
  });

  it("resolveComparisonRunIds parses URL parameter", () => {
    expect(resolveComparisonRunIds("url-a,url-b")).toEqual(["url-a", "url-b"]);
    expect(resolveComparisonRunIds(null)).toEqual([]);
  });

  it("updateRunsSearch sets and clears runs param", () => {
    const current = new URLSearchParams("foo=1");
    const withRuns = updateRunsSearch(current, ["a", "b", "a"]);
    expect(withRuns.get("runs")).toBe("a,b");
    expect(withRuns.get("foo")).toBe("1");

    const cleared = updateRunsSearch(withRuns, []);
    expect(cleared.get("runs")).toBeNull();
    expect(cleared.get("foo")).toBe("1");
  });
});

describe("ExperimentsPage", () => {
  it("renders compare sections, highlights hash diffs, and shows op log entries", async () => {
    const { container } = renderPage("/experiments?runs=run-a,run-b");

    expect(await screen.findByText("Identity Strip")).toBeTruthy();
    expect(screen.getByText("Hash Diff Matrix")).toBeTruthy();
    expect(screen.getByText("Parameter Diff")).toBeTruthy();
    expect(screen.getByText("Op Log")).toBeTruthy();
    expect(screen.getByText("Outcomes")).toBeTruthy();
    expect(screen.getByText("Langfuse Links")).toBeTruthy();

    expect(container.querySelector('[data-hash-diff="changed"]')).toBeTruthy();
    expect(screen.getByText(/AppendRule/)).toBeTruthy();
    expect(screen.getByText(/Be concise\./)).toBeTruthy();
  });

  it("renders four columns when four run ids are provided", async () => {
    renderPage("/experiments?runs=run-a,run-b,run-c,run-d");

    await screen.findByText("Identity Strip");
    const section = document.querySelector('[data-compare-section="Identity Strip"]');
    expect(section).toBeTruthy();
    expect(section?.querySelectorAll("[data-compare-run]").length).toBe(4);
  });
});

function json(value: unknown): Response {
  return new Response(JSON.stringify(value), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}
