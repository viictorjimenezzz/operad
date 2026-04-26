import { EmptyState } from "@/components/ui/empty-state";
import { Round } from "@/lib/types";
import { z } from "zod";

const RoundsArray = z.array(Round);

/**
 * Renders Debate algorithm rounds. Each round shows per-proposer
 * scores as a horizontal bar. Best score per round highlighted.
 */
export function DebateRoundView({ data }: { data: unknown }) {
  const parsed = RoundsArray.safeParse(data);
  if (!parsed.success || parsed.data.length === 0) {
    return <EmptyState title="no debate rounds" description="round events haven't arrived yet" />;
  }

  return (
    <ol className="flex flex-col gap-3 text-xs">
      {parsed.data.map((r) => {
        const max = r.scores.length > 0 ? Math.max(...r.scores) : 0;
        return (
          <li
            key={r.round_index ?? Math.random()}
            className="rounded-md border border-border bg-bg-2 p-3"
          >
            <div className="flex items-center justify-between text-muted">
              <span className="text-[0.68rem] uppercase tracking-[0.08em]">
                round {r.round_index ?? "?"}
              </span>
              <span className="font-mono">{r.scores.length} proposers</span>
            </div>
            <div className="mt-2 flex flex-col gap-1">
              {r.scores.map((s, i) => {
                const isMax = s === max && max > 0;
                return (
                  <div key={i} className="flex items-center gap-2">
                    <span className="w-12 text-right font-mono text-muted">#{i}</span>
                    <div className="flex-1 overflow-hidden rounded-full bg-bg-3">
                      <div
                        className="h-2 rounded-full transition-all"
                        style={{
                          width: `${Math.min(100, s * 100)}%`,
                          background: isMax ? "var(--color-ok)" : "var(--color-accent)",
                        }}
                      />
                    </div>
                    <span className="w-12 text-right font-mono tabular-nums text-text">
                      {s.toFixed(2)}
                    </span>
                  </div>
                );
              })}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
