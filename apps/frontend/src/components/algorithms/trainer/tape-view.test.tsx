import { TrainerTapeView } from "@/components/algorithms/trainer/tape-view";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, useLocation } from "react-router-dom";

vi.mock("@tanstack/react-virtual", () => ({
  useVirtualizer: ({ count }: { count: number }) => ({
    getTotalSize: () => count * 22,
    getVirtualItems: () =>
      Array.from({ length: Math.min(count, 8) }, (_, index) => ({
        index,
        key: index,
        size: 22,
        start: index * 22,
      })),
  }),
}));

afterEach(cleanup);

describe("TrainerTapeView", () => {
  it("shows the required empty state message when tape capture is missing", () => {
    render(
      <MemoryRouter>
        <TrainerTapeView dataTape={{ entries: [] }} />
      </MemoryRouter>,
    );

    expect(screen.getByText(/tape capture is not enabled for this run/i)).toBeTruthy();
  });

  it("renders a virtualized subset of rows for large tape payloads", () => {
    render(
      <MemoryRouter>
        <TrainerTapeView dataTape={{ entries: makeEntries(50) }} />
      </MemoryRouter>,
    );

    expect(screen.getAllByTestId("tape-row")).toHaveLength(8);
    expect(screen.queryByLabelText("open tape entry Root.leaf.49")).toBeNull();
  });

  it("clicking a row opens parameters tab URL state with param and step", () => {
    render(
      <MemoryRouter initialEntries={["/algorithms/run-1?tab=tape"]}>
        <TrainerTapeView dataTape={{ entries: makeEntries(5) }} />
        <LocationProbe />
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByLabelText("open tape entry Root.leaf.0"));
    const search = screen.getByTestId("search").textContent ?? "";
    expect(search).toContain("tab=parameters");
    expect(search).toContain("param=Planner.role");
    expect(search).toContain("step=3");
  });
});

function LocationProbe() {
  const location = useLocation();
  return <div data-testid="search">{location.search}</div>;
}

function makeEntries(count: number) {
  return Array.from({ length: count }, (_, index) => ({
    id: `entry-${index}`,
    agent_path: `Root.leaf.${index}`,
    input_hash: `in-${index}`,
    output_hash: `out-${index}`,
    latency_ms: 12 + index,
    in_tape_for_step: { epoch: 1, batch: 2, iter: 3, optimizer_step: index + 3 },
    gradient_severity: index % 3 === 0 ? "high" : index % 3 === 1 ? "medium" : "low",
    param_path: index === 0 ? "Planner.role" : `Planner.rules.${index}`,
    step_index: index === 0 ? 3 : index + 3,
    langfuse_url: `https://langfuse.example/trace/${index}`,
  }));
}
