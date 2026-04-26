import { CassettesPage } from "@/dashboard/pages/CassettesPage";
import { dashboardApi } from "@/lib/api/dashboard";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/dashboard", () => ({
  dashboardApi: {
    cassettes: vi.fn(),
    cassetteReplay: vi.fn(),
    cassetteDeterminism: vi.fn(),
  },
}));

function renderPage() {
  const qc = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });
  return render(
    <MemoryRouter initialEntries={["/cassettes"]}>
      <QueryClientProvider client={qc}>
        <CassettesPage />
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

afterEach(() => {
  vi.clearAllMocks();
});

describe("CassettesPage", () => {
  it("lists cassettes and runs determinism", async () => {
    vi.mocked(dashboardApi.cassettes).mockResolvedValue([
      {
        path: "trace.jsonl",
        type: "trace",
        size: 12,
        mtime: Date.now() / 1000,
        metadata: { run_id: "r1" },
      },
    ]);
    vi.mocked(dashboardApi.cassetteDeterminism).mockResolvedValue({
      ok: false,
      diff: [{ event_index: 1, field: "x", expected: 1, actual: 2 }],
    });
    vi.mocked(dashboardApi.cassetteReplay).mockResolvedValue({ run_id: "run-1", emitted: 2 });

    renderPage();

    expect(await screen.findByText("trace.jsonl")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /determinism/i }));
    await waitFor(() =>
      expect(dashboardApi.cassetteDeterminism).toHaveBeenCalledWith("trace.jsonl"),
    );
    expect(await screen.findByText(/drift/i)).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /^replay$/i }));
    await waitFor(() =>
      expect(dashboardApi.cassetteReplay).toHaveBeenCalledWith({
        path: "trace.jsonl",
        delayMs: 50,
      }),
    );
  });
});
