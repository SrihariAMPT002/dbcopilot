import {
  Activity,
  ArrowRight,
  BarChart3,
  BookOpenText,
  Bot,
  Boxes,
  Database,
  Gauge,
  LayoutDashboard,
  Network,
  Settings,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  TableProperties,
  TrendingUp,
  type LucideIcon,
} from "lucide-react";

export type ModuleKey =
  | "dashboard"
  | "governance"
  | "semantics"
  | "relationships"
  | "kpi"
  | "prompt-studio"
  | "embeddings"
  | "retrieval"
  | "agent-memory"
  | "business-intelligence"
  | "business-events"
  | "observability"
  | "readiness"
  | "jobs"
  | "sources"
  | "connect"
  | "explorer"
  | "settings"
  | "agents";

export type ModuleRegistryItem = {
  key: ModuleKey;
  label: string;
  route: string;
  icon: LucideIcon;
  apiBase?: string;
  owner?: string;
};

export const moduleRegistry: Record<ModuleKey, ModuleRegistryItem> = {
  dashboard: { key: "dashboard", label: "Dashboard", route: "/", icon: LayoutDashboard, owner: "platform" },
  governance: { key: "governance", label: "Governance", route: "/governance", icon: ShieldCheck, owner: "intelligence" },
  semantics: { key: "semantics", label: "Semantics", route: "/semantics", icon: BookOpenText, owner: "intelligence" },
  relationships: { key: "relationships", label: "Relationships", route: "/relationships", icon: Network, owner: "intelligence" },
  kpi: { key: "kpi", label: "KPI", route: "/kpi", icon: TrendingUp, owner: "intelligence" },
  "prompt-studio": { key: "prompt-studio", label: "Prompt Studio", route: "/prompt-studio", icon: Sparkles, owner: "ai-surface" },
  embeddings: { key: "embeddings", label: "Embeddings & Retrieval", route: "/embeddings", icon: Boxes, owner: "ai-surface" },
  retrieval: { key: "retrieval", label: "Retrieval", route: "/retrieval", icon: Boxes, owner: "ai-surface" },
  "agent-memory": { key: "agent-memory", label: "Agent Memory", route: "/agents", icon: Bot, owner: "ai-surface" },
  "business-intelligence": { key: "business-intelligence", label: "Business Intelligence", route: "/business-intelligence", icon: BarChart3, owner: "ai-surface" },
  "business-events": { key: "business-events", label: "Business Events", route: "/business-events", icon: ArrowRight, owner: "platform" },
  observability: { key: "observability", label: "AI Observability", route: "/observability", icon: ShieldAlert, owner: "platform" },
  readiness: { key: "readiness", label: "AI Readiness", route: "/readiness", icon: Gauge, owner: "platform" },
  jobs: { key: "jobs", label: "Jobs & Operations", route: "/jobs", icon: Activity, owner: "platform" },
  sources: { key: "sources", label: "Connected Sources", route: "/sources", icon: Database, owner: "sources" },
  connect: { key: "connect", label: "Connect Database", route: "/connect", icon: Database, owner: "sources" },
  explorer: { key: "explorer", label: "Database Explorer", route: "/explorer", icon: TableProperties, owner: "sources" },
  settings: { key: "settings", label: "Settings", route: "/settings", icon: Settings, owner: "platform" },
  agents: { key: "agents", label: "Agents", route: "/agents", icon: Bot, owner: "platform" },
};

export const moduleRouteRegistry = Object.values(moduleRegistry).map(({ key, route, label, icon }) => ({ key, route, label, icon }));
