import { VerifierIterations } from "@/components/algorithms/verifier/verifier-iterations";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

afterEach(cleanup);

describe("VerifierIterations", () => {
  it("renders per-iteration accept and reject states against threshold", () => {
    render(
      <MemoryRouter>
        <VerifierIterations
          data={{
            threshold: 0.8,
            converged: true,
            iterations: [
              { iter_index: 0, phase: "verify", score: 0.5, text: "first", metadata: {} },
              { iter_index: 1, phase: "verify", score: 0.9, text: "second", metadata: {} },
            ],
          }}
        />
      </MemoryRouter>,
    );

    expect(screen.getByText(/Reject/)).toBeTruthy();
    expect(screen.getByText(/Accept/)).toBeTruthy();
    expect(screen.getByText("first")).toBeTruthy();
    expect(screen.getByText("second")).toBeTruthy();
  });
});
