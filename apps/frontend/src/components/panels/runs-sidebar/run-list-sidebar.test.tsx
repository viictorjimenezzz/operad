import type { RunSummary } from "@/lib/types";
import { useUIStore } from "@/stores";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { RunListSidebar } from "./run-list-sidebar";

const runsMock: RunSummary[] = [
  {
    run_id: "run-001",
    algorithm_class: "EvoGradient",
    algorithm_path: "EvoGradient",
    state: "running",
    started_at: Math.floor(Date.now() / 1000),
    synthetic: false,
    generations: [],
    iterations: [],
    rounds: [],
    candidates: [],
    batches: [],
  } as unknown as RunSummary,
  {
    run_id: "run-002",
    algorithm_class: "Trainer",
    algorithm_path: "Trainer",
    state: "ended",
    started_at: Math.floor(Date.now() / 1000),
    synthetic: false,
    generations: [],
    iterations: [],
    rounds: [],
    candidates: [],
    batches: [],
  } as unknown as RunSummary,
];

vi.mock("@/hooks/use-runs", () => ({
  useRunsFiltered: () => ({ data: runsMock, isLoading: false }),
}));

function renderSidebar() {
  return render(
    <MemoryRouter initialEntries={["/runs/run-001"]}>
      <Routes>
        <Route path="/runs/:runId" element={<RunListSidebar />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("RunListSidebar", () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    useUIStore.setState({
      currentTab: "overview",
      eventKindFilter: "all",
      eventSearch: "",
      autoFollow: true,
      eventsFollow: true,
      sidebarCollapsed: false,
      drawer: null,
      drawerWidth: 420,
      selectedInvocationId: null,
      selectedInvocationAgentPath: null,
    });
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("toggles collapse via button and cmd+\\ shortcut", () => {
    renderSidebar();

    const collapseButton = screen.getByRole("button", { name: "Collapse runs sidebar" });
    fireEvent.click(collapseButton);

    expect(screen.getByRole("button", { name: "Expand runs sidebar" })).toBeTruthy();

    fireEvent.keyDown(window, { key: "\\", metaKey: true });

    expect(screen.getByRole("button", { name: "Collapse runs sidebar" })).toBeTruthy();
  });

  it("opens rail popover per group when collapsed", () => {
    useUIStore.getState().setSidebarCollapsed(true);
    renderSidebar();

    const groupButton = screen.getByRole("button", { name: "Open EvoGradient runs" });
    fireEvent.click(groupButton);

    expect(screen.getByText("run-001")).toBeTruthy();
  });
});
