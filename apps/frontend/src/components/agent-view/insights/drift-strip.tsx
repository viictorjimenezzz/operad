import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { hashColor } from "@/lib/hash-color";
import { formatRelativeTime, truncateMiddle } from "@/lib/utils";
import type { RunInvocation, RunSummary } from "@/lib/types";
import { useUIStore } from "@/stores/ui";

export interface DriftStripProps {
  invocations: RunInvocation[];
  rootPath: string | null;
  summary: RunSummary;
}

interface Tick {
  id: string;
  startedAt: number;
  hashPrompt: string;
  hashInput: string;
}

export function DriftStrip({ invocations, rootPath, summary }: DriftStripProps) {
  const openDrawer = useUIStore((s) => s.openDrawer);
  const ticks = downsample(invocations);
  const transitions = findTransitions(ticks);
  const uniquePromptCount = new Set(ticks.map((tick) => tick.hashPrompt)).size;
  const lastTransition = transitions[transitions.length - 1];
  const now = Date.now() / 1000;
  const groups = makeBestOfGroups(ticks);

  return (
    <Card>
      <CardHeader>
        <CardTitle>prompt drift</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {ticks.length === 0 ? (
          <div className="rounded border border-dashed border-border p-3 text-[0.72rem] text-muted">
            no invocations yet
          </div>
        ) : (
          <div className="relative">
            <svg width="100%" height={16} viewBox={`0 0 ${ticks.length * 3} 16`} className="block">
              {ticks.map((tick, index) => {
                const x = index * 3;
                const groupSize = groups.get(`${tick.hashPrompt}::${tick.hashInput}`) ?? 1;
                return (
                  <g key={tick.id}>
                    <rect x={x} y={0} width={3} height={16} fill={hashColor(tick.hashPrompt)}>
                      <title>
                        {`#${index + 1} · ${new Date(tick.startedAt * 1000).toISOString()} · ${truncateMiddle(tick.hashPrompt, 12)}${groupSize > 1 ? ` · best-of ${groupSize}` : ""}`}
                      </title>
                    </rect>
                    {summary.state === "running" && index === ticks.length - 1 ? (
                      <circle cx={x + 1.5} cy={8} r={1.5} className="animate-pulse fill-accent" />
                    ) : null}
                  </g>
                );
              })}
              {transitions.map((transition) => {
                const markerX = transition.index * 3;
                return (
                  <line
                    key={`transition-${transition.after.id}`}
                    x1={markerX}
                    y1={0}
                    x2={markerX}
                    y2={16}
                    stroke="var(--color-text)"
                    strokeWidth={0.6}
                    className="cursor-pointer"
                    onClick={() => {
                      if (!rootPath) return;
                      openDrawer("prompts", { agentPath: rootPath, focus: transition.after.id });
                    }}
                  >
                    <title>{`open prompt diff at ${transition.after.id}`}</title>
                  </line>
                );
              })}
            </svg>
          </div>
        )}
        <p className="m-0 text-[0.68rem] text-muted">
          {ticks.length} invocations · {uniquePromptCount} unique prompts · last drift{" "}
          {lastTransition ? formatRelativeTime(lastTransition.after.startedAt, now) : "never"}
        </p>
      </CardContent>
    </Card>
  );
}

function findTransitions(ticks: Tick[]): Array<{ index: number; before: Tick; after: Tick }> {
  const out: Array<{ index: number; before: Tick; after: Tick }> = [];
  for (let i = 1; i < ticks.length; i += 1) {
    const prev = ticks[i - 1];
    const current = ticks[i];
    if (!prev || !current) continue;
    if (prev.hashPrompt !== current.hashPrompt) out.push({ index: i, before: prev, after: current });
  }
  return out;
}

function downsample(invocations: RunInvocation[]): Tick[] {
  const base = invocations.map((invocation) => ({
    id: invocation.id,
    startedAt: invocation.started_at,
    hashPrompt: invocation.hash_prompt,
    hashInput: invocation.hash_input,
  }));
  if (base.length <= 500) return base;
  const buckets = 240;
  const bucketSize = Math.ceil(base.length / buckets);
  const sampled: Tick[] = [];
  for (let i = 0; i < base.length; i += bucketSize) {
    const slice = base.slice(i, i + bucketSize);
    if (!slice.length) continue;
    sampled.push(slice[Math.floor(slice.length / 2)] as Tick);
  }
  return sampled;
}

function makeBestOfGroups(ticks: Tick[]): Map<string, number> {
  const map = new Map<string, number>();
  for (const tick of ticks) {
    const key = `${tick.hashPrompt}::${tick.hashInput}`;
    map.set(key, (map.get(key) ?? 0) + 1);
  }
  return map;
}
