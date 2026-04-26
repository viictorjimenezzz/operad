import { FieldTree, Section } from "@/components/ui";
import { useAgentMeta } from "@/hooks/use-runs";
import { RunSummary } from "@/lib/types";

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
  const role = meta.data?.role ?? null;
  const task = meta.data?.task ?? null;
  const rules = meta.data?.rules ?? [];
  const empty = !config && !role && !task && rules.length === 0;

  const fields = [
    role ? "role" : null,
    task ? "task" : null,
    rules.length > 0 ? `${rules.length} rules` : null,
    config ? "config" : null,
  ].filter((f): f is string => f !== null);

  return (
    <Section
      title="Configuration"
      summary={empty ? "no metadata available" : fields.join(" · ")}
      disabled={empty}
    >
      <div className="space-y-3">
        {role ? (
          <div>
            <div className="mb-1 text-[10px] font-medium uppercase tracking-[0.08em] text-muted">
              role
            </div>
            <div className="rounded-lg bg-bg-inset px-3 py-2 text-[13px] text-text">{role}</div>
          </div>
        ) : null}
        {task ? (
          <div>
            <div className="mb-1 text-[10px] font-medium uppercase tracking-[0.08em] text-muted">
              task
            </div>
            <div className="rounded-lg bg-bg-inset px-3 py-2 text-[13px] text-text">{task}</div>
          </div>
        ) : null}
        {rules.length > 0 ? (
          <div>
            <div className="mb-1 text-[10px] font-medium uppercase tracking-[0.08em] text-muted">
              rules
            </div>
            <ol className="ml-4 list-decimal space-y-0.5 text-[13px] text-text marker:text-muted-2">
              {rules.map((rule, i) => (
                <li key={i}>{rule}</li>
              ))}
            </ol>
          </div>
        ) : null}
        {config ? (
          <div>
            <div className="mb-1 text-[10px] font-medium uppercase tracking-[0.08em] text-muted">
              config
            </div>
            <div className="rounded-lg bg-bg-inset px-3 py-2">
              <FieldTree data={config} defaultDepth={1} hideCopy />
            </div>
          </div>
        ) : null}
      </div>
    </Section>
  );
}
