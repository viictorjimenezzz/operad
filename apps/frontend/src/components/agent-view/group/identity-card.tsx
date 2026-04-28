import { HashTag, Metric, Pill } from "@/components/ui";
import type { AgentGroupDetail, AgentMetaResponse } from "@/lib/types";

export function AgentGroupIdentityCard({
  group,
  meta,
}: {
  group: AgentGroupDetail;
  meta?: AgentMetaResponse | null | undefined;
}) {
  // Prefer the group-level class name (the user-declared label such as
  // `research_analyst` or `Reasoner`) over the runtime meta's
  // `class_name`, which may resolve to the wrapper composite type
  // (`Sequential`, `Parallel`...) and confuse the reader.
  const className = group.class_name ?? meta?.class_name ?? "Agent";
  const role = meta?.role?.trim() ? meta.role : null;
  const task = meta?.task?.trim() ? meta.task : null;
  const trainable = meta?.trainable_paths.length ?? 0;
  // Show only the leaf-level parameter names (e.g. "role, task") without
  // the dotted full path, capped at 6 — enough to cue the reader without
  // turning the identity card into a wall of text. The full list lives
  // on the Training tab.
  const trainablePreview =
    trainable > 0
      ? meta!.trainable_paths
          .slice(0, 6)
          .map((path) => path.split(".").at(-1) ?? path)
          .filter((leaf, index, arr) => arr.indexOf(leaf) === index)
          .join(", ") + (trainable > 6 ? "…" : "")
      : undefined;

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
              {...(trainablePreview ? { sub: trainablePreview } : {})}
            />
          </div>
        </div>
        <HashTag hash={group.hash_content} mono label={`hash ${group.hash_content.slice(0, 10)}`} />
      </div>
    </section>
  );
}
