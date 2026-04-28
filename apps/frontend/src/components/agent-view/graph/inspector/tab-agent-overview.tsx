import { Eyebrow, FieldTree, MarkdownView, Pill } from "@/components/ui";
import { HashRow } from "@/components/ui/hash-row";
import { useAgentMeta } from "@/hooks/use-runs";

export function TabAgentOverview({ runId, agentPath }: { runId: string; agentPath: string }) {
  const meta = useAgentMeta(runId, agentPath);

  if (meta.isLoading) {
    return <div className="p-5 text-[12px] text-muted-2">loading…</div>;
  }
  if (meta.error || !meta.data) {
    return <div className="p-5 text-[12px] text-[--color-err]">failed to load metadata</div>;
  }

  const m = meta.data;

  return (
    <div className="divide-y divide-border">
      <section className="px-5 py-4">
        <Eyebrow>identity</Eyebrow>
        <div className="mt-2 space-y-1.5">
          <div>
            <div className="text-[10px] text-muted-2">class</div>
            <div className="text-[13px]">{m.class_name}</div>
          </div>
          <div>
            <div className="text-[10px] text-muted-2">kind</div>
            <div className="text-[13px]">{m.kind}</div>
          </div>
          <div>
            <div className="text-[10px] text-muted-2">agent path</div>
            <div className="font-mono text-[11px] text-muted">{m.agent_path}</div>
          </div>
          <div>
            <div className="mb-1 text-[10px] text-muted-2">hash content</div>
            <HashRow current={{ hash_content: m.hash_content }} size="sm" />
          </div>
        </div>
      </section>

      {m.input_schema ? (
        <section className="px-5 py-4">
          <Eyebrow>input</Eyebrow>
          <div className="mt-2">
            <FieldTree data={m.input_schema} defaultDepth={2} hideCopy />
          </div>
        </section>
      ) : null}

      {m.output_schema ? (
        <section className="px-5 py-4">
          <Eyebrow>output</Eyebrow>
          <div className="mt-2">
            <FieldTree data={m.output_schema} defaultDepth={2} hideCopy />
          </div>
        </section>
      ) : null}

      {m.role ? (
        <section className="px-5 py-4">
          <Eyebrow>role</Eyebrow>
          <div className="mt-2 text-[13px]">
            <MarkdownView value={m.role} />
          </div>
        </section>
      ) : null}

      {m.task ? (
        <section className="px-5 py-4">
          <Eyebrow>task</Eyebrow>
          <div className="mt-2 text-[13px]">
            <MarkdownView value={m.task} />
          </div>
        </section>
      ) : null}

      {m.rules.length > 0 ? (
        <section className="px-5 py-4">
          <Eyebrow>rules ({m.rules.length})</Eyebrow>
          <ol className="mt-2 ml-4 list-decimal space-y-1 text-[13px] marker:text-muted-2">
            {m.rules.map((rule, i) => (
              <li key={i}>{rule}</li>
            ))}
          </ol>
        </section>
      ) : null}

      {m.examples.length > 0 ? (
        <section className="px-5 py-4">
          <Eyebrow>examples ({m.examples.length})</Eyebrow>
          <div className="mt-2 space-y-2">
            {m.examples.slice(0, 3).map((ex, i) => (
              <div key={i} className="grid grid-cols-2 gap-2 border-b border-border pb-2 last:border-0 last:pb-0">
                <div>
                  <div className="mb-1 text-[10px] text-muted-2">in</div>
                  <FieldTree data={ex.input} defaultDepth={1} hideCopy />
                </div>
                <div>
                  <div className="mb-1 text-[10px] text-muted-2">out</div>
                  <FieldTree data={ex.output} defaultDepth={1} hideCopy />
                </div>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      {m.config ? (
        <section className="px-5 py-4">
          <Eyebrow>config</Eyebrow>
          <div className="mt-2">
            <FieldTree data={m.config} defaultDepth={1} hideCopy />
          </div>
        </section>
      ) : null}

      <section className="px-5 py-4">
        <Eyebrow>hooks</Eyebrow>
        <div className="mt-2 flex flex-wrap gap-2">
          <Pill tone={m.forward_in_overridden ? "accent" : "default"}>
            forward_in {m.forward_in_overridden ? "overridden" : "default"}
          </Pill>
          <Pill tone={m.forward_out_overridden ? "accent" : "default"}>
            forward_out {m.forward_out_overridden ? "overridden" : "default"}
          </Pill>
        </div>
      </section>
    </div>
  );
}
