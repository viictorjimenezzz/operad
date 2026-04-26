import { cn } from "@/lib/utils";

interface ValueDistributionProps {
  name: string;
  values: unknown[];
  className?: string;
}

function isNumeric(values: unknown[]): values is number[] {
  return values.length > 0 && values.every((v) => typeof v === "number" && Number.isFinite(v));
}

function histogram(values: number[], bins = 8): number[] {
  const min = Math.min(...values);
  const max = Math.max(...values);
  if (min === max) return [values.length];
  const width = (max - min) / bins;
  const out = Array.from({ length: bins }, () => 0);
  for (const v of values) {
    const idx = Math.min(bins - 1, Math.floor((v - min) / width));
    out[idx] = (out[idx] ?? 0) + 1;
  }
  return out;
}

export function ValueDistribution({ name, values, className }: ValueDistributionProps) {
  const usable = values.filter((v) => v != null).slice(-80);
  if (usable.length === 0) {
    return (
      <div className={cn("rounded border border-border bg-bg-2 px-2 py-1.5", className)}>
        <div className="text-[11px] text-muted">{name}</div>
        <div className="text-[11px] text-muted-2">no recent values</div>
      </div>
    );
  }

  if (isNumeric(usable)) {
    const bins = histogram(usable);
    const top = Math.max(...bins);
    return (
      <div className={cn("rounded border border-border bg-bg-2 px-2 py-1.5", className)}>
        <div className="mb-1 text-[11px] text-muted">{name}</div>
        <div className="flex h-8 items-end gap-0.5">
          {bins.map((v, i) => (
            <div
              key={`${name}:${i}`}
              className="flex-1 rounded-sm bg-accent-dim"
              style={{ height: `${(v / Math.max(1, top)) * 100}%` }}
            />
          ))}
        </div>
      </div>
    );
  }

  const counts = new Map<string, number>();
  for (const raw of usable) {
    const key = typeof raw === "string" ? raw : JSON.stringify(raw);
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  const top = [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 5);
  const max = top[0]?.[1] ?? 1;

  return (
    <div className={cn("rounded border border-border bg-bg-2 px-2 py-1.5", className)}>
      <div className="mb-1 text-[11px] text-muted">{name}</div>
      <div className="space-y-1">
        {top.map(([k, v]) => (
          <div key={`${name}:${k}`} className="flex items-center gap-1">
            <span className="max-w-[120px] truncate text-[10px] text-text" title={k}>
              {k}
            </span>
            <div className="h-1.5 flex-1 rounded bg-bg-3">
              <div className="h-full rounded bg-accent" style={{ width: `${(v / max) * 100}%` }} />
            </div>
            <span className="text-[10px] text-muted">{v}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
