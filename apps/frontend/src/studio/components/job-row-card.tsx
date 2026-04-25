import type { JobRow } from "@/lib/types";
import { truncateMiddle } from "@/lib/utils";
import { JsonView } from "@/shared/ui/json-view";
import { RatingForm } from "@/studio/components/rating-form";

interface JobRowCardProps {
  jobName: string;
  row: JobRow;
}

export function JobRowCard({ jobName, row }: JobRowCardProps) {
  return (
    <li className="rounded-md border border-border bg-bg-1 p-3">
      <header className="mb-2 flex items-center gap-3 text-[11px] text-muted">
        <span>#{row.index}</span>
        <span>
          id <code className="font-mono">{truncateMiddle(row.id, 12)}</code>
        </span>
        <span>
          run <code className="font-mono">{truncateMiddle(row.run_id, 12)}</code>
        </span>
        <span className="ml-auto font-mono">{row.agent_path}</span>
      </header>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        <Section label="input" value={row.input} />
        <Section label="predicted" value={row.predicted} />
      </div>
      {row.expected != null && (
        <div className="mt-3">
          <Section label="expected" value={row.expected} />
        </div>
      )}
      <div className="mt-3">
        <RatingForm jobName={jobName} row={row} />
      </div>
    </li>
  );
}

function Section({ label, value }: { label: string; value: unknown }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-[0.68rem] uppercase tracking-[0.08em] text-muted">{label}</span>
      <JsonView value={value} />
    </div>
  );
}
