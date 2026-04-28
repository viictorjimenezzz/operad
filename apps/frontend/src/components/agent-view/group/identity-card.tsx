import { HashTag, Metric, Pill } from "@/components/ui";
import type { AgentGroupDetail, AgentMetaResponse } from "@/lib/types";

export function AgentGroupIdentityCard({
  group,
  meta,
}: {
  group: AgentGroupDetail;
  meta?: AgentMetaResponse | null | undefined;
}) {
  const className = meta?.class_name ?? group.class_name ?? "Agent";
  const role = meta?.role?.trim() ? meta.role : null;
  const task = meta?.task?.trim() ? meta.task : null;
  const trainable = meta?.trainable_paths.length ?? 0;

  return (
    <section className="border-b border-border pb-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="m-0 text-[18px] font-semibold text-text">{className}</h2>
            {meta?.kind ? (
              <Pill tone={meta.kind === "composite" ? "algo" : "default"}>{meta.kind}</Pill>
            ) : null}
          </div>
          {role ? <p className="m-0 max-w-3xl text-[13px] text-muted">{role}</p> : null}
          {task ? <p className="m-0 max-w-3xl text-[13px] text-text">{task}</p> : null}
          <div className="flex flex-wrap items-center gap-x-5 gap-y-1.5">
            <Metric label="rules" value={meta?.rules.length ?? 0} />
            <Metric label="examples" value={meta?.examples.length ?? 0} />
            <Metric
              label="trainable"
              value={trainable}
              sub={trainable > 0 ? meta?.trainable_paths.join(", ") : undefined}
            />
          </div>
        </div>
        <HashTag hash={group.hash_content} mono label={`hash ${group.hash_content.slice(0, 10)}`} />
      </div>
    </section>
  );
}
