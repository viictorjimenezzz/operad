import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useStartTraining } from "@/hooks/use-studio";
import { TrainingStatusStream } from "@/studio/components/training-status-stream";
import { useState } from "react";

interface TrainingLauncherProps {
  jobName: string;
}

export function TrainingLauncher({ jobName }: TrainingLauncherProps) {
  const [epochs, setEpochs] = useState(1);
  const [lr, setLr] = useState(1.0);
  const [streaming, setStreaming] = useState(false);
  const mutation = useStartTraining(jobName);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setStreaming(false);
    await mutation.mutateAsync({ epochs, lr });
    setStreaming(true);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>train</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={onSubmit} className="flex flex-wrap items-end gap-3 text-xs">
          <Field label="epochs">
            <input
              type="number"
              min={1}
              max={20}
              value={epochs}
              onChange={(e) => setEpochs(Number.parseInt(e.target.value, 10) || 1)}
              className="w-20 rounded border border-border bg-bg-3 px-2 py-1 font-mono text-text focus:border-accent focus:outline-none"
            />
          </Field>
          <Field label="lr">
            <input
              type="number"
              step={0.1}
              min={0}
              value={lr}
              onChange={(e) => setLr(Number.parseFloat(e.target.value) || 1.0)}
              className="w-20 rounded border border-border bg-bg-3 px-2 py-1 font-mono text-text focus:border-accent focus:outline-none"
            />
          </Field>
          <Button type="submit" variant="primary" size="sm" disabled={mutation.isPending}>
            {mutation.isPending ? "starting…" : "Train"}
          </Button>
          {mutation.error && <span className="text-[11px] text-err">{String(mutation.error)}</span>}
        </form>
        {streaming && (
          <div className="mt-3">
            <TrainingStatusStream jobName={jobName} />
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  // <fieldset> + <legend> is the accessible way to group form controls
  // under a label without relying on htmlFor. Visually it looks like a
  // <label>+<span>; semantically it's stronger.
  return (
    <fieldset className="m-0 flex flex-col gap-1 border-0 p-0">
      <legend className="text-[0.68rem] uppercase tracking-[0.08em] text-muted">{label}</legend>
      {children}
    </fieldset>
  );
}
