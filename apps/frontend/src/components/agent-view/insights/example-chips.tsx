import { useUIStore } from "@/stores/ui";

export function ExampleChips({
  agentPath,
  examples,
}: {
  agentPath: string;
  examples: Array<{ input?: unknown; output?: unknown }>;
}) {
  const openDrawer = useUIStore((s) => s.openDrawer);

  if (examples.length === 0) return null;

  return (
    <div className="flex flex-wrap items-center gap-2 rounded-md border border-border bg-bg-1 p-3">
      <span className="text-[11px] uppercase tracking-[0.07em] text-muted">examples</span>
      {examples.map((example, index) => (
        <button
          key={`example-${index}`}
          type="button"
          className="rounded border border-border bg-bg-2 px-2 py-1 text-[11px] text-muted hover:text-text"
          onClick={() =>
            openDrawer("experiment", {
              agentPath,
              input: example.input,
              source: "example",
              exampleIndex: index,
            })
          }
        >
          run example {index + 1}
        </button>
      ))}
    </div>
  );
}
