import { CriticRationaleCard } from "@/components/algorithms/beam/critic-rationale-card";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

afterEach(cleanup);

describe("CriticRationaleCard", () => {
  it("renders candidate text and run metadata without a critic run", () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <CriticRationaleCard
          candidate={{
            candidate_index: 4,
            score: 0.91,
            text: "winner text",
            timestamp: 1,
            iter_index: 0,
          }}
          generatorRun={null}
          criticRun={null}
          rank={1}
          topK
        />
      </QueryClientProvider>,
    );

    expect(screen.getByText(/candidate #4 selected/)).toBeTruthy();
    expect(screen.getByText("winner text")).toBeTruthy();
    expect(screen.getByText("0.910")).toBeTruthy();
  });
});
