import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { ConfigurationEvolution } from "./configuration-evolution";
import type { ParameterEvolutionPoint } from "./float-evolution";

afterEach(cleanup);

const configs = [
  {
    sampling: { temperature: 0.2, top_p: 0.8 },
    io: { stream: false },
    model: "openai/gpt-4o",
  },
  {
    sampling: { temperature: 0.4, top_p: 0.8 },
    io: { stream: true },
    model: "openai/gpt-4o-mini",
  },
];

const points: ParameterEvolutionPoint[] = configs.map((value, index) => ({
  runId: `run-${index}`,
  startedAt: index,
  value,
  hash: `config-${index}`,
}));

describe("ConfigurationEvolution", () => {
  it("renders an empty state for no points", () => {
    render(<ConfigurationEvolution path="config" points={[]} />);
    expect(screen.getByText("no configuration history")).toBeTruthy();
  });

  it("recursively renders numeric and categorical leaf views", () => {
    render(<ConfigurationEvolution path="config" points={points} />);

    fireEvent.click(screen.getByText("sampling"));
    fireEvent.click(screen.getByText("temperature"));
    expect(screen.getByLabelText("config.sampling.temperature step plot")).toBeTruthy();

    fireEvent.click(screen.getByText("io"));
    fireEvent.click(screen.getByText("stream"));
    expect(screen.getByLabelText("config.io.stream state diagram")).toBeTruthy();

    fireEvent.click(screen.getByText("model"));
    expect(screen.getByLabelText("config.model state diagram")).toBeTruthy();
  });
});
