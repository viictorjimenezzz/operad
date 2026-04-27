import { VerifierDetailOverview } from "@/components/algorithms/verifier/verifier-detail-overview";
import { VerifierIterations } from "@/components/algorithms/verifier/verifier-iterations";
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
  VerifierIterations: ({ element }) => {
    const p = element.props as { data?: unknown };
    return <VerifierIterations data={p.data} />;
  },
};
