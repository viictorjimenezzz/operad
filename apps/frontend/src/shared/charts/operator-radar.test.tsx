import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { OperatorRadar } from "./operator-radar";

afterEach(cleanup);

describe("OperatorRadar", () => {
  it("renders empty state without operators", () => {
    render(
      <OperatorRadar
        runs={[
          { runId: "r1", label: "r1", operatorRates: {} },
          { runId: "r2", label: "r2", operatorRates: {} },
        ]}
      />,
    );
    expect(screen.getByText("no mutation operator data")).toBeTruthy();
  });

  it("renders radar for unioned operator axes", () => {
    const { container } = render(
      <OperatorRadar
        runs={[
          { runId: "r1", label: "r1", operatorRates: { append_rule: 0.6, set_temp: 0.2 } },
          { runId: "r2", label: "r2", operatorRates: { append_rule: 0.4 } },
        ]}
      />,
    );

    expect(container.querySelector(".recharts-responsive-container")).toBeTruthy();
    expect(screen.queryByText("no mutation operator data")).toBeNull();
  });
});
