export function langfuseUrlFor(base: string, runId: string, spanId?: string): string {
  const b = base.replace(/\/$/, "");
  const url = `${b}/trace/${runId}`;
  return spanId ? `${url}?observation=${spanId}` : url;
}
