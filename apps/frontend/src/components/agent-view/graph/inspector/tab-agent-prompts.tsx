import { Eyebrow, HashTag } from "@/components/ui";
import { dashboardApi } from "@/lib/api/dashboard";
import { formatRelativeTime } from "@/lib/utils";
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";

export function TabAgentPrompts({ runId, agentPath }: { runId: string; agentPath: string }) {
  const query = useQuery({
    queryKey: ["agent-prompts", runId, agentPath] as const,
    queryFn: () => dashboardApi.agentPrompts(runId, agentPath),
    staleTime: 30_000,
    retry: false,
  });
  const [activeIdx, setActiveIdx] = useState(0);

  const grouped = useMemo(() => {
    const entries = query.data?.entries ?? [];
    // Group consecutive runs of identical hash_prompt — drift events boundary.
    const out: Array<{
      hash: string | null;
      first: (typeof entries)[number];
      count: number;
    }> = [];
    for (const e of entries) {
      const last = out[out.length - 1];
      if (last && last.hash === e.hash_prompt) {
        last.count += 1;
      } else {
        out.push({ hash: e.hash_prompt, first: e, count: 1 });
      }
    }
    return out;
  }, [query.data]);

  if (query.isLoading) {
    return <div className="p-5 text-[12px] text-muted-2">loading prompts…</div>;
  }
  if (query.error) {
    return <div className="p-5 text-[12px] text-[--color-err]">failed to load prompts</div>;
  }
  if (grouped.length === 0) {
    return <div className="p-5 text-[12px] text-muted-2">no prompts captured</div>;
  }

  const active = grouped[activeIdx];
  if (!active) return null;

  return (
    <div className="grid h-full grid-cols-[180px_1fr] divide-x divide-border">
      <aside className="overflow-auto py-3">
        {grouped.map((g, i) => (
          <button
            key={i}
            type="button"
            onClick={() => setActiveIdx(i)}
            className={`flex w-full flex-col items-start gap-1 border-l-2 px-3 py-2 text-left text-[12px] ${
              activeIdx === i ? "border-l-accent bg-bg-2" : "border-l-transparent hover:bg-bg-2"
            }`}
          >
            <HashTag hash={g.hash} size="sm" mono />
            <span className="text-[10px] text-muted-2">
              {formatRelativeTime(g.first.started_at)} · {g.count}×
            </span>
          </button>
        ))}
      </aside>
      <div className="overflow-auto p-4">
        <div className="mb-3 flex items-center gap-2">
          <Eyebrow>system</Eyebrow>
          <span className="text-[11px] text-muted-2">
            renderer · {query.data?.renderer ?? "xml"}
          </span>
        </div>
        <pre className="mb-4 whitespace-pre-wrap rounded-lg bg-bg-inset p-3 font-mono text-[11px] leading-5">
          {active.first.system ?? "—"}
        </pre>
        <Eyebrow>user</Eyebrow>
        <pre className="mt-2 whitespace-pre-wrap rounded-lg bg-bg-inset p-3 font-mono text-[11px] leading-5">
          {active.first.user ?? "—"}
        </pre>
      </div>
    </div>
  );
}
