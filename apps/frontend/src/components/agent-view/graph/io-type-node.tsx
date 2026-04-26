import { IoNodePopup } from "@/components/agent-view/graph/io-node-popup";
import { useUIStore } from "@/stores";
import { Handle, type NodeProps, Position } from "@xyflow/react";

type IoNodeData = {
  label: string;
  fields: Array<{ name: string; type: string; description: string; system: boolean }>;
  agentPath: string;
  selected: boolean;
  dimmed: boolean;
  onSelect: () => void;
  onClose: () => void;
};

export function IoTypeNode({ data }: NodeProps) {
  const nodeData = data as IoNodeData;
  const openDrawer = useUIStore((s) => s.openDrawer);

  return (
    <button
      type="button"
      aria-label={`I/O type node ${nodeData.label}`}
      className={`relative min-w-[200px] rounded-xl border px-3 py-2 text-left shadow ${nodeData.dimmed ? "opacity-35" : "opacity-100"} border-border bg-bg-2`}
      onClick={nodeData.onSelect}
    >
      <Handle type="target" position={Position.Left} />
      <Handle type="source" position={Position.Right} />
      <div className="font-mono text-sm text-text">{nodeData.label}</div>
      <div className="text-[11px] text-muted">{nodeData.fields.length} fields</div>
      {nodeData.selected ? (
        <IoNodePopup
          node={{ key: nodeData.label, name: nodeData.label, fields: nodeData.fields }}
          agentPath={nodeData.agentPath}
          onValues={(attr) =>
            openDrawer("values", { agentPath: nodeData.agentPath, attr, side: "in" })
          }
          onClose={nodeData.onClose}
        />
      ) : null}
    </button>
  );
}
