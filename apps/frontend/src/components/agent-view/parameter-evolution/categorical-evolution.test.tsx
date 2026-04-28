import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CategoricalEvolution } from "./categorical-evolution";
import type { ParameterEvolutionPoint } from "./float-evolution";

afterEach(cleanup);

const values = [
  "openai/gpt-4o",
  "openai/gpt-4o",
  "openai/gpt-4o-mini",
  "openai/gpt-4o-mini",
  "anthropic/claude-3-5-sonnet",
  "anthropic/claude-3-5-sonnet",
  "local/qwen2.5",
  "local/qwen2.5",
];

const points: ParameterEvolutionPoint[] = values.map((value, index) => ({
  runId: `run-${index}`,
  startedAt: index,
  value,
  hash: `h-${index}`,
}));

describe("CategoricalEvolution", () => {
  it("renders an empty state for no points", () => {
    render(<CategoricalEvolution path="model" points={[]} />);
    expect(screen.getByText("no categorical parameter history")).toBeTruthy();
  });

  it("renders nodes and directed transition edges", () => {
    render(<CategoricalEvolution path="model" points={points} />);

    expect(screen.getByLabelText("model state diagram")).toBeTruthy();
    expect(screen.getAllByTestId("category-node")).toHaveLength(4);
    expect(screen.getAllByTestId("category-edge")).toHaveLength(3);
  });

  it("fires onSelectStep from the step list", () => {
    const onSelectStep = vi.fn();
    render(<CategoricalEvolution path="model" points={points} onSelectStep={onSelectStep} />);

    fireEvent.click(screen.getByText("step 3"));
    expect(onSelectStep).toHaveBeenCalledWith(3);
  });
});
