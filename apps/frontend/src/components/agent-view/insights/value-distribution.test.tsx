import { ValueDistribution } from "@/components/agent-view/insights/value-distribution";
import { useUIStore } from "@/stores/ui";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

describe("ValueDistribution", () => {
  beforeEach(() => useUIStore.setState({ drawer: null }));

  it("renders numeric summary", () => {
    render(<ValueDistribution label="score" values={[1, 2, 3, 4]} />);
    expect(screen.getByText(/min/i)).toBeTruthy();
    expect(screen.getByText(/avg/i)).toBeTruthy();
    expect(screen.getByText(/max/i)).toBeTruthy();
  });

  it("renders categorical bars", () => {
    render(<ValueDistribution label="topic" values={["a", "a", "b", "c"]} />);
    expect(screen.getByText("a")).toBeTruthy();
    expect(screen.getByText("b")).toBeTruthy();
  });

  it("opens values drawer for high-cardinality strings", () => {
    render(
      <ValueDistribution
        label="question"
        values={Array.from({ length: 20 }).map((_, index) => `q-${index}`)}
        agentPath="Root"
        side="in"
      />,
    );
    fireEvent.click(screen.getByText(/see all values/i));
    expect(useUIStore.getState().drawer).toEqual({
      kind: "values",
      payload: { agentPath: "Root", attr: "question", side: "in" },
    });
  });

  it("renders empty state when no values", () => {
    render(<ValueDistribution label="question" values={[]} />);
    expect(screen.getByText(/no values yet/i)).toBeTruthy();
  });
});
