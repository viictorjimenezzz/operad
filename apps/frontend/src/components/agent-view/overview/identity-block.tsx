import { HashTag, PanelCard, Pill } from "@/components/ui";
import { useAgentMeta } from "@/hooks/use-runs";
import { RunSummary } from "@/lib/types";

export interface IdentityBlockProps {
  dataSummary?: unknown;
  summary?: unknown;
  runId?: string | undefined;
  flat?: boolean | undefined;
}

export function IdentityBlock(props: IdentityBlockProps) {
  const summaryParsed = RunSummary.safeParse(props.dataSummary ?? props.summary);
  if (!summaryParsed.success || !props.runId || !summaryParsed.data.root_agent_path) {
    if (props.flat) {
      return <span className="text-[12px] text-muted-2">no agent metadata yet</span>;
    }
    return (
      <PanelCard eyebrow="Identity" title="not available">
        <span className="text-[12px] text-muted-2">no agent metadata yet</span>
      </PanelCard>
    );
  }
  const meta = useAgentMeta(props.runId, summaryParsed.data.root_agent_path);
  if (!meta.data) {
    if (props.flat) return <span className="text-[12px] text-muted-2">loading...</span>;
    return (
      <PanelCard eyebrow="Identity" title="loading…">
        <span />
      </PanelCard>
    );
  }

  const { class_name, kind, hash_content, role, task, rules, examples } = meta.data;
  const roleText = role?.trim() ? role : null;
  const taskText = task?.trim() ? task : null;

  const title = (
    <span className="flex flex-wrap items-center gap-2">
      <span className="font-mono">{class_name}</span>
      <Pill tone={kind === "composite" ? "algo" : "default"} size="sm">
        {kind}
      </Pill>
      <HashTag hash={hash_content} mono size="sm" />
      {meta.data.forward_in_overridden ? (
        <Pill tone="accent" size="sm">
          forward_in
        </Pill>
      ) : null}
      {meta.data.forward_out_overridden ? (
        <Pill tone="accent" size="sm">
          forward_out
        </Pill>
      ) : null}
    </span>
  );
  const body = (
    <div className="space-y-3 text-[13px]">
      {roleText ? (
        <Field label="role" flat={props.flat}>
          {roleText}
        </Field>
      ) : null}
      {taskText ? (
        <Field label="task" flat={props.flat}>
          {taskText}
        </Field>
      ) : null}
      {rules.length > 0 ? (
        <Field label={`rules (${rules.length})`} flat={props.flat}>
          <ol className="ml-4 list-decimal space-y-0.5 text-text marker:text-muted-2">
            {rules.map((rule, i) => (
              <li key={i}>{rule}</li>
            ))}
          </ol>
        </Field>
      ) : null}
      {examples.length > 0 ? (
        <Field label={`examples (${examples.length})`} flat={props.flat}>
          <span className="text-muted">See the Examples panel below for full payloads.</span>
        </Field>
      ) : null}
      {meta.data.forward_in_overridden && meta.data.forward_in_doc ? (
        <Field label="forward_in" flat={props.flat}>
          <span className="text-muted">{meta.data.forward_in_doc}</span>
        </Field>
      ) : null}
      {meta.data.forward_out_overridden && meta.data.forward_out_doc ? (
        <Field label="forward_out" flat={props.flat}>
          <span className="text-muted">{meta.data.forward_out_doc}</span>
        </Field>
      ) : null}
    </div>
  );

  if (props.flat) {
    return (
      <div className="space-y-3">
        <div>{title}</div>
        {body}
      </div>
    );
  }

  return (
    <PanelCard eyebrow="Identity" title={title}>
      {body}
    </PanelCard>
  );
}

function Field({
  label,
  children,
  flat,
}: {
  label: string;
  children: React.ReactNode;
  flat?: boolean | undefined;
}) {
  return (
    <div>
      <div className="mb-1 text-[10px] font-medium uppercase tracking-[0.08em] text-muted-2">
        {label}
      </div>
      <div className={flat ? "text-text" : "rounded-md bg-bg-inset px-3 py-2"}>{children}</div>
    </div>
  );
}
