/**
 * Tests for DashboardRenderer — backfill-then-stream behavior.
 *
 * We mock:
 *   - globalThis.fetch  (JSON snapshot endpoints)
 *   - globalThis.EventSource (SSE streams) via MockEventSource
 *   - @/stores (Zustand eventBuffer so we don't need a real provider)
 *   - @json-render/react (Renderer — we only care about data wiring, not rendering)
 */
import { DashboardRenderer } from "@/components/DashboardRenderer";
import type { LayoutSpec } from "@/lib/layout-schema";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, act, waitFor } from "@testing-library/react";
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("@json-render/react", () => ({
  Renderer: () => null,
  JSONUIProvider: ({ children }: { children: React.ReactNode }) => children,
}));

vi.mock("@/stores", () => ({
  useEventBufferStore: () => new Map(),
}));

vi.mock("@/registry/registry", () => ({ registry: {} }));
vi.mock("@/registry/resolve", () => ({
  resolveSource: (_expr: string) => undefined,
}));

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
    (this.listeners[type] ??= []).push(cb);
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

function Wrapper({ qc, children }: { qc: QueryClient; children: React.ReactNode }) {
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("DashboardRenderer", () => {
  beforeEach(() => {
    MockEventSource.instances = [];
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
});
