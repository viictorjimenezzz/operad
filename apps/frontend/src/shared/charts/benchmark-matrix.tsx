import type { BenchmarkDeltaRow, BenchmarkSummaryRow } from "@/lib/types";
import { EmptyState } from "@/shared/ui/empty-state";

interface BenchmarkMatrixProps {
  summary: BenchmarkSummaryRow[];
  delta?: BenchmarkDeltaRow[];
}

function fmtDelta(n: number): string {
  if (n > 0) return `+${n.toFixed(3)}`;
  return n.toFixed(3);
}

export function BenchmarkMatrix({ summary, delta = [] }: BenchmarkMatrixProps) {
  if (!summary.length) return <EmptyState title="no benchmark summary" />;

  const tasks = [...new Set(summary.map((r) => r.task))].sort();
  const methods = [...new Set(summary.map((r) => r.method))].sort();

  const valueMap = new Map(summary.map((r) => [`${r.task}::${r.method}`, r]));
  const deltaMap = new Map(delta.map((r) => [`${r.task}::${r.method}`, r.delta]));

  return (
    <table className="w-full border-collapse text-[11px]">
      <thead>
        <tr className="border-b border-border text-muted">
          <th className="px-2 py-1 text-left font-medium">method</th>
          {tasks.map((task) => (
            <th key={task} className="px-2 py-1 text-right font-medium">
              {task}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {methods.map((method) => (
          <tr key={method} className="border-b border-border/60 align-top">
            <td className="px-2 py-1 font-mono text-text">{method}</td>
            {tasks.map((task) => {
              const key = `${task}::${method}`;
              const row = valueMap.get(key);
              const d = deltaMap.get(key);
              return (
                <td key={key} className="px-2 py-1 text-right tabular-nums">
                  {row ? `${row.mean.toFixed(3)}±${row.std.toFixed(3)}` : "-"}
                  {d !== undefined ? (
                    <div
                      className="text-[10px]"
                      style={{ color: d >= 0 ? "var(--color-ok)" : "var(--color-err)" }}
                    >
                      Δ {fmtDelta(d)}
                    </div>
                  ) : null}
                </td>
              );
            })}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
