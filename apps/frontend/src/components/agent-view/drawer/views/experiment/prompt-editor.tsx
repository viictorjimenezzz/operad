interface PromptEditorProps {
  role: string;
  task: string;
  rulesText: string;
  examplesText: string;
  temperatureText: string;
  defaults: {
    role: string;
    task: string;
    rulesText: string;
    examplesText: string;
    temperatureText: string;
  };
  onChange: (next: {
    role: string;
    task: string;
    rulesText: string;
    examplesText: string;
    temperatureText: string;
  }) => void;
}

function dirty(current: string, fallback: string): boolean {
  return current.trim() !== fallback.trim();
}

export function PromptEditor({
  role,
  task,
  rulesText,
  examplesText,
  temperatureText,
  defaults,
  onChange,
}: PromptEditorProps) {
  const labelClass = "mb-1 block text-[11px] uppercase tracking-[0.07em] text-muted";

  return (
    <div className="space-y-2 rounded border border-border bg-bg-1 p-3">
      <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-muted">edit prompt</div>

      <label className={labelClass}>
        role{dirty(role, defaults.role) ? " *" : ""}
        <textarea
          className="mt-1 w-full rounded border border-border bg-bg-2 p-2 text-xs text-text"
          rows={3}
          value={role}
          onChange={(e) => onChange({ role: e.target.value, task, rulesText, examplesText, temperatureText })}
        />
      </label>

      <label className={labelClass}>
        task{dirty(task, defaults.task) ? " *" : ""}
        <textarea
          className="mt-1 w-full rounded border border-border bg-bg-2 p-2 text-xs text-text"
          rows={3}
          value={task}
          onChange={(e) => onChange({ role, task: e.target.value, rulesText, examplesText, temperatureText })}
        />
      </label>

      <label className={labelClass}>
        rules (one per line){dirty(rulesText, defaults.rulesText) ? " *" : ""}
        <textarea
          className="mt-1 w-full rounded border border-border bg-bg-2 p-2 font-mono text-xs text-text"
          rows={4}
          value={rulesText}
          onChange={(e) =>
            onChange({ role, task, rulesText: e.target.value, examplesText, temperatureText })
          }
        />
      </label>

      <label className={labelClass}>
        examples (json array){dirty(examplesText, defaults.examplesText) ? " *" : ""}
        <textarea
          className="mt-1 w-full rounded border border-border bg-bg-2 p-2 font-mono text-xs text-text"
          rows={6}
          value={examplesText}
          onChange={(e) =>
            onChange({ role, task, rulesText, examplesText: e.target.value, temperatureText })
          }
        />
      </label>

      <label className={labelClass}>
        sampling.temperature{dirty(temperatureText, defaults.temperatureText) ? " *" : ""}
        <input
          className="mt-1 w-full rounded border border-border bg-bg-2 p-2 font-mono text-xs text-text"
          value={temperatureText}
          onChange={(e) =>
            onChange({ role, task, rulesText, examplesText, temperatureText: e.target.value })
          }
        />
      </label>
    </div>
  );
}
