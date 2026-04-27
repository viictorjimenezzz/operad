import {
  ParameterEvolutionMultiples,
  extractParameterSeries,
} from "@/components/algorithms/trainer/parameter-evolution-multiples";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

afterEach(cleanup);

const checkpoints = [
  {
    epoch: 0,
    train_loss: 0.7,
    val_loss: 0.8,
    score: 0.8,
    lr: 1,
    parameter_snapshot: { task: "'answer briefly'", temperature: "0.2" },
    is_best: false,
  },
  {
    epoch: 1,
    train_loss: 0.5,
    val_loss: 0.6,
    score: 0.6,
    lr: 0.8,
    parameter_snapshot: { task: "'answer with evidence'", temperature: "0.4" },
    is_best: true,
  },
];

describe("ParameterEvolutionMultiples", () => {
  it("extracts numeric and text parameter series from checkpoints", () => {
    const series = extractParameterSeries(checkpoints);
    expect(series.map((item) => item.path)).toEqual(["task", "temperature"]);
    expect(series.find((item) => item.path === "temperature")?.kind).toBe("numeric");
    expect(series.find((item) => item.path === "task")?.points).toHaveLength(2);
  });

  it("renders a card per parameter and opens the diff panel", () => {
    render(<ParameterEvolutionMultiples dataCheckpoints={checkpoints} />);

    expect(screen.getAllByText("task").length).toBeGreaterThan(0);
    expect(screen.getByText("temperature")).toBeTruthy();

    const taskLabel = screen.getAllByText("task")[0];
    if (!taskLabel) throw new Error("missing task label");
    fireEvent.click(taskLabel);
    expect(screen.getByText("parameter diff")).toBeTruthy();
    expect(screen.getAllByText(/answer/).length).toBeGreaterThan(0);
  });
});
