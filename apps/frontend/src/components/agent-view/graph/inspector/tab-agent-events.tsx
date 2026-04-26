import { Eyebrow, HashTag, Pill } from "@/components/ui";
import { useAgentEvents } from "@/hooks/use-runs";
import type { AgentEventEnvelope } from "@/lib/types";
import { formatRelativeTime } from "@/lib/utils";

export function TabAgentEvents({ runId, agentPath }: { runId: string; agentPath: string }) {
  const query = useAgentEvents(runId, agentPath);

  if (query.isLoading) {
    return <div className="p-5 text-[12px] text-muted-2">loading events…</div>;
  }
  const events = (query.data?.events ?? []).filter(
    (e): e is AgentEventEnvelope => e.type === "agent_event",
  );
  if (events.length === 0) {
    return <div className="p-5 text-[12px] text-muted-2">no events recorded</div>;
  }

  return (
    <div className="space-y-1.5 p-5">
      <Eyebrow>{events.length} events</Eyebrow>
      <ol className="mt-2 space-y-1">
        {events.map((e, i) => {
          const tone =
            e.kind === "error"
              ? "error"
              : e.kind === "start"
                ? "live"
                : e.kind === "end"
                  ? "ok"
                  : "default";
          const invocationId = e.metadata?.invocation_id;
          return (
            <li
              key={i}
              className="flex items-start gap-3 rounded-lg border border-border bg-bg-2 px-3 py-2"
            >
              <Pill tone={tone} size="sm">
                {e.kind}
              </Pill>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-baseline gap-2 text-[11px]">
                  <span className="text-muted">{formatRelativeTime(e.started_at)}</span>
                  {typeof invocationId === "string" ? (
                    <HashTag hash={invocationId} size="sm" mono />
                  ) : null}
                </div>
                {e.error ? (
                  <div className="mt-1 font-mono text-[11px] text-[--color-err]">
                    {e.error.type}: {e.error.message}
                  </div>
                ) : null}
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
