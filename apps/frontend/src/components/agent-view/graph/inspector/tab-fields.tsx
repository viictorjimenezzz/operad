import { Eyebrow, KeyValueGrid } from "@/components/ui";
import type { IoGraphResponse } from "@/lib/types";

export function TabFields({
  nodeKey,
  ioGraph,
}: {
  nodeKey: string;
  ioGraph: IoGraphResponse;
}) {
  const node = ioGraph.nodes.find((n) => n.key === nodeKey);
  if (!node) {
    return <div className="p-5 text-[12px] text-muted-2">type not found</div>;
  }

  const userFields = node.fields.filter((f) => !f.system);
  const systemFields = node.fields.filter((f) => f.system);
  const usedAsSource = ioGraph.edges.filter((e) => e.from === nodeKey);
  const usedAsTarget = ioGraph.edges.filter((e) => e.to === nodeKey);

  return (
    <div className="space-y-5 p-5">
      <section>
        <Eyebrow>Fields ({userFields.length})</Eyebrow>
        <ul className="mt-3 space-y-2.5">
          {userFields.map((f) => (
            <li key={f.name} className="rounded-xl border border-border bg-bg-2 px-3 py-2.5">
              <div className="flex items-baseline gap-2">
                <span className="font-mono text-[13px] font-medium text-text">{f.name}</span>
                <span className="font-mono text-[11px] text-muted">{f.type}</span>
              </div>
              {f.description ? (
                <div className="mt-1 text-[12px] text-muted">{f.description}</div>
              ) : null}
            </li>
          ))}
        </ul>
      </section>

      {systemFields.length > 0 ? (
        <section>
          <Eyebrow>System fields ({systemFields.length})</Eyebrow>
          <ul className="mt-2 space-y-1">
            {systemFields.map((f) => (
              <li
                key={f.name}
                className="flex items-baseline gap-2 rounded-lg bg-bg-2/40 px-2.5 py-1.5 font-mono text-[11px]"
              >
                <span className="text-text">{f.name}</span>
                <span className="text-muted">{f.type}</span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section>
        <Eyebrow>Used by</Eyebrow>
        <KeyValueGrid
          density="compact"
          rows={[
            {
              key: "as input",
              value:
                usedAsTarget.length > 0 ? usedAsTarget.map((e) => e.class_name).join(", ") : "—",
            },
            {
              key: "as output",
              value:
                usedAsSource.length > 0 ? usedAsSource.map((e) => e.class_name).join(", ") : "—",
            },
          ]}
          className="mt-2"
        />
      </section>
    </div>
  );
}
