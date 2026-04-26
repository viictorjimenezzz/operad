import { Button } from "@/components/ui/button";
import { useRateRow } from "@/hooks/use-studio";
import type { JobRow } from "@/lib/types";
import * as Slider from "@radix-ui/react-slider";
import { useState } from "react";

interface RatingFormProps {
  jobName: string;
  row: JobRow;
}

export function RatingForm({ jobName, row }: RatingFormProps) {
  const [rating, setRating] = useState(row.rating ?? 3);
  const [rationale, setRationale] = useState(row.rationale ?? "");
  const [savedAt, setSavedAt] = useState<number | null>(null);
  const mutation = useRateRow(jobName);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await mutation.mutateAsync({ rowId: row.id, rating, rationale });
    setSavedAt(Date.now());
  };

  return (
    <form
      onSubmit={onSubmit}
      className="flex flex-col gap-2 rounded-md border border-border bg-bg-2 p-3"
    >
      <div className="flex items-center gap-3 text-xs">
        <span className="text-[0.68rem] uppercase tracking-[0.08em] text-muted">rating</span>
        <Slider.Root
          className="relative flex h-5 w-full max-w-xs touch-none select-none items-center"
          value={[rating]}
          min={1}
          max={5}
          step={1}
          onValueChange={(v) => v[0] != null && setRating(v[0])}
        >
          <Slider.Track className="relative h-1 grow rounded-full bg-bg-3">
            <Slider.Range className="absolute h-full rounded-full bg-accent" />
          </Slider.Track>
          <Slider.Thumb
            className="block h-3 w-3 rounded-full border border-border-strong bg-accent shadow focus:outline-none focus:ring-2 focus:ring-accent"
            aria-label="rating"
          />
        </Slider.Root>
        <span className="w-8 text-center font-mono tabular-nums text-text">{rating}</span>
      </div>
      <textarea
        value={rationale}
        onChange={(e) => setRationale(e.target.value)}
        rows={2}
        placeholder="rationale (optional)"
        className="w-full rounded border border-border bg-bg-3 px-2 py-1 font-mono text-[11px] text-text focus:border-accent focus:outline-none"
      />
      <div className="flex items-center gap-2">
        <Button type="submit" size="sm" variant="primary" disabled={mutation.isPending}>
          {mutation.isPending ? "saving…" : "save"}
        </Button>
        {savedAt && Date.now() - savedAt < 2000 && (
          <span className="text-[11px] text-ok">saved</span>
        )}
        {mutation.error && <span className="text-[11px] text-err">{String(mutation.error)}</span>}
      </div>
    </form>
  );
}
