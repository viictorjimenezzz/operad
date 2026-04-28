import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { type ParameterEvolutionPoint, WhyPane } from "./why-pane";

afterEach(cleanup);

const fullPoint: ParameterEvolutionPoint = {
  runId: "run-gradient-1234567890",
  startedAt: 1_700_000_000,
  value: "answer with citations",
  hash: "hash-current-abcdef",
  gradient: {
    message: "**Raise evidence weight**\n\n- cite the source before final answer",
    severity: "high",
    targetPaths: ["research_analyst.task", "research_analyst.rules.0"],
    critic: {
      agentPath: "research_analyst.critic",
      runId: "critic-run-1",
      langfuseUrl: "https://langfuse.example/trace/critic-run-1",
    },
  },
  sourceTapeStep: {
    epoch: 2,
    batch: 5,
    iter: 8,
    optimizerStep: 13,
  },
  metricSnapshot: {
    train_loss: 0.71,
    val_loss: 0.84,
    lr: 0.001,
  },
  langfuseUrl: "https://langfuse.example/trace/run-gradient-1234567890",
};

const previousPoint: ParameterEvolutionPoint = {
  runId: "run-before",
  startedAt: 1_699_999_900,
  value: "answer briefly",
  hash: "hash-before-abcdef",
};

describe("WhyPane", () => {
  it("renders gradient markdown, tape context, metrics, and critic deep-link", () => {
    render(<WhyPane point={fullPoint} previous={previousPoint} />);

    expect(screen.getByText("Raise evidence weight")).toBeTruthy();
    expect(screen.getByText("high")).toBeTruthy();
    expect(screen.getByText("research_analyst.task")).toBeTruthy();
    expect(screen.getByText("research_analyst.rules.0")).toBeTruthy();
    expect(screen.getByText("Open critic invocation in Langfuse ->")).toBeTruthy();
    expect(screen.getByText("epoch")).toBeTruthy();
    expect(screen.getByText("2")).toBeTruthy();
    expect(screen.getByText("batch")).toBeTruthy();
    expect(screen.getByText("5")).toBeTruthy();
    expect(screen.getByText("iter")).toBeTruthy();
    expect(screen.getByText("8")).toBeTruthy();
    expect(screen.getByText("optimizer_step")).toBeTruthy();
    expect(screen.getByText("13")).toBeTruthy();
    expect(screen.getByText("train_loss")).toBeTruthy();
    expect(screen.getByText("0.71")).toBeTruthy();
    expect(screen.getByText("val_loss")).toBeTruthy();
    expect(screen.getByText("0.84")).toBeTruthy();
    expect(screen.getByText("lr")).toBeTruthy();
  });

  it("renders a selected-step empty state", () => {
    render(<WhyPane point={null} />);

    expect(screen.getByText("select a step")).toBeTruthy();
    expect(
      screen.getByText("Select a step in the timeline above to see how it changed."),
    ).toBeTruthy();
  });

  it("renders a no-gradient hint without crashing", () => {
    render(
      <WhyPane
        point={{
          runId: "run-initial",
          startedAt: 1_700_000_010,
          value: "initial value",
          hash: "hash-initial",
        }}
      />,
    );

    expect(screen.getByText("no textual-gradient critic")).toBeTruthy();
    expect(screen.getByText(/without a textual-gradient critic/)).toBeTruthy();
    expect(screen.getByText("baseline")).toBeTruthy();
  });
});
