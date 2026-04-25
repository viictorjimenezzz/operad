import { MutationsMatrix } from "@/lib/types";
import { EmptyState } from "@/shared/ui/empty-state";

export function OpSuccessTable({ data }: { data: unknown }) {
  const parsed = MutationsMatrix.safeParse(data);
  if (!parsed.success || parsed.data.ops.length === 0) {
    return <EmptyState title="no op stats yet" />;
  }
  const { ops, success, attempts } = parsed.data;
  const rows = ops.map((op, i) => {
    const totalAttempts = attempts[i]?.reduce((a, b) => a + b, 0) ?? 0;
    const totalSuccess = success[i]?.reduce((a, b) => a + b, 0) ?? 0;
    const rate = totalAttempts > 0 ? totalSuccess / totalAttempts : 0;
    return { op, attempts: totalAttempts, success: totalSuccess, rate };
  });
  rows.sort((a, b) => b.rate - a.rate || b.attempts - a.attempts);

  return (
    <table className="w-full border-collapse text-[11px]">
      <thead>
        <tr className="border-b border-border text-muted">
          <th className="px-2 py-1 text-left font-medium">op</th>
          <th className="px-2 py-1 text-right font-medium">attempts</th>
          <th className="px-2 py-1 text-right font-medium">success</th>
          <th className="px-2 py-1 text-right font-medium">rate</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.op} className="border-b border-border/60">
            <td className="px-2 py-1 font-mono text-text">{r.op}</td>
            <td className="px-2 py-1 text-right tabular-nums">{r.attempts}</td>
            <td className="px-2 py-1 text-right tabular-nums">{r.success}</td>
            <td
              className="px-2 py-1 text-right font-medium tabular-nums"
              style={{ color: r.rate > 0 ? "var(--color-ok)" : "var(--color-muted)" }}
            >
              {(r.rate * 100).toFixed(0)}%
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
