import { BeamLeaderboard } from "@/components/algorithms/beam/beam-leaderboard";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

afterEach(cleanup);

function wrapper(children: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={client}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}

describe("BeamLeaderboard", () => {
  it("sorts scored candidates descending and expands a candidate", () => {
    render(
      wrapper(
        <BeamLeaderboard
          runId="beam-1"
          data={[
            { candidate_index: 0, score: 0.2, text: "low", timestamp: 1, iter_index: 0 },
            { candidate_index: 1, score: 0.9, text: "high", timestamp: 1, iter_index: 0 },
          ]}
          dataIterations={{
            iterations: [{ iter_index: 0, phase: "prune", metadata: { top_indices: [1] } }],
          }}
          dataChildren={[]}
        />,
      ),
    );

    const text = document.body.textContent ?? "";
    expect(text.indexOf("#1")).toBeLessThan(text.indexOf("#0"));
    fireEvent.click(screen.getByText("#1"));
    expect(screen.getByText("Full text")).toBeTruthy();
    expect(screen.getAllByText("high").length).toBeGreaterThan(0);
  });

  it("hides score column for judge-free candidates", () => {
    render(
      wrapper(
        <BeamLeaderboard
          runId="beam-1"
          data={[
            { candidate_index: 0, score: null, text: "generated", timestamp: 1, iter_index: 0 },
          ]}
          dataChildren={[]}
        />,
      ),
    );

    expect(screen.queryByText("Score")).toBeNull();
    expect(screen.getByText("#0")).toBeTruthy();
  });
});
