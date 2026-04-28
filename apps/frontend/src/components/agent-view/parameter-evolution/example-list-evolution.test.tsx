import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ExampleListEvolution } from "./example-list-evolution";
import type { ParameterEvolutionPoint } from "./text-evolution";

afterEach(cleanup);

const exampleA = { input: { question: "Q1" }, output: { answer: "A1" } };
const exampleB = { input: { question: "Q2" }, output: { answer: "A2" } };
const exampleC = { input: { question: "Q3" }, output: { answer: "A3" } };

const points: ParameterEvolutionPoint[] = [
  { runId: "run-0", startedAt: 1, hash: "h0", value: [exampleA] },
  { runId: "run-1", startedAt: 2, hash: "h1", value: [exampleA, exampleB] },
  { runId: "run-2", startedAt: 3, hash: "h2", value: [exampleB, exampleC] },
];

describe("ExampleListEvolution", () => {
  it("renders the lifeline grid", () => {
    render(
      <ExampleListEvolution points={points} selectedStep={0} onSelectStep={() => undefined} />,
    );

    expect(screen.getByText(/Q1/)).toBeTruthy();
    expect(screen.getByText(/Q2/)).toBeTruthy();
    expect(screen.getByText(/Q3/)).toBeTruthy();
    expect(screen.getAllByLabelText(/example .*present at step 1/).length).toBeGreaterThan(0);
    expect(screen.getAllByLabelText(/example .*absent at step 1/).length).toBeGreaterThan(0);
  });

  it("clicking a present cell expands input and output inline", () => {
    const onSelectStep = vi.fn();
    render(
      <ExampleListEvolution points={points} selectedStep={null} onSelectStep={onSelectStep} />,
    );

    fireEvent.click(screen.getByLabelText(/example .*Q2.*present at step 2/));
    expect(onSelectStep).toHaveBeenCalledWith(1);
    expect(screen.getByText("step 2 example")).toBeTruthy();
    expect(screen.getByText("input")).toBeTruthy();
    expect(screen.getByText("output")).toBeTruthy();
    expect(screen.getByText('"Q2"')).toBeTruthy();
    expect(screen.getByText('"A2"')).toBeTruthy();
  });

  it("handles a single point", () => {
    const firstPoint = points[0];
    if (!firstPoint) throw new Error("missing fixture point");
    render(
      <ExampleListEvolution
        points={[firstPoint]}
        selectedStep={0}
        onSelectStep={() => undefined}
      />,
    );

    expect(screen.getByText(/Q1/)).toBeTruthy();
    expect(screen.getByLabelText(/example .*present at step 1/)).toBeTruthy();
  });

  it("renders an empty state", () => {
    render(<ExampleListEvolution points={[]} selectedStep={null} onSelectStep={() => undefined} />);

    expect(screen.getByText("no observed values yet")).toBeTruthy();
  });
});
