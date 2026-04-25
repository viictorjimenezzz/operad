import type { EventEnvelope } from "@/lib/types";
import { Envelope } from "@/lib/types";
import { Badge } from "@/shared/ui/badge";
import { Chip } from "@/shared/ui/chip";
import { EmptyState } from "@/shared/ui/empty-state";
import { JsonView } from "@/shared/ui/json-view";
import { useMemo, useState } from "react";
import { z } from "zod";

const EventArray = z.array(Envelope);

interface EventTimelineProps {
  data: unknown;
  kindFilter?: string;
}

type KindFilter = "all" | "agent" | "algo" | "error";

export function EventTimeline({ data }: EventTimelineProps) {
  const parsed = EventArray.safeParse(data);
  const events = useMemo(
    () =>
      parsed.success
        ? (parsed.data.filter(
            (e) => e.type === "agent_event" || e.type === "algo_event",
          ) as EventEnvelope[])
        : [],
    [parsed],
  );
  const [filter, setFilter] = useState<KindFilter>("all");
  const [search, setSearch] = useState("");
  const [selectedIdx, setSelectedIdx] = useState<number>(-1);

  const filtered = useMemo(() => {
    return events.filter((env) => {
      if (filter === "agent" && env.type !== "agent_event") return false;
      if (filter === "algo" && env.type !== "algo_event") return false;
      if (filter === "error") {
        if (env.type === "agent_event") return env.kind === "error";
        if (env.type === "algo_event") return env.kind === "algo_error";
        return false;
      }
      if (search) {
        const s = search.toLowerCase();
        const path = env.type === "agent_event" ? env.agent_path : env.algorithm_path;
        if (!path.toLowerCase().includes(s) && !env.kind.toLowerCase().includes(s)) {
          return false;
        }
      }
      return true;
    });
  }, [events, filter, search]);

  if (events.length === 0) {
    return <EmptyState title="no events" description="run hasn't emitted any events yet" />;
  }

  const selected = selectedIdx >= 0 && selectedIdx < filtered.length ? filtered[selectedIdx] : null;

  return (
    <div className="grid h-full grid-cols-1 gap-3 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
      <div className="flex h-full flex-col overflow-hidden rounded-md border border-border bg-bg-1">
        <div className="flex items-center gap-2 border-b border-border px-2 py-1.5">
          <Chip active={filter === "all"} onClick={() => setFilter("all")}>
            all
          </Chip>
          <Chip active={filter === "agent"} onClick={() => setFilter("agent")}>
            agent
          </Chip>
          <Chip active={filter === "algo"} onClick={() => setFilter("algo")}>
            algo
          </Chip>
          <Chip active={filter === "error"} onClick={() => setFilter("error")}>
            error
          </Chip>
          <input
            type="text"
            placeholder="filter…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="ml-auto rounded border border-border bg-bg-2 px-2 py-1 text-[11px] focus:border-accent focus:outline-none"
          />
        </div>
        <ul className="flex-1 overflow-auto">
          {filtered.map((env, idx) => {
            const isAgent = env.type === "agent_event";
            const path = isAgent ? env.agent_path : env.algorithm_path;
            const kind = env.kind;
            const isError = (isAgent && kind === "error") || kind === "algo_error";
            return (
              <li key={`${env.run_id}-${idx}-${env.started_at}`}>
                <button
                  type="button"
                  onClick={() => setSelectedIdx(idx)}
                  className={`flex w-full items-center gap-2 border-b border-border/60 px-2 py-1.5 text-left text-[11px] transition-colors hover:bg-bg-2 ${
                    selectedIdx === idx ? "bg-bg-2" : ""
                  }`}
                >
                  <span className="font-mono tabular-nums text-muted" style={{ minWidth: 60 }}>
                    {env.started_at.toFixed(3).slice(-7)}
                  </span>
                  <Badge variant={isError ? "error" : isAgent ? "default" : "algo"}>{kind}</Badge>
                  <span className="truncate font-mono text-text">{path}</span>
                </button>
              </li>
            );
          })}
        </ul>
      </div>
      <div className="overflow-auto rounded-md border border-border bg-bg-1 p-3">
        {selected ? (
          <div className="flex flex-col gap-2 text-xs">
            <div className="flex items-center gap-2">
              <Badge variant={selected.type === "algo_event" ? "algo" : "default"}>
                {selected.type}
              </Badge>
              <span className="font-mono text-muted">{selected.kind}</span>
              <span className="ml-auto font-mono text-muted-2">
                {(selected.finished_at ?? selected.started_at) - selected.started_at >= 0
                  ? `${(((selected.finished_at ?? selected.started_at) - selected.started_at) * 1000).toFixed(1)}ms`
                  : ""}
              </span>
            </div>
            <div className="font-mono text-text">
              {selected.type === "agent_event" ? selected.agent_path : selected.algorithm_path}
            </div>
            {selected.type === "agent_event" && selected.input != null && (
              <Section label="input">
                <JsonView value={selected.input} />
              </Section>
            )}
            {selected.type === "agent_event" && selected.output != null && (
              <Section label="output">
                <JsonView value={selected.output} />
              </Section>
            )}
            {selected.type === "algo_event" && (
              <Section label="payload">
                <JsonView value={selected.payload} />
              </Section>
            )}
            {selected.type === "agent_event" && selected.error != null && (
              <Section label="error">
                <pre className="rounded-md border border-err/50 bg-err-dim/40 p-2 text-[11px] text-[#ffc0c8]">
                  {selected.error.type}: {selected.error.message}
                </pre>
              </Section>
            )}
          </div>
        ) : (
          <EmptyState title="select an event" description="click a row on the left" />
        )}
      </div>
    </div>
  );
}

function Section({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-[0.68rem] uppercase tracking-[0.08em] text-muted">{label}</span>
      {children}
    </div>
  );
}
