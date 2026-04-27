import { KeyValueGrid, Metric, PanelCard } from "@/components/ui";
import { useAgentMeta } from "@/hooks/use-runs";
import { RunInvocationsResponse, RunSummary } from "@/lib/types";

export interface BackendBlockProps {
  dataSummary?: unknown;
  dataInvocations?: unknown;
  summary?: unknown;
  invocations?: unknown;
  runId?: string;
}

export function BackendBlock(props: BackendBlockProps) {
  const summaryParsed = RunSummary.safeParse(props.dataSummary ?? props.summary);
  const summary = summaryParsed.success ? summaryParsed.data : null;
  const invocationsParsed = RunInvocationsResponse.safeParse(
    props.dataInvocations ?? props.invocations,
  );
  const invocations = invocationsParsed.success ? invocationsParsed.data.invocations : [];

  const meta = useAgentMeta(
    props.runId ?? null,
    summary?.root_agent_path ?? invocationsParsed.data?.agent_path ?? null,
  );

  const lastInv = invocations[invocations.length - 1] ?? null;
  const backend = lastInv?.backend ?? meta.data?.config?.backend ?? null;
  const model = lastInv?.model ?? meta.data?.config?.model ?? null;
  const renderer = lastInv?.renderer ?? null;
  const host =
    (meta.data?.config?.runtime as Record<string, unknown> | null)?.host as string | undefined;

  const sampling = (meta.data?.config?.sampling as Record<string, unknown> | undefined) ?? {};
  const resilience = (meta.data?.config?.resilience as Record<string, unknown> | undefined) ?? {};
  const io = (meta.data?.config?.io as Record<string, unknown> | undefined) ?? {};

  const empty = !backend && !model && !renderer;

  return (
    <PanelCard
      eyebrow="Backend"
      title={
        empty ? (
          "no backend captured yet"
        ) : (
          <span className="font-mono">{[backend, model, renderer].filter(Boolean).join(" · ")}</span>
        )
      }
    >
      {empty ? null : (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-x-5 gap-y-1.5">
            {backend ? <Metric label="backend" value={backend} /> : null}
            {model ? (
              <Metric label="model" value={<span className="font-mono">{model}</span>} />
            ) : null}
            {renderer ? <Metric label="renderer" value={renderer} /> : null}
            {host ? (
              <Metric label="host" value={<span className="font-mono">{host}</span>} />
            ) : null}
          </div>
          {meta.data ? (
            <KeyValueGrid
              density="compact"
              rows={[
                { key: "agent path", value: meta.data.agent_path, mono: true },
                { key: "kind", value: meta.data.kind },
                ...(backend ? [{ key: "backend", value: backend, mono: true }] : []),
                ...(model ? [{ key: "model", value: model, mono: true }] : []),
                ...(host ? [{ key: "host", value: host, mono: true }] : []),
                ...(renderer ? [{ key: "renderer", value: renderer, mono: true }] : []),
                ...kvRows(sampling, "sampling"),
                ...kvRows(resilience, "resilience"),
                ...kvRows(io, "io"),
              ]}
            />
          ) : null}
        </div>
      )}
    </PanelCard>
  );
}

function kvRows(
  obj: Record<string, unknown>,
  prefix: string,
): Array<{ key: string; value: string; mono: boolean }> {
  return Object.entries(obj).map(([k, v]) => ({
    key: `${prefix}.${k}`,
    value: v === null || v === undefined ? "—" : String(v),
    mono: true,
  }));
}
