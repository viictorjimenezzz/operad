import { SweepSnapshot } from "@/lib/types";
import { EmptyState } from "@/shared/ui/empty-state";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export function SweepHeatmap({ data }: { data: unknown }) {
  const parsed = SweepSnapshot.safeParse(data);
  if (!parsed.success || parsed.data.cells.length === 0) {
    return <EmptyState title="no sweep data" description="waiting for cells to complete" />;
  }
  const snap = parsed.data;
  const dims = snap.axes.length;

  if (dims > 5) {
    return (
      <EmptyState
        title="too many dimensions"
        description="view as table in the Cells tab"
      />
    );
  }
  if (dims <= 1) {
    return <_BarView snap={snap} />;
  }
  if (dims === 2) {
    return <_MatrixView snap={snap} />;
  }
  // 3-d+: small multiples sliced by axis[2]
  return <_SmallMultiples snap={snap} />;
}

// ---------------------------------------------------------------------------
// 1-d: bar chart
// ---------------------------------------------------------------------------

function _BarView({ snap }: { snap: SweepSnapshot }) {
  const axisName = snap.axes[0]?.name ?? "cell";
  const bars = snap.cells.map((c) => ({
    label: String(c.parameters[axisName] ?? c.cell_index),
    score: c.score,
  }));
  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={bars} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
        <XAxis dataKey="label" tick={{ fontSize: 11 }} />
        <YAxis tick={{ fontSize: 11 }} />
        <Tooltip />
        <Bar dataKey="score" fill="rgba(70, 167, 255, 0.7)" radius={[2, 2, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

// ---------------------------------------------------------------------------
// 2-d: matrix grid
// ---------------------------------------------------------------------------

function _MatrixView({ snap }: { snap: SweepSnapshot }) {
  const ax0 = snap.axes[0]!;
  const ax1 = snap.axes[1]!;
  const [scoreMin, scoreMax] = snap.score_range ?? [0, 1];
  const range = scoreMax - scoreMin || 1;

  // Index cells by (ax0_val, ax1_val)
  const cellMap = new Map<string, { score: number | null; idx: number }>();
  for (const c of snap.cells) {
    const key = `${c.parameters[ax0.name]}||${c.parameters[ax1.name]}`;
    cellMap.set(key, { score: c.score, idx: c.cell_index });
  }

  return (
    <div className="overflow-auto">
      <table className="border-collapse text-[11px]">
        <thead>
          <tr>
            <th className="sticky left-0 bg-bg-1 px-2 py-1 text-left font-medium text-muted">
              {ax0.name} \ {ax1.name}
            </th>
            {ax1.values.map((v) => (
              <th key={String(v)} className="px-2 py-1 text-right font-medium text-muted">
                {String(v)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {ax0.values.map((v0) => (
            <tr key={String(v0)}>
              <td className="sticky left-0 bg-bg-1 px-2 py-1 font-mono text-text">
                {String(v0)}
              </td>
              {ax1.values.map((v1) => {
                const entry = cellMap.get(`${v0}||${v1}`);
                const score = entry?.score ?? null;
                const alpha =
                  score !== null ? 0.08 + ((score - scoreMin) / range) * 0.62 : 0;
                const bg = score !== null ? `rgba(70, 167, 255, ${alpha})` : "transparent";
                return (
                  <td
                    key={String(v1)}
                    className="px-2 py-1 text-right font-mono tabular-nums"
                    style={{ background: bg }}
                    title={score !== null ? `score: ${score}` : "no score"}
                  >
                    {score !== null ? score.toFixed(3) : "—"}
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

// ---------------------------------------------------------------------------
// 3-d+: small multiples sliced by axis[2]
// ---------------------------------------------------------------------------

function _SmallMultiples({ snap }: { snap: SweepSnapshot }) {
  const ax2 = snap.axes[2]!;
  const slices = ax2.values.map((v2) => ({
    label: `${ax2.name} = ${v2}`,
    subSnap: {
      ...snap,
      axes: snap.axes.slice(0, 2),
      cells: snap.cells.filter((c) => String(c.parameters[ax2.name]) === String(v2)),
    } as SweepSnapshot,
  }));

  return (
    <div className="flex flex-col gap-6">
      {slices.map(({ label, subSnap }) => (
        <div key={label}>
          <p className="mb-1 text-[11px] font-medium text-muted">{label}</p>
          <_MatrixView snap={subSnap} />
        </div>
      ))}
    </div>
  );
}
