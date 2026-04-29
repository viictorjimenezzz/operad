import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { type ParameterEvolutionPoint, TextEvolution } from "./text-evolution";

afterEach(cleanup);

const startedAt = Math.floor(Date.now() / 1000) - 300;

const points: ParameterEvolutionPoint[] = [
  {
    runId: "run-001",
    startedAt,
    value: "Answer briefly.",
    hash: "aaa111",
  },
  {
    runId: "run-002",
    startedAt: startedAt + 60,
    value: "Answer briefly with evidence.",
    hash: "bbb222",
    gradient: { message: "Need support.", severity: "medium", targetPaths: ["task"] },
  },
  {
    runId: "run-003",
    startedAt: startedAt + 120,
    value: "Answer briefly with evidence and citations.",
    hash: "ccc333",
  },
];

describe("TextEvolution", () => {
  it("renders a selected N-step timeline with adjacent diffs", () => {
    const onSelectStep = vi.fn();
    const { container } = render(
      <TextEvolution points={points} selectedStep={1} onSelectStep={onSelectStep} />,
    );

    expect(screen.getByLabelText("select step 1")).toBeTruthy();
    expect(screen.getByLabelText("select step 2")).toBeTruthy();
    expect(screen.getByText("diff vs step 1")).toBeTruthy();
    expect(screen.getByText("severity: medium")).toBeTruthy();
    expect(container.querySelector('[data-selected="true"]')).toBeTruthy();
  });

  it("expands full text and calls selection callback", () => {
    const onSelectStep = vi.fn();
    render(<TextEvolution points={points} selectedStep={null} onSelectStep={onSelectStep} />);

    fireEvent.click(screen.getByLabelText("select step 3"));
    expect(onSelectStep).toHaveBeenCalledWith(2);

    const thirdSummary = screen.getAllByText("View full value")[2];
    if (!thirdSummary) throw new Error("missing third full-text summary");
    fireEvent.click(thirdSummary);
    expect(screen.getAllByText(/citations/).length).toBeGreaterThan(0);
  });

  it("handles a single point without rendering a diff", () => {
    const firstPoint = points[0];
    if (!firstPoint) throw new Error("missing fixture point");
    render(<TextEvolution points={[firstPoint]} selectedStep={0} onSelectStep={() => undefined} />);

    expect(screen.getByText("initial value")).toBeTruthy();
    expect(screen.queryByText(/diff vs step/)).toBeNull();
  });

  it("renders an empty state", () => {
    render(<TextEvolution points={[]} selectedStep={null} onSelectStep={() => undefined} />);

    expect(screen.getByText("no observed values yet")).toBeTruthy();
  });
});
