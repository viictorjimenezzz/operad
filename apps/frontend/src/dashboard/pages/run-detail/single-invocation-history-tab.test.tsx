import { SingleInvocationHistoryTab } from "@/dashboard/pages/run-detail/SingleInvocationHistoryTab";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const hookMocks = vi.hoisted(() => ({
  useRunInvocations: vi.fn(),
}));

vi.mock("@/hooks/use-runs", () => ({
  useRunInvocations: hookMocks.useRunInvocations,
}));

const invocations = {
  agent_path: "Root",
  invocations: [
    {
      id: "Root:0",
      started_at: 1000,
      status: "ok",
      latency_ms: 20,
      prompt_tokens: 10,
      completion_tokens: 5,
      cost_usd: 0,
      prompt_system: "first system prompt",
      prompt_user: "first user prompt",
      input: { question: "first question" },
      output: { answer: "first answer" },
    },
    {
      id: "Root:1",
      started_at: 2000,
      status: "ok",
      latency_ms: 30,
      prompt_tokens: 11,
      completion_tokens: 6,
      cost_usd: 0.001,
      prompt_system: "second system prompt",
      prompt_user: "second user prompt",
      input: { question: "second question" },
      output: { answer: "second answer" },
    },
  ],
};

function LocationProbe() {
  const location = useLocation();
  return <span data-testid="location">{location.search}</span>;
}

function renderHistory(initialEntry = "/agents/abc123/runs/run-1/history") {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route
          path="/agents/:hashContent/runs/:runId/history"
          element={
            <>
              <SingleInvocationHistoryTab />
              <LocationProbe />
            </>
          }
        />
      </Routes>
    </MemoryRouter>,
  );
}

describe("SingleInvocationHistoryTab", () => {
  afterEach(cleanup);

  beforeEach(() => {
    hookMocks.useRunInvocations.mockReturnValue({ isLoading: false, data: invocations });
  });

  it("renders all invocations as a timeline without the old previous-invocation wrapper", () => {
    renderHistory();

    expect(screen.getByText("invocation 1")).toBeTruthy();
    expect(screen.getByText("invocation 2")).toBeTruthy();
    expect(screen.getByText((text) => text.includes("first question"))).toBeTruthy();
    expect(screen.getByText((text) => text.includes("second answer"))).toBeTruthy();
    expect(screen.queryByText(/previous invocation/i)).toBeNull();
  });

  it("expands a row to show input, output, and prompts, then stores selection in the URL", () => {
    renderHistory();

    fireEvent.click(screen.getByRole("button", { name: /invocation 2/i }));

    expect(screen.getByText("Input")).toBeTruthy();
    expect(screen.getByText("Output")).toBeTruthy();
    expect(screen.getByText("System Prompt")).toBeTruthy();
    expect(screen.getByText("User Prompt")).toBeTruthy();
    expect(screen.getByText("second system prompt")).toBeTruthy();
    expect(screen.getByText("second user prompt")).toBeTruthy();
    expect(screen.getByTestId("location").textContent).toContain("invocation=Root%3A1");
  });
});
