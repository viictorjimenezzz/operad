import { HashTag, Metric, Pill } from "@/components/ui";
import type { AgentGroupDetail, AgentMetaResponse } from "@/lib/types";
import { useState } from "react";

const ROLE_TASK_CLAMP_CHARS = 240;

function isConfigPath(path: string): boolean {
  return path.startsWith("config.") || path === "config";
}

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

  const trainablePaths = meta?.trainable_paths ?? [];
  // Surface user-facing knobs first; bury config.* (model/backend/renderer/
  // temperature) since those rarely participate in optimisation by default
  // and would otherwise dominate the preview line on every leaf.
  const userPaths = trainablePaths.filter((p) => !isConfigPath(p));
  const configPaths = trainablePaths.filter(isConfigPath);
  const trainable = trainablePaths.length;
  const previewLeaves = (userPaths.length > 0 ? userPaths : configPaths)
    .slice(0, 6)
    .map((path) => path.split(".").at(-1) ?? path);
  const dedupedLeaves = previewLeaves.filter((leaf, i, arr) => arr.indexOf(leaf) === i);
  const previewSuffix =
    trainable > dedupedLeaves.length ? ` +${trainable - dedupedLeaves.length}` : "";
  const trainablePreview =
    trainable > 0 ? dedupedLeaves.join(", ") + previewSuffix : undefined;

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
          {role ? <ClampedText className="text-muted" text={role} /> : null}
          {task ? <ClampedText className="text-text" text={task} /> : null}
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

function ClampedText({ text, className }: { text: string; className: string }) {
  const [open, setOpen] = useState(false);
  if (text.length <= ROLE_TASK_CLAMP_CHARS) {
    return <p className={`m-0 max-w-3xl text-[13px] ${className}`}>{text}</p>;
  }
  return (
    <p className={`m-0 max-w-3xl text-[13px] ${className}`}>
      {open ? text : text.slice(0, ROLE_TASK_CLAMP_CHARS) + "…"}
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="ml-1 align-baseline text-[11px] font-medium text-accent underline-offset-2 hover:underline"
      >
        {open ? "show less" : "show more"}
      </button>
    </p>
  );
}
