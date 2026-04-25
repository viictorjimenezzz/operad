import { useStats } from "@/hooks/use-runs";
import { formatCost, formatTokens } from "@/lib/utils";
import { Badge } from "@/shared/ui/badge";
import { useStatsStore } from "@/stores";
import { useStreamStore } from "@/stores/stream";
import { useMemo } from "react";

export function GlobalStatsBar({ subtitle }: { subtitle?: string }) {
  const live = useStatsStore((s) => s.globalStats);
  const { data } = useStats();
  const stats = live ?? data;
  const costTotalsLive = useStatsStore((s) => s.costTotals);
  const costTotalsSeed = data?.cost_totals ?? {};
  const totalCost = useMemo(() => {
    const totals: Record<string, { cost_usd: number }> = { ...costTotalsSeed, ...costTotalsLive };
    return Object.values(totals).reduce((acc, t) => acc + (t?.cost_usd ?? 0), 0);
  }, [costTotalsLive, costTotalsSeed]);

  const status = useStreamStore((s) => s.status);
  const statusVariant = status === "live" ? "live" : status === "error" ? "error" : "default";

  return (
    <header className="flex h-12 items-center gap-5 border-b border-border bg-bg-1 px-4 text-xs">
      <div className="flex min-w-[160px] items-center gap-2">
        <span
          className="h-2.5 w-2.5 rounded-full bg-accent"
          style={{ boxShadow: "0 0 8px var(--color-accent)" }}
        />
        <span className="font-semibold tracking-wide">operad</span>
        {subtitle ? <span className="text-muted">{subtitle}</span> : null}
      </div>
      <div className="flex flex-1 gap-5 overflow-x-auto">
        <Stat label="runs" value={stats?.runs_total} />
        <Stat label="live" value={stats?.runs_running} />
        <Stat label="ended" value={stats?.runs_ended} />
        <Stat
          label="errors"
          value={stats?.runs_error}
          {...(stats?.runs_error ? { variant: "error" as const } : {})}
        />
        <Stat label="events" value={stats?.event_total} />
        <Stat
          label="tokens"
          value={formatTokens((stats?.prompt_tokens ?? 0) + (stats?.completion_tokens ?? 0))}
        />
        <Stat label="cost" value={formatCost(totalCost)} />
      </div>
      <div className="flex items-center gap-2">
        <Badge variant={statusVariant}>{status}</Badge>
      </div>
    </header>
  );
}

function Stat({
  label,
  value,
  variant,
}: {
  label: string;
  value: number | string | undefined;
  variant?: "error";
}) {
  return (
    <div className="flex min-w-[64px] flex-col gap-0.5">
      <span className="text-[0.68rem] uppercase tracking-[0.08em] text-muted">{label}</span>
      <strong
        className="font-semibold tabular-nums"
        style={
          variant === "error" && value && value !== 0 ? { color: "var(--color-err)" } : undefined
        }
      >
        {value ?? "—"}
      </strong>
    </div>
  );
}
