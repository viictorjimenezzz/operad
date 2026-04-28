import { AlgorithmsTree } from "@/components/panels/section-sidebar/algorithms-tree";
import type { AlgorithmGroup, RunSummary } from "@/lib/types";
import { render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

const useAlgorithmGroupsMock = vi.fn();
const sectionSpy = vi.fn();

vi.mock("@/hooks/use-runs", () => ({
  useAlgorithmGroups: () => useAlgorithmGroupsMock(),
}));

vi.mock("@/components/ui", async () => {
  const actual = await vi.importActual<typeof import("@/components/ui")>("@/components/ui");
  return {
    ...actual,
    GroupTreeSection: (props: {
      label: ReactNode;
      count?: number;
      rows: Array<{ id: string; label: ReactNode; meta?: ReactNode }>;
      onSelect: (row: { id: string }) => void;
    }) => {
      sectionSpy(props);
      return (
        <div>
          <div>{props.label}</div>
          <div>{props.count}</div>
          {props.rows.map((row) => (
            <button type="button" key={row.id} onClick={() => props.onSelect(row)}>
              <span>{row.label}</span>
              <span>{row.meta}</span>
            </button>
          ))}
        </div>
      );
    },
    Pager: () => null,
  };
});

function LocationProbe() {
  const location = useLocation();
  return <div data-testid="location">{location.pathname}</div>;
}

function renderTree(initialPath = "/algorithms") {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route
          path="/algorithms"
          element={
            <>
              <AlgorithmsTree search="" />
              <LocationProbe />
            </>
          }
        />
        <Route
          path="/algorithms/:runId"
          element={
            <>
              <AlgorithmsTree search="" />
              <LocationProbe />
            </>
          }
        />
      </Routes>
    </MemoryRouter>,
  );
}

function run(runId: string, algorithmClass: string): RunSummary {
  return {
    run_id: runId,
    started_at: 1_700_000_000,
    last_event_at: 1_700_000_100,
    state: "ended",
    has_graph: true,
    is_algorithm: true,
    algorithm_path: `algorithms.${algorithmClass}`,
    algorithm_kinds: [],
    root_agent_path: null,
    script: null,
    event_counts: {},
    event_total: 5,
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
  };
}

function group(className: string, runs: RunSummary[]): AlgorithmGroup {
  return {
    algorithm_path: `algorithms.${className}`,
    class_name: className,
    count: runs.length,
    running: 0,
    errors: 0,
    last_seen: 1_700_000_100,
    first_seen: 1_700_000_000,
    runs,
  };
}

afterEach(() => {
  vi.clearAllMocks();
});

describe("<AlgorithmsTree />", () => {
  it("uses algorithm class as row label and class identity color grouping", async () => {
    useAlgorithmGroupsMock.mockReturnValue({
      data: [
        group("Sweep", [run("run-sweep-1", "Sweep"), run("run-sweep-2", "Sweep")]),
        group("Beam", [run("run-beam-1", "Beam")]),
      ],
      isLoading: false,
    });

    renderTree();

    expect(await screen.findByText("Algorithms")).toBeTruthy();
    expect(screen.getAllByText("Sweep").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("Beam")).toBeTruthy();

    const latest = sectionSpy.mock.calls.at(-1)?.[0];
    expect(latest).toBeDefined();
    const rows = latest.rows as Array<{ id: string; colorIdentity?: string }>;
    const sweep1 = rows.find((row) => row.id === "run-sweep-1");
    const sweep2 = rows.find((row) => row.id === "run-sweep-2");
    const beam1 = rows.find((row) => row.id === "run-beam-1");

    expect(sweep1?.colorIdentity).toBe("Sweep");
    expect(sweep2?.colorIdentity).toBe("Sweep");
    expect(beam1?.colorIdentity).toBe("Beam");

    latest.onSelect({ id: "run-beam-1" });
    await waitFor(() => {
      expect(screen.getByTestId("location").textContent).toBe("/algorithms/run-beam-1");
    });
  });
});
