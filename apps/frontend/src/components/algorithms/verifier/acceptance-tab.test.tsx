import { VerifierAcceptanceTab } from "@/components/algorithms/verifier/acceptance-tab";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

afterEach(cleanup);

describe("VerifierAcceptanceTab", () => {
  it("renders accepted/rejected histogram with threshold and acceptance trend", () => {
    render(
      <VerifierAcceptanceTab
        data={{
          threshold: 0.8,
          converged: true,
          iterations: [
            { iter_index: 0, phase: "verify", score: 0.5, text: "first", metadata: {} },
            { iter_index: 1, phase: "verify", score: 0.9, text: "second", metadata: {} },
          ],
        }}
      />,
    );

    expect(screen.getByText(/threshold 0\.80/i)).toBeTruthy();
    expect(screen.getAllByText(/accepted/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/rejected/i).length).toBeGreaterThan(0);
    expect(screen.getByLabelText("threshold line")).toBeTruthy();
    expect(screen.getByLabelText("acceptance rate line")).toBeTruthy();
  });
});
