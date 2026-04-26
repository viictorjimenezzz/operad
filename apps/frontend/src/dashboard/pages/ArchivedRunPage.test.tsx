import type { RunSummary } from "@/lib/types";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { ArchivedRunPage } from "./ArchivedRunPage";

const useArchivedRunMock = vi.fn();
const useRestoreArchivedRunMock = vi.fn();
const mutateAsyncMock = vi.fn();

vi.mock("@/hooks/use-runs", () => ({
  useArchivedRun: (runId: string | undefined) => useArchivedRunMock(runId),
  useRestoreArchivedRun: () => useRestoreArchivedRunMock(),
}));

vi.mock("@/components/DashboardRenderer", () => ({
  DashboardRenderer: () => <div>renderer</div>,
}));

vi.mock("@/layouts", () => ({
  pickLayout: () => ({ algorithm: "test", widgets: [] }),
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function makeSummary(overrides: Partial<RunSummary> = {}): RunSummary {
  return {
    run_id: "arch-1",
    started_at: 1000,
    last_event_at: 1001,
    state: "ended",
    has_graph: false,
    is_algorithm: true,
    algorithm_path: "pkg.EvoGradient",
    algorithm_kinds: ["algo_start", "algo_end"],
    algorithm_class: "EvoGradient",
    root_agent_path: null,
    event_counts: { algo_start: 1, algo_end: 1 },
    event_total: 2,
    duration_ms: 1000,
    generations: [],
    iterations: [],
    rounds: [],
    candidates: [],
    batches: [],
    prompt_tokens: 0,
    completion_tokens: 0,
    error: null,
    algorithm_terminal_score: 1.0,
    synthetic: false,
    parent_run_id: null,
    ...overrides,
  };
}

describe("ArchivedRunPage", () => {
  it("restores archived run on button click", async () => {
    mutateAsyncMock.mockResolvedValue({ ok: true, run: makeSummary() });
    useRestoreArchivedRunMock.mockReturnValue({ isPending: false, mutateAsync: mutateAsyncMock });
    useArchivedRunMock.mockReturnValue({
      isLoading: false,
      error: null,
      data: { summary: makeSummary(), events: [] },
    });

    render(
      <MemoryRouter initialEntries={["/archive/arch-1"]}>
        <Routes>
          <Route path="/archive/:runId" element={<ArchivedRunPage />} />
          <Route path="/runs/:runId" element={<div>live run page</div>} />
        </Routes>
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole("button", { name: /restore to live/i }));

    await waitFor(() => {
      expect(mutateAsyncMock).toHaveBeenCalledWith("arch-1");
    });
  });
});
