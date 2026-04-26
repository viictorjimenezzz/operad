import { useBenchmarkDelete, useBenchmarkDetail, useBenchmarkTag } from "@/hooks/use-runs";
import type { BenchmarkCell } from "@/lib/types";
import { BenchmarkMatrix } from "@/shared/charts/benchmark-matrix";
import { MethodLeaderboard } from "@/shared/charts/method-leaderboard";
import { Button } from "@/shared/ui/button";
import { EmptyState } from "@/shared/ui/empty-state";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  CartesianGrid,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

interface ScatterPoint {
  task: string;
  method: string;
  seed: number;
  score: number;
  cost: number;
}

export function toScatterPoints(cells: BenchmarkCell[]): ScatterPoint[] {
  return cells.map((cell) => ({
    task: cell.task,
    method: cell.method,
    seed: cell.seed,
    score: cell.score,
    cost: cell.tokens.prompt + cell.tokens.completion,
  }));
}

function fmtTs(ts: number): string {
  return new Date(ts * 1000).toLocaleString();
}

export function BenchmarkDetailPage() {
  const { benchmarkId } = useParams<{ benchmarkId: string }>();
  const navigate = useNavigate();
  const detail = useBenchmarkDetail(benchmarkId);
  const tag = useBenchmarkTag();
  const del = useBenchmarkDelete();
  const [tagText, setTagText] = useState("");

  if (!benchmarkId) return <EmptyState title="missing benchmark id" />;
  if (detail.isLoading) return <div className="p-6 text-xs text-muted">loading benchmark…</div>;
  if (detail.error || !detail.data) return <EmptyState title="benchmark not found" />;

  const data = detail.data;
  const points = toScatterPoints(data.report.cells);

  return (
    <div className="h-full overflow-auto p-4">
      <div className="mb-3 flex items-center gap-3 border-b border-border pb-2 text-xs">
        <Link to="/benchmarks" className="text-muted hover:text-text">
          ← benchmarks
        </Link>
        <span className="font-mono text-text">{data.name}</span>
        {data.tag ? (
          <span className="rounded bg-bg-3 px-1.5 py-0.5 text-[10px] uppercase tracking-[0.08em] text-warn">
            {data.tag}
          </span>
        ) : null}
        <span className="ml-auto text-muted">{fmtTs(data.created_at)}</span>
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <input
          value={tagText}
          onChange={(e) => setTagText(e.target.value)}
          placeholder="baseline-v1"
          className="rounded border border-border bg-bg-2 px-2 py-1 text-xs text-text outline-none"
        />
        <Button
          variant="primary"
          size="sm"
          onClick={() => {
            const next = tagText.trim();
            if (!next) return;
            tag.mutate({ benchmarkId, tag: next });
            setTagText("");
          }}
          disabled={tag.isPending}
        >
          tag
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={() =>
            del.mutate(benchmarkId, {
              onSuccess: () => navigate("/benchmarks"),
            })
          }
          disabled={del.isPending}
        >
          delete
        </Button>
        <span className="text-[11px] text-muted">
          {data.n_tasks} tasks · {data.n_methods} methods · {points.length} points
        </span>
      </div>

      {data.baseline ? (
        <div className="mb-3 rounded border border-border bg-bg-1 px-3 py-2 text-[11px] text-muted">
          baseline: <span className="font-mono text-text">{data.baseline.name}</span>
          {data.baseline.tag ? ` (${data.baseline.tag})` : ""}
        </div>
      ) : null}

      <div className="mb-4 rounded border border-border bg-bg-1 p-3">
        <div className="mb-2 text-xs uppercase tracking-[0.08em] text-muted">method × task matrix</div>
        <BenchmarkMatrix summary={data.report.summary} delta={data.delta} />
      </div>

      <div className="mb-4 rounded border border-border bg-bg-1 p-3">
        <div className="mb-2 text-xs uppercase tracking-[0.08em] text-muted">
          cost vs metric scatter ({points.length} points)
        </div>
        <ResponsiveContainer width="100%" height={260}>
          <ScatterChart margin={{ top: 12, right: 16, bottom: 8, left: 0 }}>
            <CartesianGrid stroke="var(--color-border)" strokeDasharray="3 3" />
            <XAxis
              dataKey="cost"
              stroke="var(--color-muted)"
              tick={{ fontSize: 11 }}
              type="number"
              name="tokens"
            />
            <YAxis
              dataKey="score"
              stroke="var(--color-muted)"
              tick={{ fontSize: 11 }}
              type="number"
              name="score"
            />
            <Tooltip
              contentStyle={{
                background: "var(--color-bg-2)",
                border: "1px solid var(--color-border)",
                fontSize: 11,
              }}
              formatter={(value: number, name: string) =>
                name === "score" ? value.toFixed(3) : Math.round(value).toString()
              }
              labelFormatter={(_, payload) => {
                const point = payload?.[0]?.payload as ScatterPoint | undefined;
                if (!point) return "";
                return `${point.task} / ${point.method} / seed=${point.seed}`;
              }}
            />
            <Scatter data={points} fill="var(--color-accent)" />
          </ScatterChart>
        </ResponsiveContainer>
      </div>

      <div className="rounded border border-border bg-bg-1 p-3">
        <div className="mb-2 text-xs uppercase tracking-[0.08em] text-muted">per-task leaderboard</div>
        <MethodLeaderboard summary={data.report.summary} />
      </div>
    </div>
  );
}
