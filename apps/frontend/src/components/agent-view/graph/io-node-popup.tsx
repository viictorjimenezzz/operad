import { FieldRow } from "@/components/agent-view/graph/field-row";
import { Button } from "@/components/ui/button";
import type { IoTypeNode } from "@/lib/types";

interface IoNodePopupProps {
  node: IoTypeNode;
  agentPath: string;
  onValues: (attr: string) => void;
  onClose: () => void;
}

export function IoNodePopup({ node, agentPath, onValues, onClose }: IoNodePopupProps) {
  return (
    <dialog
      open
      className="absolute left-0 top-full z-20 mt-2 w-[300px] rounded border border-border bg-bg-1 p-2 shadow-xl"
    >
      <div className="mb-1 flex items-center justify-between">
        <div className="text-xs text-text">{node.name} fields</div>
        <Button variant="ghost" size="sm" className="h-5 px-1" onClick={onClose}>
          close
        </Button>
      </div>
      <div className="max-h-56 space-y-1 overflow-auto">
        {node.fields.map((field) => (
          <FieldRow
            key={`${node.key}:${field.name}`}
            name={field.name}
            type={field.type}
            description={field.description}
            system={field.system}
            onValues={() => onValues(field.name)}
          />
        ))}
      </div>
      <div className="mt-1 text-[10px] text-muted">agent path: {agentPath}</div>
    </dialog>
  );
}
