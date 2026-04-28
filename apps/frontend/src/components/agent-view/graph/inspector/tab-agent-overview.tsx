import { Eyebrow } from "@/components/ui";
import { useAgentMeta } from "@/hooks/use-runs";

type SchemaField = {
  name: string;
  type?: string | undefined;
  description?: string | undefined;
  system?: boolean | undefined;
  has_default?: boolean | undefined;
  default?: unknown;
};

type TypeSchema = {
  key: string;
  name: string;
  fields: SchemaField[];
};

export function TabAgentOverview({ runId, agentPath }: { runId: string; agentPath: string }) {
  const meta = useAgentMeta(runId, agentPath);

  if (meta.isLoading) {
    return <div className="p-5 text-[12px] text-muted-2">loading…</div>;
  }
  if (meta.error || !meta.data) {
    return <div className="p-5 text-[12px] text-[--color-err]">failed to load metadata</div>;
  }

  const inputSchema = coerceTypeSchema(meta.data.input_schema);
  const outputSchema = coerceTypeSchema(meta.data.output_schema);

  return (
    <div className="space-y-4 p-5">
      <SchemaSummary title="input" schema={inputSchema} />
      <SchemaSummary title="output" schema={outputSchema} />
    </div>
  );
}

function SchemaSummary({ title, schema }: { title: string; schema: TypeSchema | null }) {
  return (
    <section className="rounded-md border border-border bg-bg-2">
      <div className="border-b border-border/60 px-3 py-2">
        <Eyebrow>{title}</Eyebrow>
      </div>
      {schema ? (
        <div className="space-y-4 px-3 py-3">
          <div className="space-y-2">
            <MetaLine label="key" value={schema.key} mono />
            <MetaLine label="name" value={schema.name} />
          </div>
          <div>
            <div className="mb-2 text-[10px] font-medium uppercase tracking-[0.08em] text-muted">
              fields
            </div>
            {schema.fields.length > 0 ? (
              <ul className="space-y-3">
                {schema.fields.map((field) => (
                  <FieldLine key={field.name} field={field} />
                ))}
              </ul>
            ) : (
              <div className="text-[12px] text-muted-2">no fields</div>
            )}
          </div>
        </div>
      ) : (
        <div className="px-3 py-3 text-[12px] text-muted-2">no schema captured</div>
      )}
    </section>
  );
}

function MetaLine({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div>
      <div className="text-[10px] font-medium uppercase tracking-[0.08em] text-muted-2">
        {label}
      </div>
      <div
        className={mono ? "break-all font-mono text-[11px] text-muted" : "text-[13px] text-text"}
      >
        {value || "—"}
      </div>
    </div>
  );
}

function FieldLine({ field }: { field: SchemaField }) {
  const system = Boolean(field.system);
  const description = field.description?.trim() || "No description.";

  return (
    <li className="border-l border-border pl-3">
      <div className="flex items-center gap-2 text-[10px] font-medium uppercase tracking-[0.08em]">
        <span
          aria-hidden
          className={
            system ? "h-2 w-2 rounded-full bg-[--color-warn]" : "h-2 w-2 rounded-full bg-accent"
          }
        />
        <span className={system ? "text-[--color-warn]" : "text-accent"}>
          {system ? "system" : "user"}
        </span>
      </div>
      <div className="mt-1 text-[12px] leading-5 text-muted">
        <span className="font-mono text-[13px] font-medium text-text">{field.name}</span>{" "}
        <span className="font-mono text-[11px] text-muted-2">
          &lt;{field.type || "unknown"}&gt;
        </span>
        {": "}
        <span>{description}</span>
      </div>
      {field.has_default ? (
        <div className="mt-1 font-mono text-[11px] text-muted-2">
          default {formatDefault(field.default)}
        </div>
      ) : null}
    </li>
  );
}

function coerceTypeSchema(raw: unknown): TypeSchema | null {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return null;
  const obj = raw as Record<string, unknown>;
  const key = typeof obj.key === "string" ? obj.key : "";
  const name = typeof obj.name === "string" ? obj.name : (key.split(".").at(-1) ?? "");
  const rawFields = Array.isArray(obj.fields) ? obj.fields : [];
  const fields = rawFields.flatMap((field) => {
    if (!field || typeof field !== "object" || Array.isArray(field)) return [];
    const row = field as Record<string, unknown>;
    const fieldName = typeof row.name === "string" ? row.name : null;
    if (!fieldName) return [];
    return [
      {
        name: fieldName,
        type: typeof row.type === "string" ? row.type : undefined,
        description: typeof row.description === "string" ? row.description : undefined,
        system: typeof row.system === "boolean" ? row.system : undefined,
        has_default: typeof row.has_default === "boolean" ? row.has_default : undefined,
        default: row.default,
      },
    ];
  });
  return { key, name, fields };
}

function formatDefault(value: unknown): string {
  if (value === undefined) return "undefined";
  if (typeof value === "string") return JSON.stringify(value);
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}
