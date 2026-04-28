import { EmptyState } from "@/components/ui";
import { cn } from "@/lib/utils";
import { buildTurnRows } from "@/components/algorithms/talker_reasoner/transcript-tab";

interface TalkerTreeTabProps {
  dataSummary?: unknown;
  dataEvents?: unknown;
}

export function TalkerTreeTab({ dataSummary, dataEvents }: TalkerTreeTabProps) {
  const turns = buildTurnRows(dataSummary, dataEvents);

  if (turns.length === 0) {
    return (
      <EmptyState
        title="no routing turns yet"
        description="TalkerReasoner speak events will populate the decision tree"
      />
    );
  }

  return (
    <div className="h-full overflow-auto p-4">
      <div className="mb-3 flex items-center justify-between border-b border-border pb-2">
        <div className="text-[10px] uppercase tracking-[0.08em] text-muted-2">decision tree</div>
        <div className="font-mono text-[11px] text-muted">{turns.length} turns</div>
      </div>

      <div className="grid gap-4">
        {turns.map((turn, index) => {
          const choice = turn.routerChoice.toLowerCase();
          const chooseTalker = choice.includes("talk") || choice === "advance";
          const chooseReasoner = !chooseTalker;

          return (
            <section key={turn.turn} className="rounded-lg border border-border bg-bg-1">
              <div className="flex items-center justify-between border-b border-border px-3 py-2">
                <div className="font-mono text-[11px] text-text">turn {turn.turn}</div>
                <div className="text-[11px] text-muted">
                  {turn.fromNodeId || "-"} -&gt; {turn.toNodeId || "-"}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2 p-3">
                <BranchCard
                  label="talker"
                  selected={chooseTalker}
                  dimmed={!chooseTalker}
                  confidence={turn.routerConfidence}
                />
                <BranchCard
                  label="reasoner"
                  selected={chooseReasoner}
                  dimmed={!chooseReasoner}
                  confidence={turn.routerConfidence}
                />
              </div>

              {index < turns.length - 1 ? (
                <div className="flex justify-center pb-2">
                  <div className="h-4 w-px bg-border" />
                </div>
              ) : null}
            </section>
          );
        })}
      </div>
    </div>
  );
}

function BranchCard({
  label,
  selected,
  dimmed,
  confidence,
}: {
  label: string;
  selected: boolean;
  dimmed: boolean;
  confidence: number | null;
}) {
  return (
    <div
      className={cn(
        "rounded-md border px-2 py-2 transition-colors",
        selected
          ? "border-[--color-accent-dim] bg-[--color-accent-dim]/15 text-text"
          : "border-border bg-bg-2 text-muted",
        dimmed && "opacity-55",
      )}
    >
      <div className="text-[10px] uppercase tracking-[0.08em]">{label}</div>
      <div className="mt-1 font-mono text-[11px]">
        {selected ? "chosen" : "not chosen"}
        {selected && confidence != null ? ` · ${(confidence * 100).toFixed(1)}%` : ""}
      </div>
    </div>
  );
}
