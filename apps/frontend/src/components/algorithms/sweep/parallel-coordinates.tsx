import { EmptyState } from "@/components/ui/empty-state";
import { SweepSnapshot } from "@/lib/types";

interface ParallelCoordinatesProps {
  data: unknown;
}

const WIDTH = 720;
const HEIGHT = 280;
const PAD_X = 44;
const PAD_Y = 28;

export function ParallelCoordinates({ data }: ParallelCoordinatesProps) {
  const parsed = SweepSnapshot.safeParse(data);
  if (!parsed.success || parsed.data.cells.length === 0) {
    return <EmptyState title="no sweep data" description="waiting for cells to complete" />;
  }

  const snap = parsed.data;
  if (snap.axes.length <= 2) {
    return (
      <EmptyState
        title="parallel coordinates unavailable"
        description="use the heatmap for one- and two-axis sweeps"
      />
    );
  }

  const scoreRange = snap.score_range ?? [0, 1];
  const scored = snap.cells.some((cell) => cell.score != null);
  const axisX = (index: number) =>
    PAD_X + (index / Math.max(1, snap.axes.length - 1)) * (WIDTH - PAD_X * 2);

  return (
    <div className="overflow-auto rounded-lg border border-border bg-bg-inset p-2">
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        role="img"
        aria-label="parallel coordinates"
        className="min-w-[640px]"
      >
        {snap.cells.map((cell) => {
          const points = snap.axes
            .map((axis, index) => {
              const valueIndex = axis.values.findIndex(
                (value) => String(value) === String(cell.parameters[axis.name]),
              );
              const y =
                PAD_Y +
                (1 - Math.max(0, valueIndex) / Math.max(1, axis.values.length - 1)) *
                  (HEIGHT - PAD_Y * 2);
              return `${axisX(index)},${y}`;
            })
            .join(" ");
          return (
            <polyline
              key={cell.cell_index}
              points={points}
              fill="none"
              stroke={scored ? colorForScore(cell.score, scoreRange) : "var(--color-muted-2)"}
              strokeOpacity={scored ? 0.72 : 0.35}
              strokeWidth={1.5}
            />
          );
        })}
        {snap.axes.map((axis, index) => {
          const x = axisX(index);
          return (
            <g key={axis.name}>
              <line x1={x} x2={x} y1={PAD_Y} y2={HEIGHT - PAD_Y} stroke="var(--color-border)" />
              <text
                x={x}
                y={16}
                textAnchor="middle"
                fill="var(--color-muted)"
                className="text-[11px] font-medium"
              >
                {axis.name}
              </text>
              {axis.values.map((value, valueIndex) => {
                const y =
                  PAD_Y +
                  (1 - valueIndex / Math.max(1, axis.values.length - 1)) * (HEIGHT - PAD_Y * 2);
                return (
                  <g key={String(value)}>
                    <circle cx={x} cy={y} r={2} fill="var(--color-border-strong)" />
                    <text
                      x={x + 6}
                      y={y + 3}
                      fill="var(--color-muted-2)"
                      className={
                        index === snap.axes.length - 1 ? "hidden text-[9px]" : "text-[9px]"
                      }
                    >
                      {String(value)}
                    </text>
                  </g>
                );
              })}
            </g>
          );
        })}
      </svg>
    </div>
  );
}

function colorForScore(score: number | null, [min, max]: [number, number]): string {
  if (score == null) return "var(--color-muted-2)";
  const t = Math.max(0, Math.min(1, (score - min) / (max - min || 1)));
  if (t > 0.75) return "var(--color-ok)";
  if (t > 0.45) return "var(--color-accent)";
  return "var(--color-warn)";
}
