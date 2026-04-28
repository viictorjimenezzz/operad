import { VerifierIterationsTab } from "@/components/algorithms/verifier/iterations-tab";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

afterEach(cleanup);

describe("VerifierIterationsTab", () => {
  it("renders per-iteration candidate, score, and acceptance", () => {
    render(
      <MemoryRouter>
        <VerifierIterationsTab
          data={{
            threshold: 0.8,
            converged: true,
            iterations: [
              { iter_index: 0, phase: "verify", score: 0.5, text: "first candidate", metadata: {} },
              { iter_index: 1, phase: "verify", score: 0.9, text: "second candidate", metadata: {} },
            ],
          }}
        />
      </MemoryRouter>,
    );

    expect(screen.getAllByText("first candidate").length).toBeGreaterThan(0);
    expect(screen.getByText("second candidate")).toBeTruthy();
    expect(screen.getAllByText("accepted").length).toBeGreaterThan(0);
    expect(screen.getAllByText("rejected").length).toBeGreaterThan(0);
  });
});
