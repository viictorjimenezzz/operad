import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it } from "vitest";
import { SelfRefineIterationsTab, SelfRefineLadderTab } from "./refine-ladder-tab";

afterEach(cleanup);

const data = {
  iterations: [
    {
      iter_index: 0,
      phase: "generator",
      score: 0.4,
      text: "# draft 0\n\nfirst attempt",
      metadata: {},
    },
    {
      iter_index: 0,
      phase: "reflector",
      score: 0.58,
      text: "needs tighter claim",
      metadata: {},
    },
    {
      iter_index: 0,
      phase: "refiner",
      score: 0.71,
      text: "refined answer 0",
      metadata: { stop_reason: "continue", langfuse_url: "https://langfuse.local/trace/0" },
    },
    {
      iter_index: 1,
      phase: "generator",
      score: 0.64,
      text: "# draft 1\n\nsecond attempt",
      metadata: {},
    },
    {
      iter_index: 1,
      phase: "reflector",
      score: 0.77,
      text: "looks good",
      metadata: {},
    },
    {
      iter_index: 1,
      phase: "refiner",
      score: 0.84,
      text: "refined answer 1",
      metadata: { stop_reason: "threshold_met", langfuse_url: "https://langfuse.local/trace/1" },
    },
  ],
  max_iter: 5,
  threshold: 0.8,
  converged: true,
};

function renderWithRouter(node: ReactNode) {
  return render(<MemoryRouter>{node}</MemoryRouter>);
}

describe("SelfRefine ladder tabs", () => {
  it("renders N x 3 cells and opens drawer on click", () => {
    renderWithRouter(<SelfRefineLadderTab dataIterations={data} />);

    const phaseCells = screen.getAllByRole("button", {
      name: /Generator|Reflector|Refiner/,
    });
    expect(phaseCells).toHaveLength(6);

    fireEvent.click(screen.getAllByRole("button", { name: /Refiner/ })[1]!);
    expect(screen.getByText("Iteration 1 · Refiner")).toBeDefined();
    expect(screen.getAllByText("refined answer 1")).toHaveLength(2);
  });

  it("renders iterations tab as RunTable with required columns", () => {
    renderWithRouter(<SelfRefineIterationsTab dataIterations={data} runId="run-1" />);

    expect(screen.getByText("iter")).toBeDefined();
    expect(screen.getByText("refine_score")).toBeDefined();
    expect(screen.getByText("stop_reason")).toBeDefined();
    expect(screen.getByText("langfuse →")).toBeDefined();
    expect(screen.getAllByRole("link", { name: "open" })).toHaveLength(2);
  });
});
