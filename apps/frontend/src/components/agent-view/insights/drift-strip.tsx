import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  buildDriftTicks,
  driftGeometry,
  driftTickColor,
  findDriftTransitions,
  makeBestOfGroups,
} from "@/components/agent-view/insights/drift-strip-primitives";
import type { RunInvocation, RunSummary } from "@/lib/types";
import { formatRelativeTime, truncateMiddle } from "@/lib/utils";
import { useUIStore } from "@/stores/ui";

export interface DriftStripProps {
  invocations: RunInvocation[];
  rootPath: string | null;
  summary: RunSummary;
}

export function DriftStrip({ invocations, rootPath, summary }: DriftStripProps) {
  const openDrawer = useUIStore((s) => s.openDrawer);
  const ticks = buildDriftTicks(invocations);
  const transitions = findDriftTransitions(ticks);
  const uniquePromptCount = new Set(ticks.map((tick) => tick.hashPrompt)).size;
  const lastTransition = transitions[transitions.length - 1];
  const now = Date.now() / 1000;
  const groups = makeBestOfGroups(ticks);
  const geometry = driftGeometry(ticks.length);

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
            <svg
              width="100%"
              height={16}
              viewBox={`0 0 ${geometry.viewBoxWidth} 16`}
              className="block"
            >
              <title>prompt hash transitions</title>
              {ticks.map((tick, index) => {
                const x = index * geometry.barWidth;
                const groupSize = groups.get(`${tick.hashPrompt}::${tick.hashInput}`) ?? 1;
                return (
                  <g key={tick.id}>
                    <rect
                      x={x}
                      y={0}
                      width={geometry.barWidth}
                      height={16}
                      fill={driftTickColor(tick.hashPrompt)}
                    >
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
                const markerX = transition.index * geometry.barWidth;
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
                    onKeyDown={(e) => {
                      if (e.key !== "Enter" && e.key !== " ") return;
                      e.preventDefault();
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

export {
  buildDriftTicks,
  driftGeometry,
  driftTickColor,
  findDriftTransitions,
  makeBestOfGroups,
} from "@/components/agent-view/insights/drift-strip-primitives";
