import { VerifierAcceptanceTab } from "@/components/algorithms/verifier/acceptance-tab";
import { VerifierDetailOverview } from "@/components/algorithms/verifier/verifier-detail-overview";
import { VerifierIterationsTab } from "@/components/algorithms/verifier/iterations-tab";
import type { ComponentRegistry } from "@json-render/react";

export const verifierRegistry: ComponentRegistry = {
  VerifierDetailOverview: ({ element }) => {
    const p = element.props as {
      dataSummary?: unknown;
      dataIterations?: unknown;
      runId?: string;
    };
    return (
      <VerifierDetailOverview
        dataSummary={p.dataSummary}
        dataIterations={p.dataIterations}
        runId={p.runId ?? ""}
      />
    );
  },
  VerifierIterationsTab: ({ element }) => {
    const p = element.props as { data?: unknown };
    return <VerifierIterationsTab data={p.data} />;
  },
  VerifierAcceptanceTab: ({ element }) => {
    const p = element.props as { data?: unknown };
    return <VerifierAcceptanceTab data={p.data} />;
  },
};
