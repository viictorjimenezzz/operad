/**
 * Tab definitions for the multi-invocation Agent Group page.
 */
export interface GroupTabSpec {
  to: string;
  label: string;
  end?: boolean;
}

export function agentGroupTabs(hashContent: string): GroupTabSpec[] {
  const base = `/agents/${hashContent}`;
  return [
    { to: base, label: "Overview", end: true },
    { to: `${base}/runs`, label: "Invocations" },
    { to: `${base}/metrics`, label: "Metrics" },
    { to: `${base}/train`, label: "Train" },
    { to: `${base}/graph`, label: "Graph" },
  ];
}
