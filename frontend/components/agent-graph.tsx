"use client";
import { useMemo } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  Handle,
  Position,
  MarkerType,
  type NodeProps,
  type Node,
  type Edge,
} from "@xyflow/react";
import {
  BrainCircuit,
  Search,
  Compass,
  PenLine,
  ShieldCheck,
  ScanText,
  Palette,
  ChartNoAxesCombined,
  ScanLine,
  PackageCheck,
  UserRoundCheck,
  Check,
  Loader2,
  AlertTriangle,
  Clock3,
} from "lucide-react";
import type { Detail, Execution } from "@/lib/api";
import { duration } from "@/lib/api";
export const agentMeta = [
  {
    id: "supervisor",
    name: "Supervisor",
    role: "Orchestrate the campaign",
    icon: BrainCircuit,
    color: "#a78bfa",
    x: 0,
    y: 0,
  },
  {
    id: "research",
    name: "Research",
    role: "Collect source evidence",
    icon: Search,
    color: "#68b7ff",
    x: 240,
    y: 0,
  },
  {
    id: "strategy",
    name: "Strategy",
    role: "Shape the narrative",
    icon: Compass,
    color: "#a78bfa",
    x: 480,
    y: 0,
  },
  {
    id: "writer",
    name: "Writer",
    role: "Create channel drafts",
    icon: PenLine,
    color: "#68b7ff",
    x: 480,
    y: 165,
  },
  {
    id: "fact_checker",
    name: "Fact Checker",
    role: "Trace claims to evidence",
    icon: ShieldCheck,
    color: "#42d6c4",
    x: 240,
    y: 165,
  },
  {
    id: "editor",
    name: "Editor",
    role: "Refine every sentence",
    icon: ScanText,
    color: "#a78bfa",
    x: 0,
    y: 165,
  },
  {
    id: "brand",
    name: "Brand Guardian",
    role: "Keep your voice consistent",
    icon: Palette,
    color: "#f4a7d0",
    x: 0,
    y: 330,
  },
  {
    id: "seo",
    name: "SEO & Channels",
    role: "Adapt for each platform",
    icon: ChartNoAxesCombined,
    color: "#fbbf24",
    x: 240,
    y: 330,
  },
  {
    id: "quality",
    name: "Quality",
    role: "Evaluate and improve",
    icon: ScanLine,
    color: "#42d6c4",
    x: 480,
    y: 330,
  },
  {
    id: "human",
    name: "Human Review",
    role: "Your final editorial say",
    icon: UserRoundCheck,
    color: "#fbbf24",
    x: 480,
    y: 495,
  },
  {
    id: "export",
    name: "Export & Publishing",
    role: "Package approved content",
    icon: PackageCheck,
    color: "#68b7ff",
    x: 240,
    y: 495,
  },
];
type AgentData = {
  agent: string;
  execution?: Execution;
  status: string;
  selectedAgent: boolean;
  revision: number;
};
function AgentNode({ data }: NodeProps<Node<AgentData>>) {
  const meta = agentMeta.find((a) => a.id === data.agent)!;
  const Icon = meta.icon;
  return (
    <div
      className={`agent-node ${data.status} ${data.selectedAgent ? "selected" : ""}`}
      data-testid={`agent-${data.agent}`}
    >
      <Handle type="target" position={Position.Top} />
      <div className="agent-node-top">
        <span
          className="agent-icon"
          style={{ color: meta.color, background: `${meta.color}16` }}
        >
          <Icon size={18} />
        </span>
        <span className="node-status">
          {data.status === "completed" ? (
            <Check size={12} />
          ) : data.status === "running" ? (
            <Loader2 size={12} className="spin" />
          ) : data.status === "failed" ? (
            <AlertTriangle size={12} />
          ) : (
            <span className="status-dot" />
          )}
          {data.status === "pending"
            ? "Waiting"
            : data.status === "awaiting_approval"
              ? "Review needed"
              : data.status}
        </span>
      </div>
      <strong>{meta.name}</strong>
      <p>{meta.role}</p>
      <div className="node-bottom">
        <span>
          <span className="io-dot" /> IN <span className="io-dot out" /> OUT
        </span>
        <span>
          <Clock3 size={10} />
          {data.execution ? duration(data.execution.duration_ms) : "—"}
        </span>
      </div>
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
}
const nodeTypes = { agent: AgentNode };
const connections = [
  ["supervisor", "research"],
  ["supervisor", "strategy"],
  ["research", "writer"],
  ["strategy", "writer"],
  ["writer", "fact_checker"],
  ["fact_checker", "editor"],
  ["editor", "brand"],
  ["brand", "seo"],
  ["seo", "quality"],
  ["quality", "human"],
  ["human", "export"],
];
export default function AgentGraph({
  run,
  selected = "supervisor",
  onSelect = () => {},
  preview = false,
}: {
  run?: Detail;
  selected?: string;
  onSelect?: (id: string) => void;
  preview?: boolean;
}) {
  const executions = useMemo(
    () => Object.fromEntries((run?.executions || []).map((e) => [e.agent, e])),
    [run],
  );
  const nodes: Node<AgentData>[] = agentMeta.map((meta) => {
    let status = executions[meta.id]?.status || "pending";
    if (meta.id === "human")
      status =
        run?.status === "awaiting_approval"
          ? "awaiting_approval"
          : run?.reviews?.some((r) => r.decision === "approve")
            ? "completed"
            : "pending";
    return {
      id: meta.id,
      type: "agent",
      position: { x: meta.x, y: meta.y },
      data: {
        agent: meta.id,
        execution: executions[meta.id],
        status,
        selectedAgent: selected === meta.id,
        revision: run?.revision || 0,
      },
    };
  });
  const edges: Edge[] = connections.map(([source, target]) => ({
    id: `${source}-${target}`,
    source,
    target,
    type: "smoothstep",
    animated: executions[target]?.status === "running",
    markerEnd: {
      type: MarkerType.ArrowClosed,
      width: 12,
      height: 12,
      color: "#506687",
    },
    style: {
      stroke:
        executions[target]?.status === "running"
          ? "#68b7ff"
          : executions[source]?.status === "completed"
            ? "#3b7c73"
            : "#34435c",
      strokeWidth: 1.5,
    },
  }));
  if (run?.revision)
    edges.push({
      id: "revision",
      source: "quality",
      target: "writer",
      type: "smoothstep",
      label: `Revision ${run.revision}`,
      animated: executions.writer?.status === "running",
      style: { stroke: "#fbbf24", strokeDasharray: "5 5" },
      labelStyle: { fill: "#fbbf24", fontSize: 11 },
      labelBgStyle: { fill: "#121826" },
    });
  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      fitView
      fitViewOptions={{ padding: 0.08 }}
      minZoom={0.25}
      maxZoom={1.5}
      onNodeClick={(_, node) => onSelect(node.id)}
      nodesDraggable={!preview}
      proOptions={{ hideAttribution: true }}
      colorMode="dark"
    >
      <Background color="#2c3650" gap={22} size={1} />
      {!preview && (
        <>
          <Controls showInteractive={false} />
          <MiniMap
            pannable
            zoomable
            nodeColor="#314663"
            maskColor="#080b12aa"
          />
        </>
      )}
    </ReactFlow>
  );
}
