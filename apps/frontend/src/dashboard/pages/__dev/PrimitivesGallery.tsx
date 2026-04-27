import {
  CollapsibleSection,
  MarkdownView,
  MultiSeriesChart,
  PanelCard,
  PanelGrid,
  type RunRow,
  RunTable,
  type RunTableColumn,
} from "@/components/ui";

const rows: RunRow[] = Array.from({ length: 64 }, (_, index) => {
  const state = index % 17 === 0 ? "error" : index % 9 === 0 ? "running" : "ended";
  return {
    id: `run-${index.toString().padStart(3, "0")}`,
    identity: `hash-${index % 12}`,
    state,
    startedAt: 1_720_000_000 + index * 80,
    endedAt: state === "running" ? null : 1_720_000_030 + index * 80,
    durationMs: state === "running" ? null : 900 + index * 17,
    fields: {
      score: { kind: "num", value: 0.72 + index / 500, format: "score" },
      tokens: { kind: "num", value: 400 + index * 19, format: "tokens" },
      cost: { kind: "num", value: 0.002 + index * 0.0007, format: "cost" },
      group: { kind: "text", value: index % 2 === 0 ? "planner" : "writer" },
      spark: {
        kind: "sparkline",
        values: [2, 3 + (index % 4), 4, 5 + (index % 7), 3 + (index % 5)],
      },
      notes: { kind: "markdown", value: index % 3 === 0 ? "**reviewed**" : "queued" },
    },
  };
});

const columns: RunTableColumn[] = [
  { id: "state", label: "State", source: "_state", sortable: true, width: 92 },
  { id: "run", label: "Run", source: "_id", sortable: true, width: 110 },
  { id: "started", label: "Started", source: "_started", sortable: true, width: 110 },
  { id: "duration", label: "Latency", source: "_duration", sortable: true, width: 90 },
  { id: "score", label: "Score", source: "score", sortable: true, defaultSort: "desc", width: 82 },
  { id: "tokens", label: "Tokens", source: "tokens", sortable: true, width: 86, align: "right" },
  { id: "cost", label: "Cost", source: "cost", sortable: true, width: 80, align: "right" },
  { id: "spark", label: "Trend", source: "spark", width: 86 },
  { id: "notes", label: "Notes", source: "notes", width: "1fr" },
];

export function PrimitivesGallery() {
  return (
    <div className="min-h-full overflow-auto bg-bg p-5">
      <div className="mx-auto flex max-w-6xl flex-col gap-4">
        <PanelGrid cols={2}>
          <PanelCard title="RunTable" bodyMinHeight={380} flush>
            <RunTable
              rows={rows}
              columns={columns}
              storageKey="dev.primitives"
              rowHref={(row) => `/runs/${row.id}`}
              selectable
              pageSize={50}
              groupBy={(row) => ({
                key: String(row.fields.group?.kind === "text" ? row.fields.group.value : "runs"),
                label: String(row.fields.group?.kind === "text" ? row.fields.group.value : "runs"),
              })}
            />
          </PanelCard>
          <PanelCard title="Markdown and sections" bodyMinHeight={380}>
            <div className="flex flex-col gap-3">
              <CollapsibleSection id="identity" label="Identity" preview="hash and backend">
                <MarkdownView
                  value={
                    "## Notes\n\n- renders **markdown**\n- keeps raw HTML escaped\n\n`hash_content` drives color."
                  }
                />
              </CollapsibleSection>
              <CollapsibleSection id="backend" label="Backend" preview="model sampling">
                <MarkdownView value={"A collapsed row can deep-link with `#section=backend`."} />
              </CollapsibleSection>
            </div>
          </PanelCard>
        </PanelGrid>
        <PanelCard title="MultiSeriesChart">
          <MultiSeriesChart
            height={220}
            series={[
              { id: "single", label: "single point", points: [{ x: 1, y: 0.8 }] },
              {
                id: "line",
                label: "line",
                points: [
                  { x: 0, y: 0.2 },
                  { x: 1, y: 0.5 },
                  { x: 2, y: 0.7 },
                ],
              },
            ]}
          />
        </PanelCard>
      </div>
    </div>
  );
}
