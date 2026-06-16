import {
  LayoutDashboard,
  PlugZap,
  Database,
  TableProperties,
  ShieldCheck,
  BookOpenText,
  Network,
  TrendingUp,
  Boxes,
  Sparkles,
  Gauge,
  Activity,
  ShieldAlert,
  Bot,
  Settings,
  type LucideIcon,
} from "lucide-react";

export type NavGroup = {
  label: string;
  items: { title: string; to: string; icon: LucideIcon; description?: string }[];
};

export const navGroups: NavGroup[] = [
  {
    label: "Overview",
    items: [
      { title: "Dashboard", to: "/", icon: LayoutDashboard },
    ],
  },
  {
    label: "Sources",
    items: [
      { title: "Connect Database", to: "/connect", icon: PlugZap },
      { title: "Connected Sources", to: "/sources", icon: Database },
      { title: "Database Explorer", to: "/explorer", icon: TableProperties },
    ],
  },
  {
    label: "Intelligence",
    items: [
      { title: "Governance", to: "/governance", icon: ShieldCheck },
      { title: "Semantics", to: "/semantics", icon: BookOpenText },
      { title: "Relationships", to: "/relationships", icon: Network },
      { title: "KPI", to: "/kpi", icon: TrendingUp },
    ],
  },
  {
    label: "AI Surface",
    items: [
      { title: "Embeddings & Retrieval", to: "/embeddings", icon: Boxes },
      { title: "Prompt Studio", to: "/prompt-studio", icon: Sparkles },
      { title: "AI Readiness", to: "/readiness", icon: Gauge },
    ],
  },
  {
    label: "Platform",
    items: [
      { title: "Jobs & Operations", to: "/jobs", icon: Activity },
      { title: "AI Observability", to: "/observability", icon: ShieldAlert },
      { title: "Agents", to: "/agents", icon: Bot },
      { title: "Settings", to: "/settings", icon: Settings },
    ],
  },
];

export const allNavItems = navGroups.flatMap((g) => g.items);
