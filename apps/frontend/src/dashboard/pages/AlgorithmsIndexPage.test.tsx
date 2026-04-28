import { AlgorithmsIndexPage } from "@/dashboard/pages/AlgorithmsIndexPage";
import type { AlgorithmGroup, RunSummary } from "@/lib/types";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const useAlgorithmGroupsMock = vi.fn();

vi.mock("@/hooks/use-runs", () => ({
  useAlgorithmGroups: () => useAlgorithmGroupsMock(),
}));

function LocationProbe() {
  const location = useLocation();
  return <div data-testid="location">{location.pathname}</div>;
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/algorithms"]}>
      <Routes>
        <Route
          path="/algorithms"
          element={
            <>
              <AlgorithmsIndexPage />
              <LocationProbe />
            </>
          }
        />
        <Route path="/algorithms/:runId" element={<LocationProbe />} />
      </Routes>
    </MemoryRouter>,
  );
}

function run(overrides: Partial<RunSummary> = {}): RunSummary {
  return {
    run_id: "run-sweep-1",
    started_at: 1_700_000_000,
    last_event_at: 1_700_000_002,
    state: "ended",
    has_graph: false,
    is_algorithm: true,
    algorithm_path: "Sweep",
    algorithm_kinds: [],
    root_agent_path: null,
    script: "examples/05_algorithm_gallery.py",
    event_counts: {},
    event_total: 4,
    duration_ms: 2_000,
    generations: [],
    iterations: [],
    rounds: [],
    candidates: [],
    batches: [],
    prompt_tokens: 10,
    completion_tokens: 5,
    error: null,
    algorithm_terminal_score: 0.9,
    synthetic: false,
    parent_run_id: null,
    algorithm_class: "Sweep",
    cost: { prompt_tokens: 10, completion_tokens: 5, cost_usd: 0.01 },
    ...overrides,
  };
}

function group(overrides: Partial<AlgorithmGroup> = {}): AlgorithmGroup {
  const runs = overrides.runs ?? [run()];
  return {
    algorithm_path: "Sweep",
    class_name: "Sweep",
    count: runs.length,
    running: 0,
    errors: 0,
    last_seen: 1_700_000_002,
    first_seen: 1_700_000_000,
    runs,
    ...overrides,
  };
}

beforeEach(() => {
  window.localStorage.clear();
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("<AlgorithmsIndexPage />", () => {
  it("renders algorithm invocations as table rows without the old grouped cards", async () => {
    useAlgorithmGroupsMock.mockReturnValue({
      data: [
        group(),
        group({
          algorithm_path: "Debate",
          class_name: "Debate",
          runs: [
            run({
              run_id: "run-debate-1",
              algorithm_path: "Debate",
              algorithm_class: "Debate",
              script: null,
              event_total: 8,
              rounds: [{ round_index: 0, scores: [0.5], timestamp: 1_700_000_001 }],
              algorithm_terminal_score: null,
            }),
          ],
        }),
      ],
      isLoading: false,
    });

    renderPage();

    expect(await screen.findByRole("button", { name: /Run ID/ })).toBeTruthy();
    expect(screen.getByText("Sweep")).toBeTruthy();
    expect(screen.getByText("run-sweep-1")).toBeTruthy();
    expect(screen.getByText("examples/05_algorithm_gallery.py")).toBeTruthy();
    expect(screen.getByText("score=0.900")).toBeTruthy();
    expect(screen.getByText("run-debate-1")).toBeTruthy();
    expect(screen.getByText("rounds=1")).toBeTruthy();
    expect(screen.queryByText("Algorithm")).toBeNull();
    expect(screen.queryByText("Algorithms")).toBeNull();
  });

  it("navigates rows to the algorithm detail route", async () => {
    useAlgorithmGroupsMock.mockReturnValue({
      data: [group()],
      isLoading: false,
    });

    renderPage();

    fireEvent.click(await screen.findByText("run-sweep-1"));

    await waitFor(() => {
      expect(screen.getByTestId("location").textContent).toBe("/algorithms/run-sweep-1");
    });
  });
});
