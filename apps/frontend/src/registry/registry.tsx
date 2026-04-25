import { AgentGraph } from "@/shared/charts/agent-graph";
import { BeamCandidateChart } from "@/shared/charts/beam-candidate-chart";
import { CheckpointTimeline } from "@/shared/charts/checkpoint-timeline";
import { DebateRoundView } from "@/shared/charts/debate-round-view";
import { DriftTimeline } from "@/shared/charts/drift-timeline";
import { FitnessCurve } from "@/shared/charts/fitness-curve";
import { GradientLog } from "@/shared/charts/gradient-log";
import { LrScheduleCurve } from "@/shared/charts/lr-schedule-curve";
import { MutationHeatmap } from "@/shared/charts/mutation-heatmap";
import { OpSuccessTable } from "@/shared/charts/op-success-table";
import { PopulationScatter } from "@/shared/charts/population-scatter";
import { TrainingLossCurve } from "@/shared/charts/training-loss-curve";
import { TrainingProgress } from "@/shared/charts/training-progress";
import { EventTimeline } from "@/shared/panels/event-timeline";
import { IODetail } from "@/shared/panels/io-detail";
import { KpiTile } from "@/shared/panels/kpi-tile";
import { LangfuseLink } from "@/shared/panels/langfuse-link";
import { MetaListPanel } from "@/shared/panels/meta-list-panel";
import { RawEnvelopePanel } from "@/shared/panels/raw-envelope-panel";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { TabsContent, TabsList, TabsTrigger, Tabs as UITabs } from "@/shared/ui/tabs";
/**
 * Registry: name -> ComponentRenderer. Each renderer reads the
 * resolved-prop bag forwarded by <DashboardRenderer />, casts it to
 * the right shape, and delegates to the actual chart/panel under
 * src/shared/.
 *
 * The cast is `as unknown as <Shape>` because @json-render's
 * ComponentRenderer prop type is `Record<string, unknown>` — we
 * already validated the shape at the catalog layer (Zod parse) and
 * at the layout-schema layer.
 */
import type { ComponentRegistry } from "@json-render/react";

export const registry: ComponentRegistry = {
  Card: ({ element, children }) => {
    const title = (element.props as { title?: string }).title;
    return (
      <Card>
        {title ? (
          <CardHeader>
            <CardTitle>{title}</CardTitle>
          </CardHeader>
        ) : null}
        <CardContent>{children}</CardContent>
      </Card>
    );
  },
  Row: ({ element, children }) => {
    const gap = (element.props as { gap?: number }).gap ?? 12;
    return (
      <div className="flex flex-wrap gap-3 [&>*]:min-w-0 [&>*]:flex-1" style={{ gap }}>
        {children}
      </div>
    );
  },
  Col: ({ element, children }) => {
    const gap = (element.props as { gap?: number }).gap ?? 12;
    return (
      <div className="flex flex-col" style={{ gap }}>
        {children}
      </div>
    );
  },
  Tabs: ({ element, children }) => {
    const tabs = (element.props as { tabs: Array<{ id: string; label: string }> }).tabs;
    const firstTab = tabs[0]?.id ?? "tab-0";
    const childArray = Array.isArray(children) ? children : [children];
    return (
      <UITabs defaultValue={firstTab} className="flex h-full flex-col">
        <TabsList>
          {tabs.map((t) => (
            <TabsTrigger key={t.id} value={t.id}>
              {t.label}
            </TabsTrigger>
          ))}
        </TabsList>
        {tabs.map((t, i) => (
          <TabsContent key={t.id} value={t.id} className="flex-1 overflow-auto">
            {childArray[i]}
          </TabsContent>
        ))}
      </UITabs>
    );
  },

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

  FitnessCurve: ({ element }) => {
    const p = element.props as { data?: unknown; height?: number };
    return <FitnessCurve data={p.data} height={p.height ?? 220} />;
  },
  PopulationScatter: ({ element }) => {
    const p = element.props as { data?: unknown; height?: number };
    return <PopulationScatter data={p.data} height={p.height ?? 220} />;
  },
  MutationHeatmap: ({ element }) => (
    <MutationHeatmap data={(element.props as { data?: unknown }).data} />
  ),
  OpSuccessTable: ({ element }) => (
    <OpSuccessTable data={(element.props as { data?: unknown }).data} />
  ),
  TrainingProgress: ({ element }) => (
    <TrainingProgress data={(element.props as { data?: unknown }).data} />
  ),
  TrainingLossCurve: ({ element }) => {
    const p = element.props as { data?: unknown; dataCheckpoint?: unknown; height?: number };
    return <TrainingLossCurve data={p.data} checkpointData={p.dataCheckpoint} height={p.height ?? 220} />;
  },
  DriftTimeline: ({ element }) => (
    <DriftTimeline data={(element.props as { data?: unknown }).data} />
  ),
  DebateRoundView: ({ element }) => (
    <DebateRoundView data={(element.props as { data?: unknown }).data} />
  ),
  BeamCandidateChart: ({ element }) => {
    const p = element.props as { data?: unknown; height?: number };
    return <BeamCandidateChart data={p.data} height={p.height ?? 220} />;
  },
  GradientLog: ({ element }) => (
    <GradientLog data={(element.props as { data?: unknown }).data} />
  ),
  LrScheduleCurve: ({ element }) => {
    const p = element.props as { data?: unknown; height?: number };
    return <LrScheduleCurve data={p.data} height={p.height ?? 220} />;
  },
  CheckpointTimeline: ({ element }) => (
    <CheckpointTimeline data={(element.props as { data?: unknown }).data} />
  ),
  AgentGraph: ({ element }) => {
    const p = element.props as { data?: unknown; dataMutations?: unknown };
    return <AgentGraph data={p.data} mutations={p.dataMutations} />;
  },

  EventTimeline: ({ element }) => {
    const p = element.props as { data?: unknown; kindFilter?: string };
    return <EventTimeline data={p.data} {...(p.kindFilter ? { kindFilter: p.kindFilter } : {})} />;
  },
  IODetail: ({ element }) => <IODetail data={(element.props as { data?: unknown }).data} />,
  RawEnvelope: () => <RawEnvelopePanel />,
};
