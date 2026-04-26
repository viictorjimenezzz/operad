import { EventTimeline } from "@/components/panels/event-timeline";
import { IODetail } from "@/components/panels/io-detail";
import { KpiTile } from "@/components/panels/kpi-tile";
import { LangfuseLink } from "@/components/panels/langfuse-link";
import { LangfuseSummaryCard } from "@/components/panels/langfuse-summary-card";
import { MetaListPanel } from "@/components/panels/meta-list-panel";
import { RawEnvelopePanel } from "@/components/panels/raw-envelope-panel";
import type { ComponentRegistry } from "@json-render/react";

export const panelsRegistry: ComponentRegistry = {
  KPI: ({ element }) => {
    const props = element.props as {
      label: string;
      data?: unknown;
      format?: "int" | "duration" | "cost" | "tokens" | "number" | "string";
      sub?: string;
    };
    return (
      <KpiTile
        label={props.label}
        value={props.data}
        format={props.format ?? "string"}
        sub={props.sub}
      />
    );
  },
  MetaList: ({ element }) => <MetaListPanel data={(element.props as { data?: unknown }).data} />,
  LangfuseLink: ({ element }) => (
    <LangfuseLink runId={(element.props as { runId?: string }).runId ?? null} />
  ),
  LangfuseSummaryCard: ({ element }) => {
    const p = element.props as { runId?: string; data?: unknown };
    return <LangfuseSummaryCard runId={p.runId ?? null} data={p.data} />;
  },
  EventTimeline: ({ element }) => {
    const p = element.props as { data?: unknown; kindFilter?: string };
    return <EventTimeline data={p.data} {...(p.kindFilter ? { kindFilter: p.kindFilter } : {})} />;
  },
  IODetail: ({ element }) => <IODetail data={(element.props as { data?: unknown }).data} />,
  RawEnvelope: () => <RawEnvelopePanel />,
};
