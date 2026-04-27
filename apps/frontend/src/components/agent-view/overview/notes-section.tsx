import { MarkdownView } from "@/components/ui";
import { usePatchRunNotes } from "@/hooks/use-runs";
import { RunSummary } from "@/lib/types";
import { Pencil } from "lucide-react";
import { useEffect, useState } from "react";

export interface NotesSectionProps {
  dataSummary?: unknown;
  sourceSummary?: unknown;
  runId?: string;
}

export function NotesSection(props: NotesSectionProps) {
  const parsed = RunSummary.safeParse(props.dataSummary ?? props.sourceSummary);
  const run = parsed.success ? parsed.data : null;
  const runId = props.runId ?? run?.run_id ?? null;
  const [value, setValue] = useState(run?.notes_markdown ?? "");
  const saveNotes = usePatchRunNotes();

  useEffect(() => {
    setValue(run?.notes_markdown ?? "");
  }, [run?.notes_markdown]);

  return (
    <section className="rounded-lg border border-border bg-bg-1">
      <div className="flex min-h-10 items-center gap-2 border-b border-border px-3 py-2">
        <span className="text-[13px] font-medium text-text">Notes</span>
        {!value.trim() ? <span className="text-[12px] text-muted-2">add a note</span> : null}
        <Pencil size={12} className="ml-auto text-muted-2" />
      </div>
      <div className="p-3">
        <MarkdownView
          value={value}
          {...(runId
            ? {
                onSave: async (next: string) => {
                  const saved = await saveNotes.mutateAsync({ runId, markdown: next });
                  setValue(saved.notes_markdown);
                },
              }
            : {})}
        />
      </div>
    </section>
  );
}
