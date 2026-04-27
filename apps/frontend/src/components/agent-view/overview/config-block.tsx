import { FieldTree, Metric, Section } from "@/components/ui";
import { useAgentMeta } from "@/hooks/use-runs";
import { RunSummary } from "@/lib/types";
import { useMemo } from "react";

export interface ConfigBlockProps {
  dataSummary?: unknown;
  summary?: unknown;
  runId?: string;
}

export function ConfigBlock(props: ConfigBlockProps) {
  const summaryParsed = RunSummary.safeParse(props.dataSummary ?? props.summary);
  if (!summaryParsed.success || !props.runId || !summaryParsed.data.root_agent_path) {
    return (
      <Section title="Configuration" summary="not available" disabled>
        <span />
      </Section>
    );
  }
  const meta = useAgentMeta(props.runId, summaryParsed.data.root_agent_path);
  const config = meta.data?.config ?? null;
  const isComposite = meta.data?.kind === "composite";

  const summary = useMemo(() => {
    if (!meta.data) return "loading…";
    if (!config) {
      return isComposite ? "configuration lives on leaf agents" : "no configuration captured";
    }
    const parts: string[] = [];
    const sampling = (config.sampling as Record<string, unknown>) ?? {};
    if (sampling.temperature !== undefined) parts.push(`temp ${sampling.temperature}`);
    if (sampling.max_tokens !== undefined) parts.push(`max_tokens ${sampling.max_tokens}`);
    return parts.length > 0 ? parts.join(" · ") : "configuration available";
  }, [config, isComposite, meta.data]);

  const succinct =
    config !== null ? (
      <div className="flex flex-wrap items-center gap-x-5 gap-y-1.5">
        {(() => {
          const sampling = (config.sampling as Record<string, unknown>) ?? {};
          const resilience = (config.resilience as Record<string, unknown>) ?? {};
          const items: { label: string; value: string }[] = [];
          if (sampling.temperature !== undefined)
            items.push({ label: "temperature", value: String(sampling.temperature) });
          if (sampling.max_tokens !== undefined)
            items.push({ label: "max_tokens", value: String(sampling.max_tokens) });
          if (sampling.top_p !== undefined && sampling.top_p !== null)
            items.push({ label: "top_p", value: String(sampling.top_p) });
          if (sampling.seed !== undefined && sampling.seed !== null)
            items.push({ label: "seed", value: String(sampling.seed) });
          if (resilience.max_retries !== undefined)
            items.push({ label: "retries", value: String(resilience.max_retries) });
          if (resilience.timeout !== undefined)
            items.push({ label: "timeout", value: `${resilience.timeout}s` });
          return items.map((it) => <Metric key={it.label} label={it.label} value={it.value} />);
        })()}
      </div>
    ) : null;

  return (
    <Section
      title="Configuration"
      summary={summary}
      {...(succinct ? { succinct } : {})}
      disabled={!config}
    >
      {config ? (
        <div className="rounded-md bg-bg-inset px-3 py-2">
          <FieldTree data={config} defaultDepth={2} hideCopy />
        </div>
      ) : null}
    </Section>
  );
}
