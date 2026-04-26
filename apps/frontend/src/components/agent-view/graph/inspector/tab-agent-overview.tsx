import { Eyebrow, FieldTree, HashTag, KeyValueGrid, Pill } from "@/components/ui";
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
    <div className="space-y-5 p-5">
      <section>
        <div className="flex items-center gap-2">
          <Eyebrow>identity</Eyebrow>
        </div>
        <KeyValueGrid
          className="mt-2"
          density="compact"
          rows={[
            { key: "class", value: m.class_name },
            { key: "kind", value: m.kind },
            { key: "agent path", value: m.agent_path, mono: true },
            {
              key: "hash content",
              value: <HashTag hash={m.hash_content} mono size="sm" />,
            },
          ]}
        />
      </section>

      {m.role ? (
        <section>
          <Eyebrow>role</Eyebrow>
          <div className="mt-2 rounded-lg bg-bg-inset px-3 py-2 text-[13px]">{m.role}</div>
        </section>
      ) : null}

      {m.task ? (
        <section>
          <Eyebrow>task</Eyebrow>
          <div className="mt-2 rounded-lg bg-bg-inset px-3 py-2 text-[13px]">{m.task}</div>
        </section>
      ) : null}

      {m.rules.length > 0 ? (
        <section>
          <Eyebrow>rules ({m.rules.length})</Eyebrow>
          <ol className="mt-2 ml-4 list-decimal space-y-1 text-[13px] marker:text-muted-2">
            {m.rules.map((rule, i) => (
              <li key={i}>{rule}</li>
            ))}
          </ol>
        </section>
      ) : null}

      <section>
        <Eyebrow>hooks</Eyebrow>
        <div className="mt-2 flex flex-wrap gap-2">
          <Pill tone={m.forward_in_overridden ? "accent" : "default"}>
            forward_in {m.forward_in_overridden ? "✓" : "default"}
          </Pill>
          <Pill tone={m.forward_out_overridden ? "accent" : "default"}>
            forward_out {m.forward_out_overridden ? "✓" : "default"}
          </Pill>
        </div>
      </section>

      {m.config ? (
        <section>
          <Eyebrow>config</Eyebrow>
          <div className="mt-2 rounded-lg bg-bg-inset p-3">
            <FieldTree data={m.config} defaultDepth={1} hideCopy />
          </div>
        </section>
      ) : null}

      {m.examples.length > 0 ? (
        <section>
          <Eyebrow>examples ({m.examples.length})</Eyebrow>
          <div className="mt-2 space-y-2">
            {m.examples.slice(0, 3).map((ex, i) => (
              <div key={i} className="grid grid-cols-2 gap-2 rounded-lg bg-bg-inset p-2">
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
    </div>
  );
}
