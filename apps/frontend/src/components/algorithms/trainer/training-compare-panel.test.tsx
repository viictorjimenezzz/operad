import { TrainingComparePanel } from "@/components/algorithms/trainer/training-compare-panel";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

function wrapper(children: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={client}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}

describe("TrainingComparePanel", () => {
  it("loads selected runs and renders overlays plus final diff", async () => {
    const fetchMock = vi.fn(async (url: string) => {
      const runId = url.includes("run-b") ? "run-b" : "run-a";
      if (url.endsWith("/summary")) {
        return json({
          run_id: runId,
          started_at: 1,
          last_event_at: 2,
          state: "ended",
          has_graph: false,
          is_algorithm: true,
          algorithm_path: "Trainer",
          algorithm_kinds: [],
          root_agent_path: "Agent",
          event_counts: {},
          event_total: 4,
          duration_ms: 1000,
          generations: [],
          iterations: [],
          rounds: [],
          candidates: [],
          batches: [],
          prompt_tokens: 0,
          completion_tokens: 0,
          error: null,
          algorithm_terminal_score: runId === "run-b" ? 0.9 : 0.7,
          synthetic: false,
          parent_run_id: null,
          algorithm_class: "Trainer",
          hash_content: "abc123",
        });
      }
      if (url.endsWith("/fitness.json")) {
        return json([
          {
            gen_index: 0,
            best: runId === "run-b" ? 0.7 : 0.8,
            mean: 0.8,
            worst: 0.8,
            train_loss: runId === "run-b" ? 0.7 : 0.8,
            val_loss: null,
            lr: 1,
            population_scores: [0.8],
            timestamp: 1,
          },
          {
            gen_index: 1,
            best: runId === "run-b" ? 0.4 : 0.5,
            mean: 0.5,
            worst: 0.5,
            train_loss: runId === "run-b" ? 0.4 : 0.5,
            val_loss: null,
            lr: 0.5,
            population_scores: [0.5],
            timestamp: 2,
          },
        ]);
      }
      return json([
        {
          epoch: 1,
          train_loss: runId === "run-b" ? 0.4 : 0.5,
          val_loss: null,
          score: runId === "run-b" ? 0.4 : 0.5,
          lr: 0.5,
          parameter_snapshot: { task: runId === "run-b" ? "'new'" : "'old'" },
          is_best: true,
        },
      ]);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(wrapper(<TrainingComparePanel runIds={["run-a", "run-b"]} />));

    expect(await screen.findByText("Overlaid loss curves")).toBeTruthy();
    expect(screen.getByText("Overlaid LR schedules")).toBeTruthy();
    expect(screen.getByText("Final-state diff")).toBeTruthy();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(6));
  });
});

function json(body: unknown) {
  return {
    ok: true,
    json: async () => body,
  } as Response;
}
