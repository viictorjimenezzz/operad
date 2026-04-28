import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { FloatEvolution, type ParameterEvolutionPoint } from "./float-evolution";

afterEach(cleanup);

const points: ParameterEvolutionPoint[] = [0.2, 0.25, 0.5, 0.4, 0.6].map((value, index) => ({
  runId: `run-${index}`,
  startedAt: index,
  value,
  hash: `h-${value}`,
}));

describe("FloatEvolution", () => {
  it("renders an empty state for no points", () => {
    render(<FloatEvolution path="sampling.temperature" points={[]} />);
    expect(screen.getByText("no numeric parameter history")).toBeTruthy();
  });

  it("renders a step plot with summary stats and selected step", () => {
    render(
      <FloatEvolution
        path="sampling.temperature"
        points={points}
        constraint={{ min: 0, max: 1, default: 0.2 }}
        selectedStep={2}
      />,
    );

    expect(screen.getByLabelText("sampling.temperature step plot")).toBeTruthy();
    expect(screen.getByText("mean")).toBeTruthy();
    expect(screen.getByText("step 2")).toBeTruthy();
  });

  it("fires onSelectStep from the plot step target", () => {
    const onSelectStep = vi.fn();
    render(
      <FloatEvolution path="sampling.temperature" points={points} onSelectStep={onSelectStep} />,
    );

    fireEvent.click(screen.getByLabelText("select step 3"));
    expect(onSelectStep).toHaveBeenCalledWith(3);
  });
});
