import type { BenchmarkSummaryRow } from "@/lib/types";
import { EmptyState } from "@/shared/ui/empty-state";

interface MethodLeaderboardProps {
  summary: BenchmarkSummaryRow[];
}

export function MethodLeaderboard({ summary }: MethodLeaderboardProps) {
  if (!summary.length) return <EmptyState title="no benchmark summary" />;

  const tasks = [...new Set(summary.map((r) => r.task))].sort();

  return (
    <div className="space-y-4">
      {tasks.map((task) => {
        const rows = summary.filter((r) => r.task === task).sort((a, b) => b.mean - a.mean);
        return (
          <div key={task}>
            <div className="mb-1 text-xs font-medium uppercase tracking-[0.08em] text-muted">{task}</div>
            <table className="w-full border-collapse text-[11px]">
              <thead>
                <tr className="border-b border-border text-muted">
                  <th className="px-2 py-1 text-left font-medium">method</th>
                  <th className="px-2 py-1 text-right font-medium">mean</th>
                  <th className="px-2 py-1 text-right font-medium">std</th>
                  <th className="px-2 py-1 text-right font-medium">tokens</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row, idx) => (
                  <tr
                    key={`${task}:${row.method}`}
                    className="border-b border-border/60"
                    style={idx === 0 ? { background: "var(--color-ok-dim)" } : undefined}
                  >
                    <td className="px-2 py-1 font-mono text-text">{row.method}</td>
                    <td className="px-2 py-1 text-right tabular-nums">{row.mean.toFixed(3)}</td>
                    <td className="px-2 py-1 text-right tabular-nums">{row.std.toFixed(3)}</td>
                    <td className="px-2 py-1 text-right tabular-nums">{row.tokens_mean}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      })}
    </div>
  );
}
