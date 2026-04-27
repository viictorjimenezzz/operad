import { EventsTab } from "@/components/agent-view/page-shell/events-tab";
import type { EventEnvelope } from "@/lib/types";
import { useEventBufferStore } from "@/stores";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const hookMocks = vi.hoisted(() => ({
  useManifest: vi.fn(),
  useRunEvents: vi.fn(),
  useRunSummary: vi.fn(),
}));

vi.mock("@/hooks/use-runs", () => ({
  useManifest: hookMocks.useManifest,
  useRunEvents: hookMocks.useRunEvents,
  useRunSummary: hookMocks.useRunSummary,
}));

function LocationProbe() {
  const location = useLocation();
  return <div data-testid="location">{location.search}</div>;
}

function renderTab(initialEntry = "/algorithms/run-1") {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <EventsTab runId="run-1" />
      <LocationProbe />
    </MemoryRouter>,
  );
}

function setEvents(events: EventEnvelope[], state: "running" | "ended" = "ended") {
  hookMocks.useRunEvents.mockReturnValue({
    data: { run_id: "run-1", events },
    isLoading: false,
    error: null,
  });
  hookMocks.useRunSummary.mockReturnValue({
    data: { run_id: "run-1", state },
    isLoading: false,
    error: null,
  });
}

function algo(
  kind: string,
  payload: Record<string, unknown>,
  startedAt: number,
): Extract<EventEnvelope, { type: "algo_event" }> {
  return {
    type: "algo_event",
    run_id: "run-1",
    algorithm_path: "operad.algorithms.sweep.Sweep",
    kind,
    payload,
    started_at: startedAt,
    finished_at: startedAt,
    metadata: {},
  };
}

function agent(
  kind: "start" | "end" | "error" | "chunk",
  path: string,
  startedAt: number,
): Extract<EventEnvelope, { type: "agent_event" }> {
  return {
    type: "agent_event",
    run_id: "run-1",
    agent_path: path,
    kind,
    input: null,
    output: null,
    started_at: startedAt,
    finished_at: startedAt + 0.1,
    metadata: {},
    error: null,
  };
}

beforeEach(() => {
  hookMocks.useManifest.mockReturnValue({ data: { langfuseUrl: "http://lf.example" } });
  useEventBufferStore.getState().clear();
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  useEventBufferStore.getState().clear();
});

describe("<EventsTab />", () => {
  it("applies the inferred Sweep default kind filter", () => {
    setEvents([
      algo("algo_start", { n: 5 }, 1),
      algo("cell", { cell_index: 3, parameters: { model: "small" } }, 2),
    ]);

    renderTab();

    expect(screen.getByText("Kind: cell")).toBeTruthy();
    expect(screen.getByText("cell #3 model=small")).toBeTruthy();
    expect(screen.queryByText("algo_start")).toBeNull();
  });

  it("syncs type and path filters from the URL", () => {
    setEvents([
      agent("start", "Root.Reasoner", 1),
      agent("start", "Root.Critic", 2),
      algo("cell", { cell_index: 1 }, 3),
    ]);

    renderTab("/algorithms/run-1?kind=any&type=agent_event&path=Root.Reasoner");

    const rows = within(screen.getByLabelText("event rows"));
    expect(rows.getByText("Root.Reasoner")).toBeTruthy();
    expect(rows.queryByText("Root.Critic")).toBeNull();
    expect(rows.queryByText("cell")).toBeNull();
  });

  it("supports keyboard selection, deep links, search focus, and Langfuse detail links", async () => {
    const first = agent("start", "Root.Planner", 1);
    const second = {
      ...agent("end", "Root.Planner", 2),
      metadata: { span_id: "span-a" },
    };
    setEvents([first, second]);

    renderTab();

    const root = screen.getByRole("application", { name: "events timeline" });
    fireEvent.keyDown(root, { key: "j" });
    fireEvent.keyDown(root, { key: "Enter" });

    expect(screen.getAllByText("end").length).toBeGreaterThan(0);
    expect(screen.getByTestId("location").textContent).toContain("event=1");
    expect(screen.getByText("Open in Langfuse").getAttribute("href")).toBe(
      "http://lf.example/trace/run-1?observation=span-a",
    );

    fireEvent.keyDown(root, { key: "/" });
    await waitFor(() => {
      expect(document.activeElement).toBe(screen.getByPlaceholderText("Search..."));
    });

    fireEvent.keyDown(root, { key: "Escape" });
    expect(screen.getByTestId("location").textContent).not.toContain("event=");
  });

  it("shows severity filtering only for gradient events", () => {
    setEvents([
      {
        ...algo("gradient_applied", { severity: 0.9, target_paths: ["role"] }, 1),
        algorithm_path: "operad.train.Trainer",
      },
      {
        ...algo("iteration", { iter_index: 1, phase: "train" }, 2),
        algorithm_path: "operad.train.Trainer",
      },
    ]);

    renderTab();

    fireEvent.change(screen.getByLabelText("Severity filter"), { target: { value: "high" } });
    const rows = within(screen.getByLabelText("event rows"));
    expect(rows.getByText("severity 0.900 -> role")).toBeTruthy();
    expect(rows.queryByText("iteration")).toBeNull();
  });

  it("includes stream-buffered events when live follow is enabled", async () => {
    setEvents([agent("start", "Root.Live", 1)], "running");

    renderTab();

    await waitFor(() => {
      expect((screen.getByLabelText("Live") as HTMLInputElement).checked).toBe(true);
    });

    act(() => {
      useEventBufferStore.getState().ingest(agent("end", "Root.Live", 2));
    });

    expect(await screen.findByText("Live end (100ms)")).toBeTruthy();
  });
});
