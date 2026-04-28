import { EmptyState } from "@/components/ui";
import { paletteIndex } from "@/lib/hash-color";
import { cn, truncateMiddle } from "@/lib/utils";
import type { ParameterEvolutionPoint } from "./float-evolution";

export interface CategoricalEvolutionProps {
  path: string;
  points: ParameterEvolutionPoint[];
  selectedStep?: number | undefined;
  onSelectStep?: ((step: number) => void) | undefined;
  compact?: boolean | undefined;
}

const WIDTH = 640;
const HEIGHT = 150;
const PAD = { top: 22, right: 22, bottom: 26, left: 22 };

export function CategoricalEvolution({
  path,
  points,
  selectedStep,
  onSelectStep,
  compact,
}: CategoricalEvolutionProps) {
  if (points.length === 0) {
    return (
      <EmptyState
        title="no categorical parameter history"
        description="this parameter has no recorded value changes yet"
      />
    );
  }

  const nodes = distinctNodes(points);
  const edges = transitions(points);
  const innerW = WIDTH - PAD.left - PAD.right;
  const innerH = HEIGHT - PAD.top - PAD.bottom;
  const maxStep = Math.max(points.length - 1, 1);
  const xFor = (step: number) => PAD.left + (step / maxStep) * innerW;
  const yFor = (index: number) =>
    nodes.length === 1 ? HEIGHT / 2 : PAD.top + (index / Math.max(nodes.length - 1, 1)) * innerH;

  return (
    <div className="space-y-2" data-testid="categorical-evolution">
      <div className="overflow-hidden rounded-md border border-border bg-bg-1">
        <svg
          width="100%"
          height={compact ? 116 : HEIGHT}
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          preserveAspectRatio="none"
          role="img"
          aria-label={`${path} state diagram`}
        >
          <title>{path} state diagram</title>
          {edges.map((edge) => {
            const source = nodes.find((node) => node.label === edge.from);
            const target = nodes.find((node) => node.label === edge.to);
            if (!source || !target) return null;
            const x1 = xFor(source.firstStep) + 62;
            const x2 = xFor(target.firstStep) - 62;
            const y1 = yFor(source.index);
            const y2 = yFor(target.index);
            const labelX = (x1 + x2) / 2;
            const labelY = (y1 + y2) / 2 - 4;
            return (
              <g key={`${edge.from}->${edge.to}`} data-testid="category-edge">
                <line
                  x1={x1}
                  y1={y1}
                  x2={Math.max(x2, x1 + 20)}
                  y2={y2}
                  stroke="var(--color-border-strong)"
                  strokeWidth={Math.max(1, Math.min(edge.count, 4))}
                  markerEnd="url(#category-arrow)"
                />
                <text
                  x={labelX}
                  y={labelY}
                  textAnchor="middle"
                  fontSize={10}
                  fill="var(--color-muted-2)"
                >
                  x{edge.count}
                </text>
              </g>
            );
          })}
          <defs>
            <marker
              id="category-arrow"
              markerWidth="7"
              markerHeight="7"
              refX="6"
              refY="3.5"
              orient="auto"
            >
              <path d="M 0 0 L 7 3.5 L 0 7 z" fill="var(--color-border-strong)" />
            </marker>
          </defs>
          {nodes.map((node) => (
            <g
              key={node.label}
              data-testid="category-node"
              transform={`translate(${xFor(node.firstStep) - 58} ${yFor(node.index) - 14})`}
            >
              <rect
                width={116}
                height={28}
                rx={5}
                fill={nodeColor(node.label)}
                opacity={0.18}
                stroke={nodeColor(node.label)}
              />
              <circle cx={10} cy={14} r={3} fill={nodeColor(node.label)} />
              <text x={18} y={18} fontSize={11} fill="var(--color-text)">
                {truncateMiddle(node.label, 20)}
              </text>
            </g>
          ))}
        </svg>
      </div>
      <div className="divide-y divide-border border-y border-border">
        {points.map((point, index) => {
          const label = stringifyValue(point.value);
          const previous = index > 0 ? stringifyValue(points[index - 1]?.value) : null;
          const changed = previous != null && previous !== label;
          return (
            <div
              key={`${point.runId}-${index}`}
              className={cn(
                "flex min-h-[var(--row-h)] w-full items-center gap-2 px-2 text-[12px] hover:bg-bg-2/60",
                selectedStep === index && "bg-bg-2",
              )}
            >
              <button
                type="button"
                onClick={() => onSelectStep?.(index)}
                className="flex min-h-[var(--row-h)] min-w-0 flex-1 items-center gap-2 text-left"
              >
                <span className="w-12 shrink-0 font-mono text-[11px] text-muted-2">step {index}</span>
                <span
                  aria-hidden
                  className="h-2 w-2 shrink-0 rounded-full"
                  style={{ background: nodeColor(label) }}
                />
                <span className="min-w-0 flex-1 truncate font-mono text-text">{label}</span>
                {changed ? (
                  <span className="truncate text-[11px] text-muted-2">
                    changed from {truncateMiddle(previous, 24)}
                  </span>
                ) : null}
              </button>
              {point.langfuseUrl ? (
                <a
                  href={point.langfuseUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  title="Open trace in Langfuse"
                  className="shrink-0 text-[11px] text-accent hover:underline"
                >
                  langfuse -&gt;
                </a>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function distinctNodes(points: ParameterEvolutionPoint[]) {
  const seen = new Map<string, { label: string; firstStep: number; index: number }>();
  points.forEach((point, step) => {
    const label = stringifyValue(point.value);
    if (!seen.has(label)) seen.set(label, { label, firstStep: step, index: seen.size });
  });
  return [...seen.values()];
}

function transitions(points: ParameterEvolutionPoint[]) {
  const counts = new Map<string, { from: string; to: string; count: number }>();
  for (let index = 1; index < points.length; index += 1) {
    const from = stringifyValue(points[index - 1]?.value);
    const to = stringifyValue(points[index]?.value);
    if (from === to) continue;
    const key = `${from}\0${to}`;
    const current = counts.get(key) ?? { from, to, count: 0 };
    current.count += 1;
    counts.set(key, current);
  }
  return [...counts.values()];
}

function stringifyValue(value: unknown): string {
  if (value === null) return "null";
  if (value === undefined) return "undefined";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return JSON.stringify(value);
}

function nodeColor(label: string): string {
  const index = paletteIndex(label);
  return `var(--qual-${index >= 0 ? index + 1 : 7})`;
}
