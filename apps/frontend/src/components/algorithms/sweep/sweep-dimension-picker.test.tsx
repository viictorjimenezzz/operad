import {
  type SweepAggregation,
  SweepDimensionPicker,
} from "@/components/algorithms/sweep/sweep-dimension-picker";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(cleanup);

const axes = [
  { name: "temperature", values: [0.2, 0.4] },
  { name: "top_p", values: [0.8, 0.9] },
  { name: "model", values: ["mini", "large"] },
];

describe("SweepDimensionPicker", () => {
  it("hides itself for one- and two-axis sweeps", () => {
    const { container } = render(
      <SweepDimensionPicker
        axes={axes.slice(0, 2)}
        selected={["temperature", "top_p"]}
        onChange={vi.fn()}
        aggregations={{}}
        onAggregationsChange={vi.fn()}
      />,
    );

    expect(container.textContent).toBe("");
  });

  it("renders axis selectors and aggregation controls for 3d sweeps", () => {
    function Harness() {
      const [selected, setSelected] = useState<[string, string | null]>(["temperature", "top_p"]);
      const [aggregations, setAggregations] = useState<Record<string, SweepAggregation>>({
        model: "count",
      });
      return (
        <SweepDimensionPicker
          axes={axes}
          selected={selected}
          onChange={setSelected}
          aggregations={aggregations}
          onAggregationsChange={setAggregations}
        />
      );
    }

    render(<Harness />);

    expect(screen.getByText("Aggregate over")).toBeTruthy();
    const first = screen.getAllByRole("combobox")[0];
    if (!first) throw new Error("missing axis select");
    fireEvent.change(first, { target: { value: "model" } });
    expect((first as HTMLSelectElement).value).toBe("model");
  });
});
