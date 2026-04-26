import { Pill, Section } from "@/components/ui";
import { dashboardApi } from "@/lib/api/dashboard";
import { RunSummary } from "@/lib/types";
import { useQuery } from "@tanstack/react-query";
import { Flame } from "lucide-react";

export interface TrainableParamsBlockProps {
  dataSummary?: unknown;
  summary?: unknown;
  runId?: string;
}

function valuePreview(value: unknown): string {
  if (typeof value === "string") {
    return value.length > 80 ? `${value.slice(0, 80)}…` : value;
  }
  if (Array.isArray(value)) return `[${value.length}]`;
  if (value && typeof value === "object") return `{${Object.keys(value).length}}`;
  if (value == null) return "—";
  return String(value);
}

export function TrainableParamsBlock(props: TrainableParamsBlockProps) {
  const parsed = RunSummary.safeParse(props.dataSummary ?? props.summary);
  const summary = parsed.success ? parsed.data : null;

  const paramsQuery = useQuery({
    queryKey: ["run", "agent-parameters", props.runId, summary?.root_agent_path] as const,
    queryFn: () => dashboardApi.agentParameters(props.runId ?? "", summary?.root_agent_path ?? ""),
    enabled: !!props.runId && !!summary?.root_agent_path,
    retry: false,
    staleTime: 30_000,
  });

  const params = paramsQuery.data?.parameters ?? [];
  const trainable = params.filter((p) => p.requires_grad);
  const summaryText = paramsQuery.isLoading
    ? "loading parameters…"
    : trainable.length === 0
      ? "no parameters marked trainable"
      : `${trainable.length} trainable parameter${trainable.length === 1 ? "" : "s"}`;

  const disabled = trainable.length === 0;

  return (
    <Section title="Trainable parameters" summary={summaryText} disabled={disabled}>
      <ul className="grid gap-2">
        {trainable.map((p) => (
          <li
            key={p.path}
            className="flex items-center gap-3 rounded-lg border border-[--color-warn-dim] bg-[--color-warn-dim]/30 px-3 py-2"
          >
            <Flame size={14} className="flex-shrink-0 text-[--color-warn]" />
            <div className="min-w-0 flex-1">
              <div className="font-mono text-[12px] text-text">{p.path}</div>
              <div className="text-[11px] text-muted-2">
                {p.type} · {valuePreview(p.value)}
              </div>
            </div>
            {p.grad && p.grad.severity > 0 ? (
              <Pill tone="warn" size="sm">
                grad {p.grad.severity.toFixed(1)}
              </Pill>
            ) : null}
          </li>
        ))}
      </ul>
    </Section>
  );
}
