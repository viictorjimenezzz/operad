/**
 * Tests for DashboardRenderer — backfill-then-stream behavior.
 *
 * We mock:
 *   - globalThis.fetch  (JSON snapshot endpoints)
 *   - globalThis.EventSource (SSE streams) via MockEventSource
 *   - @/stores (Zustand eventBuffer so we don't need a real provider)
 *   - @json-render/react (Renderer — captures the resolved tree)
 */
import { DashboardRenderer } from "@/components/runtime/dashboard-renderer";
import type { LayoutSpec } from "@/lib/layout-schema";
import type { UITree } from "@json-render/core";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, waitFor } from "@testing-library/react";
import type React from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const renderedTrees: UITree[] = [];

vi.mock("@json-render/react", () => ({
  Renderer: ({ tree }: { tree: UITree }) => {
    renderedTrees.push(tree);
    return null;
  },
  JSONUIProvider: ({ children }: { children: React.ReactNode }) => children,
}));

vi.mock("@/stores", () => ({
  useEventBufferStore: (selector: (state: { eventsByRun: Map<string, unknown[]> }) => unknown) =>
    selector({ eventsByRun: new Map() }),
}));

vi.mock("@/components/registry", () => ({ registry: {} }));

class MockEventSource {
  static instances: MockEventSource[] = [];
  url: string;
  listeners: Record<string, Array<(ev: unknown) => void>> = {};
  closed = false;

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }
  addEventListener(type: string, cb: (ev: unknown) => void) {
    const listeners = this.listeners[type];
    if (listeners) listeners.push(cb);
    else this.listeners[type] = [cb];
  }
  close() {
    this.closed = true;
  }
  emit(type: string, ev: unknown) {
    for (const l of this.listeners[type] ?? []) l(ev);
  }
  emitMessage(data: unknown) {
    this.emit("message", { data: JSON.stringify(data) });
  }
  emitOpen() {
    this.emit("open", {});
  }
  emitError() {
    this.emit("error", {});
  }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeLayout(overrides: Partial<LayoutSpec["dataSources"]> = {}): LayoutSpec {
  return {
    algorithm: "Test",
    version: 1,
    dataSources: {
      fitness: {
        endpoint: "/runs/r1/fitness.json",
        stream: "/runs/r1/fitness.sse",
      },
      ...overrides,
    },
    spec: {
      root: "root",
      elements: { root: { type: "Col" } },
    },
  };
}

function makeQC() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
}

