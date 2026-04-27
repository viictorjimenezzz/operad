/**
 * Tab definitions for the multi-invocation Agent Group page.
 */
export interface GroupTabSpec {
  to: string;
  label: string;
  end?: boolean;
}

export function agentGroupTabs(
  hashContent: string,
  options: { showTrain?: boolean } = {},
): GroupTabSpec[] {
  const base = `/agents/${hashContent}`;
  const tabs = [
    { to: base, label: "Overview", end: true },
    { to: `${base}/runs`, label: "Invocations" },
    { to: `${base}/metrics`, label: "Metrics" },
    { to: `${base}/graph`, label: "Graph" },
  ];
  if (options.showTrain) {
    tabs.splice(3, 0, { to: `${base}/train`, label: "Train" });
  }
  return tabs;
}
