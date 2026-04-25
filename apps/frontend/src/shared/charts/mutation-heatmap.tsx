import { MutationsMatrix } from "@/lib/types";
import { EmptyState } from "@/shared/ui/empty-state";

export function MutationHeatmap({ data }: { data: unknown }) {
  const parsed = MutationsMatrix.safeParse(data);
  if (!parsed.success || parsed.data.gens.length === 0) {
    return <EmptyState title="no mutation data" description="op_attempt_counts not present yet" />;
  }
  const { gens, ops, success, attempts } = parsed.data;

  return (
    <div className="overflow-auto">
      <table className="border-collapse text-[11px]">
        <thead>
          <tr>
            <th className="sticky left-0 bg-bg-1 px-2 py-1 text-left font-medium text-muted">op</th>
            {gens.map((g) => (
              <th key={g} className="px-2 py-1 text-right font-medium text-muted">
                gen {g}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {ops.map((op, i) => (
            <tr key={op}>
              <td className="sticky left-0 bg-bg-1 px-2 py-1 font-mono text-text">{op}</td>
              {gens.map((g, j) => {
                const a = attempts[i]?.[j] ?? 0;
                const s = success[i]?.[j] ?? 0;
                const rate = a > 0 ? s / a : 0;
                const bg = `rgba(70, 167, 255, ${0.08 + rate * 0.62})`;
                return (
                  <td
                    key={`${op}-${g}`}
                    className="px-2 py-1 text-right font-mono"
                    style={{ background: a > 0 ? bg : "transparent" }}
                    title={`${s}/${a} successful`}
                  >
                    <span className="tabular-nums">{a > 0 ? `${s}/${a}` : "—"}</span>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