function Wrapper({
  qc,
  children,
  initialEntries = ["/"],
}: {
  qc: QueryClient;
  children: React.ReactNode;
  initialEntries?: string[];
}) {
  return (
    <MemoryRouter initialEntries={initialEntries}>
      <QueryClientProvider client={qc}>{children}</QueryClientProvider>
    </MemoryRouter>
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("DashboardRenderer", () => {
  beforeEach(() => {
    MockEventSource.instances = [];
    renderedTrees.length = 0;
    (globalThis as { EventSource?: unknown }).EventSource = MockEventSource;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("fires a fetch for each data source endpoint on mount", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [],
    });
    vi.stubGlobal("fetch", fetchMock);

    const qc = makeQC();
    render(
      <Wrapper qc={qc}>
        <DashboardRenderer layout={makeLayout()} context={{ runId: "r1" }} />
      </Wrapper>,
    );

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/runs/r1/fitness.json"));
  });

  it("reuses standard run query keys for summary and invocations data sources", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ invocations: [] }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const qc = makeQC();
    const layout = makeLayout({
      summary: { endpoint: "/runs/$context.runId/summary" },
      invocations: { endpoint: "/runs/$context.runId/invocations" },
    });
    render(
      <Wrapper qc={qc}>
        <DashboardRenderer layout={layout} context={{ runId: "r1" }} />
      </Wrapper>,
    );

    await waitFor(() => expect(qc.getQueryData(["run", "summary", "r1"])).toBeDefined());
    expect(qc.getQueryData(["run", "invocations", "r1"])).toEqual({ invocations: [] });
  });

  it("opens an SSE stream for data sources that have a stream field", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => [] }));

    const qc = makeQC();
    render(
      <Wrapper qc={qc}>
        <DashboardRenderer layout={makeLayout()} context={{ runId: "r1" }} />
      </Wrapper>,
    );

    // SSEDispatcher opens EventSource synchronously
    expect(MockEventSource.instances.length).toBeGreaterThanOrEqual(1);
    const first = MockEventSource.instances[0];
    expect(first?.url).toBe("/runs/r1/fitness.sse");
  });

  it("merges SSE delta into query cache via setQueryData (not separate streamed state)", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => [] }));

    const qc = makeQC();
    const setQueryDataSpy = vi.spyOn(qc, "setQueryData");

    render(
      <Wrapper qc={qc}>
        <DashboardRenderer layout={makeLayout()} context={{ runId: "r1" }} />
      </Wrapper>,
    );

    const es = MockEventSource.instances[0];
    if (!es) throw new Error("no EventSource created");
    act(() => {
      es.emitOpen();
      es.emitMessage({ gen_index: 0, best: 0.9 });
    });

    expect(setQueryDataSpy).toHaveBeenCalled();
  });

  it("invalidates the query key on SSE reconnect", async () => {
    vi.useFakeTimers();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => [] }));

    const qc = makeQC();
    const invalidateSpy = vi.spyOn(qc, "invalidateQueries");

    render(
      <Wrapper qc={qc}>
        <DashboardRenderer layout={makeLayout()} context={{ runId: "r1" }} />
      </Wrapper>,
    );

    const es = MockEventSource.instances[0];
    if (!es) throw new Error("no EventSource created");
    act(() => {
      es.emitOpen();
      es.emitError(); // triggers reconnect status
    });

    expect(invalidateSpy).toHaveBeenCalled();
    vi.useRealTimers();
  });

  it("closes SSE connections when context.runId changes", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => [] }));

    const qc = makeQC();
    const layout = makeLayout();
    const { rerender } = render(
      <Wrapper qc={qc}>
        <DashboardRenderer layout={layout} context={{ runId: "r1" }} />
      </Wrapper>,
    );

    const firstEs = MockEventSource.instances[0];
    if (!firstEs) throw new Error("no EventSource created");

    rerender(
      <Wrapper qc={qc}>
        <DashboardRenderer layout={layout} context={{ runId: "r2" }} />
      </Wrapper>,
    );

    expect(firstEs.closed).toBe(true);
  });

  it("uses ?tab to mount only the active tab subtree", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => [] }));

    const qc = makeQC();
    const layout: LayoutSpec = {
      algorithm: "Test",
      version: 1,
      dataSources: {},
      spec: {
        root: "page",
        elements: {
          page: {
            type: "Tabs",
            props: {
              tabs: [
                { id: "overview", label: "Overview" },
                { id: "events", label: "Events" },
              ],
            },
            children: ["overview", "events"],
          },
          overview: { type: "Card", props: { title: "Overview" } },
          events: { type: "Card", props: { title: "Events" } },
        },
      },
    };

    render(
      <Wrapper qc={qc} initialEntries={["/?tab=events"]}>
        <DashboardRenderer layout={layout} context={{ runId: "r1" }} />
      </Wrapper>,
    );

    await waitFor(() =>
      expect(renderedTrees.some((tree) => tree.elements.page?.props?.activeTab === "events")).toBe(
        true,
      ),
    );
    const tree = renderedTrees.find((item) => item.elements.page?.props?.activeTab === "events");
    expect(tree?.elements.page?.props?.activeTab).toBe("events");
    expect(tree?.elements.page?.children).toEqual(["events"]);
  });

  it("hides tabs whose condition resolves falsy", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => [] }));

    const qc = makeQC();
    const layout: LayoutSpec = {
      algorithm: "Test",
      version: 1,
      dataSources: {},
      spec: {
        root: "page",
        elements: {
          page: {
            type: "Tabs",
            props: {
              tabs: [
                { id: "overview", label: "Overview" },
                { id: "events", label: "Events", condition: "$expr:count($queries.children)" },
              ],
            },
            children: ["overview", "events"],
          },
          overview: { type: "Card", props: { title: "Overview" } },
          events: { type: "Card", props: { title: "Events" } },
        },
      },
    };

    render(
      <Wrapper qc={qc}>
        <DashboardRenderer layout={layout} context={{ runId: "r1" }} />
      </Wrapper>,
    );

    await waitFor(() =>
      expect(renderedTrees.some((tree) => Array.isArray(tree.elements.page?.props?.tabs))).toBe(
        true,
      ),
    );
    const tree = renderedTrees.find((item) => Array.isArray(item.elements.page?.props?.tabs));
    const tabs = tree?.elements.page?.props?.tabs;
    expect(tabs).toEqual([{ id: "overview", label: "Overview" }]);
    expect(tree?.elements.page?.children).toEqual(["overview"]);
  });
});
