import { SSEDispatcher, type StreamStatus, parseEnvelope } from "@/lib/sse-dispatcher";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { z } from "zod";

/**
 * Minimal hand-rolled EventSource mock — happy-dom's built-in is good
 * enough for shape but doesn't let us trigger error/message ourselves
 * deterministically. We replace globalThis.EventSource with this.
 */
class MockEventSource {
  static instances: MockEventSource[] = [];
  url: string;
  readyState = 0;
  listeners: Record<string, Array<(ev: unknown) => void>> = {};

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }
  addEventListener(type: string, listener: (ev: unknown) => void) {
    const existing = this.listeners[type] ?? [];
    existing.push(listener);
    this.listeners[type] = existing;
  }
  close() {
    this.readyState = 2;
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

describe("SSEDispatcher", () => {
  beforeEach(() => {
    MockEventSource.instances = [];
    (globalThis as { EventSource?: unknown }).EventSource = MockEventSource;
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  const schema = z.discriminatedUnion("type", [
    z.object({ type: z.literal("a"), n: z.number() }),
    z.object({ type: z.literal("b"), s: z.string() }),
  ]);

  it("parses + dispatches messages and tracks status", () => {
    const messages: unknown[] = [];
    const statuses: StreamStatus[] = [];
    const d = new SSEDispatcher({
      url: "/x",
      schema,
      onMessage: (m) => messages.push(m),
      onStatus: (s) => statuses.push(s),
    });
    d.open();
    expect(statuses).toEqual(["connecting"]);

    const es = MockEventSource.instances[0];
    expect(es).toBeDefined();
    es?.emitOpen();
    expect(statuses).toContain("live");

    es?.emitMessage({ type: "a", n: 5 });
    es?.emitMessage({ type: "b", s: "hi" });

    expect(messages).toEqual([
      { type: "a", n: 5 },
      { type: "b", s: "hi" },
    ]);

    d.close();
    expect(statuses[statuses.length - 1]).toBe("idle");
  });

  it("falls back to onUnknown for parse failures", () => {
    const unknowns: unknown[] = [];
    const d = new SSEDispatcher({
      url: "/x",
      schema,
      onMessage: () => {},
      onUnknown: (raw) => unknowns.push(raw),
    });
    d.open();
    const es = MockEventSource.instances[0];
    es?.emitMessage({ type: "c", garbage: true });
    expect(unknowns).toHaveLength(1);
    d.close();
  });

  it("reconnects on error with exponential backoff", () => {
    const statuses: StreamStatus[] = [];
    const d = new SSEDispatcher({
      url: "/x",
      schema,
      onMessage: () => {},
      onStatus: (s) => statuses.push(s),
    });
    d.open();
    const es1 = MockEventSource.instances[0];
    es1?.emitOpen();
    es1?.emitError();
    expect(statuses).toContain("reconnecting");
    expect(MockEventSource.instances.length).toBe(1);

    vi.advanceTimersByTime(250);
    expect(MockEventSource.instances.length).toBe(2);

    const es2 = MockEventSource.instances[1];
    es2?.emitError();
    vi.advanceTimersByTime(500);
    expect(MockEventSource.instances.length).toBe(3);

    d.close();
  });
});

describe("parseEnvelope()", () => {
  it("returns ok=true on match and ok=false on mismatch", () => {
    const schema = z.object({ a: z.number() });
    expect(parseEnvelope({ a: 1 }, schema)).toEqual({ ok: true, data: { a: 1 } });
    const fail = parseEnvelope({ a: "not-a-number" }, schema);
    expect(fail.ok).toBe(false);
  });
});
