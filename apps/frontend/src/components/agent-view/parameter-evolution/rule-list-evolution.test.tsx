import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { RuleListEvolution } from "./rule-list-evolution";
import type { ParameterEvolutionPoint } from "./text-evolution";

afterEach(cleanup);

const points: ParameterEvolutionPoint[] = [
  { runId: "run-0", startedAt: 1, hash: "h0", value: ["Be concise.", "Use English."] },
  { runId: "run-1", startedAt: 2, hash: "h1", value: ["Be concise.", "Avoid emoji."] },
  {
    runId: "run-2",
    startedAt: 3,
    hash: "h2",
    value: ["Be concise.", "Always cite.", "Avoid emoji."],
  },
  {
    runId: "run-3",
    startedAt: 4,
    hash: "h3",
    value: ["Be concise.", "Always cite.", "Avoid emoji."],
  },
  {
    runId: "run-4",
    startedAt: 5,
    hash: "h4",
    value: ["Always cite.", "Avoid emoji."],
  },
];

describe("RuleListEvolution", () => {
  it("renders one row per distinct rule and presence cells", () => {
    render(<RuleListEvolution points={points} selectedStep={2} onSelectStep={() => undefined} />);

    expect(screen.getAllByText("Be concise.").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Always cite.").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Use English.").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Avoid emoji.").length).toBeGreaterThan(0);
    expect(screen.getByLabelText("rule Always cite. absent at step 1")).toBeTruthy();
    expect(screen.getByLabelText("rule Always cite. present at step 3")).toBeTruthy();
  });

  it("selects cells and highlights added or removed rules below the grid", () => {
    const onSelectStep = vi.fn();
    render(<RuleListEvolution points={points} selectedStep={1} onSelectStep={onSelectStep} />);

    fireEvent.click(screen.getByLabelText("rule Always cite. absent at step 2"));
    expect(onSelectStep).toHaveBeenCalledWith(1);
    expect(screen.getByText("step 2 rules")).toBeTruthy();
    const removed = screen
      .getAllByText("Use English.")
      .find((node) => node.className.includes("line-through"));
    expect(removed).toBeTruthy();
  });

  it("handles a single point", () => {
    const firstPoint = points[0];
    if (!firstPoint) throw new Error("missing fixture point");
    render(
      <RuleListEvolution points={[firstPoint]} selectedStep={0} onSelectStep={() => undefined} />,
    );

    expect(screen.getByText("step 1 rules")).toBeTruthy();
    expect(screen.getByLabelText("rule Be concise. present at step 1")).toBeTruthy();
  });

  it("renders an empty state", () => {
    render(<RuleListEvolution points={[]} selectedStep={null} onSelectStep={() => undefined} />);

    expect(screen.getByText("no observed values yet")).toBeTruthy();
  });
});
