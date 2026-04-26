import { KeyValueGrid, Pill, Section } from "@/components/ui";
import { useAgentMeta } from "@/hooks/use-runs";
import { RunInvocationsResponse, RunSummary } from "@/lib/types";
import { useMemo } from "react";

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

  const summaryText = useMemo(() => {
    const parts: string[] = [];
    if (backend) parts.push(backend);
    if (model) parts.push(model);
    if (renderer) parts.push(renderer);
    return parts.length === 0 ? "no backend captured yet" : parts.join(" · ");
  }, [backend, model, renderer]);

  const disabled = !backend && !model && !renderer;

  return (
    <Section title="Backend" summary={summaryText} disabled={disabled}>
      <div className="flex flex-wrap gap-2">
        {backend ? <Pill tone="accent">{backend}</Pill> : null}
        {model ? <Pill tone="default">{model}</Pill> : null}
        {renderer ? <Pill tone="default">{renderer}</Pill> : null}
      </div>
      {meta.data ? (
        <div className="mt-3">
          <KeyValueGrid
            density="compact"
            rows={[
              {
                key: "agent path",
                value: meta.data.agent_path,
                mono: true,
              },
              {
                key: "kind",
                value: meta.data.kind,
              },
              ...(meta.data.config?.sampling
                ? [
                    {
                      key: "temperature",
                      value: String(
                        (meta.data.config.sampling as Record<string, unknown>).temperature ?? "—",
                      ),
                      mono: true,
                    },
                    {
                      key: "max_tokens",
                      value: String(
                        (meta.data.config.sampling as Record<string, unknown>).max_tokens ?? "—",
                      ),
                      mono: true,
                    },
                  ]
                : []),
            ]}
          />
        </div>
      ) : null}
    </Section>
  );
}
