import { hashColor } from "@/lib/hash-color";
import type { RunInvocation } from "@/lib/types";

export interface DriftTick {
  id: string;
  startedAt: number;
  hashPrompt: string;
  hashInput: string;
}

export interface DriftTransition {
  index: number;
  before: DriftTick;
  after: DriftTick;
}

export function buildDriftTicks(invocations: RunInvocation[]): DriftTick[] {
  const base = invocations.map((invocation) => ({
    id: invocation.id,
    startedAt: invocation.started_at,
    hashPrompt: invocation.hash_prompt ?? "",
    hashInput: invocation.hash_input ?? "",
  }));
  if (base.length <= 500) return base;
  const buckets = 240;
  const bucketSize = Math.ceil(base.length / buckets);
  const sampled: DriftTick[] = [];
  for (let i = 0; i < base.length; i += bucketSize) {
    const slice = base.slice(i, i + bucketSize);
    if (!slice.length) continue;
    sampled.push(slice[Math.floor(slice.length / 2)] as DriftTick);
  }
  return sampled;
}

export function findDriftTransitions(ticks: DriftTick[]): DriftTransition[] {
  const out: DriftTransition[] = [];
  for (let i = 1; i < ticks.length; i += 1) {
    const prev = ticks[i - 1];
    const current = ticks[i];
    if (!prev || !current) continue;
    if (prev.hashPrompt !== current.hashPrompt) {
      out.push({ index: i, before: prev, after: current });
    }
  }
  return out;
}

export function makeBestOfGroups(ticks: DriftTick[]): Map<string, number> {
  const map = new Map<string, number>();
  for (const tick of ticks) {
    const key = `${tick.hashPrompt}::${tick.hashInput}`;
    map.set(key, (map.get(key) ?? 0) + 1);
  }
  return map;
}

export interface DriftStripGeometry {
  viewBoxWidth: number;
  barWidth: number;
}

export function driftGeometry(tickCount: number): DriftStripGeometry {
  const barWidth = 3;
  return {
    viewBoxWidth: Math.max(1, tickCount * barWidth),
    barWidth,
  };
}

export function driftTickColor(hashPrompt: string): string {
  return hashColor(hashPrompt);
}
