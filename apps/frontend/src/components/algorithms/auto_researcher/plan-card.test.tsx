import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { PlanCard } from "./plan-card";

afterEach(cleanup);

describe("<PlanCard />", () => {
  it("renders structured plan fields, evidence, and retriever links", () => {
    render(
      <PlanCard
        attemptIndex={1}
        plan={{ query: "bee colony collapse", policy_question: "EU bans" }}
        evidence={["doc#3: neonicotinoid correlation"]}
        retrieverHrefs={["/agents/retriever/runs/r1"]}
      />,
    );

    expect(screen.getByText("Attempt #2 plan")).toBeDefined();
    expect(screen.getByText(/bee colony collapse/)).toBeDefined();
    expect(screen.getByText("doc#3: neonicotinoid correlation")).toBeDefined();
    expect(screen.getByRole("link", { name: /retriever 1/i }).getAttribute("href")).toBe(
      "/agents/retriever/runs/r1",
    );
  });

  it("shows the legacy empty state when no plan exists", () => {
    render(<PlanCard attemptIndex={null} plan={null} />);

    expect(screen.getByText("plan not available")).toBeDefined();
  });
});
