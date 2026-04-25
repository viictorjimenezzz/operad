/**
 * End-to-end fixture validation: every recorded operad envelope must
 * parse through our Zod Envelope union and route correctly through
 * dispatchEnvelope() into the right Zustand slice.
 *
 * Re-capture instructions: see src/tests/fixtures/README.md.
 */
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { Envelope, RunEventsResponse } from "@/lib/types";
import { dispatchEnvelope, useEventBufferStore, useStatsStore } from "@/stores";
import { jsonlRecordToEnvelope, parseJsonl } from "@/tests/replay-sse";
import { afterEach, describe, expect, it } from "vitest";

const fixturesDir = resolve(dirname(fileURLToPath(import.meta.url)), "fixtures");

afterEach(() => {
  useEventBufferStore.getState().clear();
  useStatsStore.setState({ slotOccupancy: [], costTotals: {}, globalStats: null });
});

describe("real fixtures", () => {
  it("parses every record from the JsonlObserver trace", () => {
    const raw = readFileSync(resolve(fixturesDir, "agent-evolution-trace.jsonl"), "utf8");
    const records = parseJsonl(raw);
    expect(records.length).toBeGreaterThan(0);

    let parsed = 0;
    for (const rec of records) {
      const env = jsonlRecordToEnvelope(rec);
      expect(env).not.toBeNull();
      const result = Envelope.safeParse(env);
      if (!result.success) {
        throw new Error(
          `record #${parsed} failed: ${JSON.stringify(result.error.issues).slice(0, 400)}`,
        );
      }
      parsed++;
    }
    expect(parsed).toBe(records.length);
  });

  it("parses an /runs/{id}/events response and routes it into the buffer", () => {
    const raw = readFileSync(resolve(fixturesDir, "agent-evolution-events.json"), "utf8");
    const data: unknown = JSON.parse(raw);
    const parsed = RunEventsResponse.parse(data);
    expect(parsed.events.length).toBeGreaterThan(0);

    for (const env of parsed.events) {
      dispatchEnvelope(env);
    }

    const buf = useEventBufferStore.getState().eventsByRun.get(parsed.run_id) ?? [];
    expect(buf.length).toBe(parsed.events.length);
  });

  it("derives liveGenerations from a real generation envelope", () => {
    const raw = readFileSync(resolve(fixturesDir, "agent-evolution-events.json"), "utf8");
    const parsed = RunEventsResponse.parse(JSON.parse(raw));
    const generations = parsed.events.filter(
      (e) => e.type === "algo_event" && e.kind === "generation",
    );
    expect(generations.length).toBeGreaterThan(0);

    for (const env of generations) {
      dispatchEnvelope(env);
    }
    const live = useEventBufferStore.getState().liveGenerations;
    expect(live.length).toBe(generations.length);
    // Every generation must produce a numeric best+mean (non-null).
    for (const g of live) {
      expect(typeof g.best).toBe("number");
      expect(typeof g.mean).toBe("number");
    }
  });
});
