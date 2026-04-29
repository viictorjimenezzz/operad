import { TrainingDetailLayout } from "@/dashboard/pages/run-detail/TrainingDetailLayout";
import type { RunSummary } from "@/lib/types";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const hookMocks = vi.hoisted(() => ({
  useRunSummary: vi.fn(),
  useRunEvents: vi.fn(),
}));

const storeMocks = vi.hoisted(() => ({
  ingest: vi.fn(),
  setCurrentRun: vi.fn(),
}));

const rendererCalls = vi.hoisted(
  () => [] as Array<{ layoutAlgorithm: string; context: Record<string, string | undefined> }>,
);

vi.mock("@/hooks/use-runs", () => ({
  useRunSummary: hookMocks.useRunSummary,
  useRunEvents: hookMocks.useRunEvents,
}));

vi.mock("@/stores", () => ({
  useEventBufferStore: (selector: (state: { ingest: typeof storeMocks.ingest }) => unknown) =>
    selector({ ingest: storeMocks.ingest }),
}));

vi.mock("@/stores/run", () => ({
  useRunStore: (selector: (state: { setCurrentRun: typeof storeMocks.setCurrentRun }) => unknown) =>
    selector({ setCurrentRun: storeMocks.setCurrentRun }),
}));

vi.mock("@/components/runtime/dashboard-renderer", () => ({
  DashboardRenderer: ({
    layout,
    context,
  }: {
    layout: { algorithm: string };
    context: Record<string, string | undefined>;
  }) => {
    rendererCalls.push({ layoutAlgorithm: layout.algorithm, context });
    return <div data-testid="dashboard-layout">{layout.algorithm}</div>;
  },
}));

const baseSummary: RunSummary = {
  run_id: "run-1",
  started_at: 1,
  last_event_at: 2,
  state: "ended",
  has_graph: true,
  is_algorithm: true,
  algorithm_path: "Trainer",
  algorithm_kinds: [],
  root_agent_path: "Reasoner",
  script: null,
  event_counts: {},
  event_total: 2,
  duration_ms: 1420,
  generations: [],
  iterations: [],
  rounds: [],
  candidates: [],
  batches: [],
  prompt_tokens: 312,
  completion_tokens: 198,
  error: null,
  algorithm_terminal_score: null,
  cost: { prompt_tokens: 312, completion_tokens: 198, cost_usd: 0.0042 },
  synthetic: false,
  parent_run_id: null,
  algorithm_class: "Trainer",
  metrics: {},
  notes_markdown: "",
};

describe("TrainingDetailLayout", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    hookMocks.useRunSummary.mockReset();
    hookMocks.useRunEvents.mockReset();
    storeMocks.ingest.mockReset();
    storeMocks.setCurrentRun.mockReset();
    rendererCalls.length = 0;
    hookMocks.useRunEvents.mockReturnValue({ data: { events: [] } });
  });

  it("uses the EvoGradient layout for optimizer runs on the Training rail", () => {
    renderTrainingDetail({
      ...baseSummary,
      run_id: "evo-run",
      algorithm_path: "EvoGradient",
      algorithm_class: "EvoGradient",
    });

    expect(screen.getByTestId("dashboard-layout").textContent).toBe("EvoGradient");
    expect(rendererCalls.at(-1)).toEqual({
      layoutAlgorithm: "EvoGradient",
      context: { runId: "evo-run" },
    });
  });

  it("keeps the Trainer layout for Trainer runs", () => {
    renderTrainingDetail({
      ...baseSummary,
      run_id: "trainer-run",
      algorithm_path: "Trainer",
      algorithm_class: "Trainer",
    });

    expect(screen.getByTestId("dashboard-layout").textContent).toBe("Trainer");
    expect(rendererCalls.at(-1)).toEqual({
      layoutAlgorithm: "Trainer",
      context: { runId: "trainer-run" },
    });
  });

  it("still resolves optimizer layout when the URL has a stale Trainer tab", () => {
    renderTrainingDetail(
      {
        ...baseSummary,
        run_id: "evo-run",
        algorithm_path: "EvoGradient",
        algorithm_class: "EvoGradient",
      },
      "/training/evo-run?tab=schedule",
    );

    expect(screen.getByTestId("dashboard-layout").textContent).toBe("EvoGradient");
  });
});

function renderTrainingDetail(summary: RunSummary, entry = `/training/${summary.run_id}`) {
  hookMocks.useRunSummary.mockReturnValue({
    isLoading: false,
    error: null,
    data: summary,
  });

  return render(
    <MemoryRouter initialEntries={[entry]}>
      <Routes>
        <Route path="/training/:runId" element={<TrainingDetailLayout />} />
      </Routes>
    </MemoryRouter>,
  );
}
