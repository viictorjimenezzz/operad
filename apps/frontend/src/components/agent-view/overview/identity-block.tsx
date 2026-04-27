import { HashTag, Pill, Section } from "@/components/ui";
import { useAgentMeta } from "@/hooks/use-runs";
import { RunSummary } from "@/lib/types";

export interface IdentityBlockProps {
  dataSummary?: unknown;
  summary?: unknown;
  runId?: string;
}

export function IdentityBlock(props: IdentityBlockProps) {
  const summaryParsed = RunSummary.safeParse(props.dataSummary ?? props.summary);
  if (!summaryParsed.success || !props.runId || !summaryParsed.data.root_agent_path) {
    return (
      <Section title="Identity" summary="not available" disabled>
        <span />
      </Section>
    );
  }
  const meta = useAgentMeta(props.runId, summaryParsed.data.root_agent_path);
  if (!meta.data) {
    return (
      <Section title="Identity" summary="loading…" disabled>
        <span />
      </Section>
    );
  }

  const { class_name, kind, hash_content, role, task, rules, examples } = meta.data;
  const roleText = role?.trim() ? role : null;
  const taskText = task?.trim() ? task : null;
  const summaryText = `${class_name} · ${kind} · ${rules.length} rules · ${examples.length} examples`;

  const succinct = (
    <div className="space-y-1.5">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-[12px] text-text">{class_name}</span>
        <Pill tone={kind === "composite" ? "algo" : "default"}>{kind}</Pill>
        <HashTag hash={hash_content} mono size="sm" />
        {meta.data.forward_in_overridden ? (
          <Pill tone="accent" title="leaf has a custom forward_in hook">
            forward_in
          </Pill>
        ) : null}
        {meta.data.forward_out_overridden ? (
          <Pill tone="accent" title="leaf has a custom forward_out hook">
            forward_out
          </Pill>
        ) : null}
      </div>
      {roleText || taskText ? (
        <div className="grid grid-cols-[60px_1fr] items-baseline gap-x-3 gap-y-1 text-[12px]">
          {roleText ? (
            <>
              <span className="text-[10px] uppercase tracking-[0.06em] text-muted-2">role</span>
              <span className="truncate text-muted">{roleText}</span>
            </>
          ) : null}
          {taskText ? (
            <>
              <span className="text-[10px] uppercase tracking-[0.06em] text-muted-2">task</span>
              <span className="truncate text-muted">{taskText}</span>
            </>
          ) : null}
        </div>
      ) : null}
    </div>
  );

  return (
    <Section title="Identity" summary={summaryText} succinct={succinct}>
      <div className="space-y-3 text-[13px]">
        {roleText ? (
          <Field label="role">
            <span className="text-text">{roleText}</span>
          </Field>
        ) : null}
        {taskText ? (
          <Field label="task">
            <span className="text-text">{taskText}</span>
          </Field>
        ) : null}
        {rules.length > 0 ? (
          <Field label={`rules (${rules.length})`}>
            <ol className="ml-4 list-decimal space-y-0.5 text-text marker:text-muted-2">
              {rules.map((rule, i) => (
                <li key={i}>{rule}</li>
              ))}
            </ol>
          </Field>
        ) : null}
        {examples.length > 0 ? (
          <Field label={`examples (${examples.length})`}>
            <span className="text-muted">
              See the Examples section below for full input/output payloads.
            </span>
          </Field>
        ) : null}
        {meta.data.forward_in_overridden && meta.data.forward_in_doc ? (
          <Field label="forward_in">
            <span className="text-muted">{meta.data.forward_in_doc}</span>
          </Field>
        ) : null}
        {meta.data.forward_out_overridden && meta.data.forward_out_doc ? (
          <Field label="forward_out">
            <span className="text-muted">{meta.data.forward_out_doc}</span>
          </Field>
        ) : null}
      </div>
    </Section>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="mb-1 text-[10px] font-medium uppercase tracking-[0.08em] text-muted-2">
        {label}
      </div>
      <div className="rounded-md bg-bg-inset px-3 py-2">{children}</div>
    </div>
  );
}
