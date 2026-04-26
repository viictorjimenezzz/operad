import type { RunSummary } from "@/lib/types";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ArchivePage } from "./ArchivePage";

const useArchiveRunsMock = vi.fn();

vi.mock("@/hooks/use-runs", () => ({
  useArchiveRuns: (params: unknown) => useArchiveRunsMock(params),
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function makeRun(overrides: Partial<RunSummary> = {}): RunSummary {
  return {
    run_id: "archived-run",
    started_at: 1000,
    last_event_at: 1001,
    state: "ended",
    has_graph: false,
    is_algorithm: true,
    algorithm_path: "pkg.EvoGradient",
    algorithm_kinds: ["algo_start", "algo_end"],
    algorithm_class: "EvoGradient",
    root_agent_path: null,
    script: null,
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
    algorithm_terminal_score: 0.5,
    synthetic: false,
    parent_run_id: null,
    ...overrides,
  };
}

describe("ArchivePage", () => {
  it("renders archived runs list", () => {
    useArchiveRunsMock.mockReturnValue({
      isLoading: false,
      error: null,
      data: [makeRun({ run_id: "arch-1" })],
    });
    render(
      <MemoryRouter>
        <ArchivePage />
      </MemoryRouter>,
    );
    expect(screen.getByText(/archive/i)).toBeTruthy();
    expect(screen.getByRole("link", { name: /arch/i }).getAttribute("href")).toContain(
      "/archive/arch-1",
    );
  });
});
