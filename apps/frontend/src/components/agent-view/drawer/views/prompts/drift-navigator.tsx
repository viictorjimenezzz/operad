import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  driftGeometry,
  driftTickColor,
} from "@/components/agent-view/insights/drift-strip-primitives";
import { truncateMiddle } from "@/lib/utils";
import type { PromptEntry, PromptTransition } from "@/components/agent-view/drawer/views/prompts/prompt-utils";

interface DriftNavigatorProps {
  entries: PromptEntry[];
  transitions: PromptTransition[];
  selectedTransitionIndex: number;
  onSelectTransition: (index: number) => void;
}

export function DriftNavigator({
  entries,
  transitions,
  selectedTransitionIndex,
  onSelectTransition,
}: DriftNavigatorProps) {
  const selected =
    selectedTransitionIndex >= 0 ? transitions[selectedTransitionIndex] ?? null : null;
  const geometry = driftGeometry(entries.length);

  return (
    <Card>
      <CardHeader>
        <CardTitle>drift navigator</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="ghost"
            disabled={transitions.length === 0 || selectedTransitionIndex <= 0}
            onClick={() => onSelectTransition(selectedTransitionIndex - 1)}
          >
            {'<<'} prev drift
          </Button>
          <div className="min-w-0 flex-1">
            <svg
              width="100%"
              height={16}
              viewBox={`0 0 ${geometry.viewBoxWidth} 16`}
              className="block"
            >
              <title>prompt drift navigator</title>
              {entries.map((entry, index) => {
                const x = index * geometry.barWidth;
                const hash = entry.hash_prompt ?? `missing-${index}`;
                return <rect key={entry.invocation_id} x={x} y={0} width={geometry.barWidth} height={16} fill={driftTickColor(hash)} />;
              })}
              {transitions.map((transition, index) => {
                const x = transition.index * geometry.barWidth;
                const selectedLine = index === selectedTransitionIndex;
                return (
                  <line
                    key={`transition-${transition.after.invocation_id}`}
                    x1={x}
                    y1={0}
                    x2={x}
                    y2={16}
                    stroke={selectedLine ? "var(--color-accent)" : "var(--color-text)"}
                    strokeWidth={selectedLine ? 1.5 : 0.6}
                    className="cursor-pointer"
                    onClick={() => onSelectTransition(index)}
                    onKeyDown={(event) => {
                      if (event.key !== "Enter" && event.key !== " ") return;
                      event.preventDefault();
                      onSelectTransition(index);
                    }}
                  >
                    <title>{`jump to transition ${transition.before.invocation_id} -> ${transition.after.invocation_id}`}</title>
                  </line>
                );
              })}
            </svg>
          </div>
          <Button
            size="sm"
            variant="ghost"
            disabled={
              transitions.length === 0 ||
              selectedTransitionIndex < 0 ||
              selectedTransitionIndex >= transitions.length - 1
            }
            onClick={() => onSelectTransition(selectedTransitionIndex + 1)}
          >
            next drift {'>>'}
          </Button>
        </div>
        {selected ? (
          <p className="m-0 text-[0.7rem] text-muted">
            showing invocation #{selected.index} vs #{selected.index + 1} · hash{" "}
            {truncateMiddle(selected.before.hash_prompt ?? "none", 10)} →{" "}
            {truncateMiddle(selected.after.hash_prompt ?? "none", 10)}
          </p>
        ) : (
          <p className="m-0 text-[0.7rem] text-muted">no drift detected for this agent path</p>
        )}
      </CardContent>
    </Card>
  );
}
