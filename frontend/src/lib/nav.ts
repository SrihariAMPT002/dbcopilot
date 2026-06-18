import { type LucideIcon } from "lucide-react";
import { moduleRegistry } from "@/lib/module-registry";

export type NavGroup = {
  label: string;
  items: { title: string; to: string; icon: LucideIcon; description?: string }[];
};

export const navGroups: NavGroup[] = [
  {
    label: "Overview",
    items: [
      { title: moduleRegistry.dashboard.label, to: moduleRegistry.dashboard.route, icon: moduleRegistry.dashboard.icon },
    ],
  },
  {
    label: "Sources",
    items: [
      { title: moduleRegistry.connect.label, to: moduleRegistry.connect.route, icon: moduleRegistry.connect.icon },
      { title: moduleRegistry.sources.label, to: moduleRegistry.sources.route, icon: moduleRegistry.sources.icon },
      { title: moduleRegistry.explorer.label, to: moduleRegistry.explorer.route, icon: moduleRegistry.explorer.icon },
    ],
  },
  {
    label: "Intelligence",
    items: [
      { title: moduleRegistry.governance.label, to: moduleRegistry.governance.route, icon: moduleRegistry.governance.icon },
      { title: moduleRegistry.semantics.label, to: moduleRegistry.semantics.route, icon: moduleRegistry.semantics.icon },
      { title: moduleRegistry.relationships.label, to: moduleRegistry.relationships.route, icon: moduleRegistry.relationships.icon },
      { title: moduleRegistry.kpi.label, to: moduleRegistry.kpi.route, icon: moduleRegistry.kpi.icon },
    ],
  },
  {
    label: "AI Surface",
    items: [
      { title: moduleRegistry.embeddings.label, to: moduleRegistry.embeddings.route, icon: moduleRegistry.embeddings.icon },
      { title: moduleRegistry["prompt-studio"].label, to: moduleRegistry["prompt-studio"].route, icon: moduleRegistry["prompt-studio"].icon },
      { title: moduleRegistry["business-intelligence"].label, to: moduleRegistry["business-intelligence"].route, icon: moduleRegistry["business-intelligence"].icon },
      { title: moduleRegistry.readiness.label, to: moduleRegistry.readiness.route, icon: moduleRegistry.readiness.icon },
    ],
  },
  {
    label: "Platform",
    items: [
      { title: moduleRegistry.jobs.label, to: moduleRegistry.jobs.route, icon: moduleRegistry.jobs.icon },
      { title: moduleRegistry["business-events"].label, to: moduleRegistry["business-events"].route, icon: moduleRegistry["business-events"].icon },
      { title: moduleRegistry.observability.label, to: moduleRegistry.observability.route, icon: moduleRegistry.observability.icon },
      { title: moduleRegistry.agents.label, to: moduleRegistry.agents.route, icon: moduleRegistry.agents.icon },
      { title: moduleRegistry.settings.label, to: moduleRegistry.settings.route, icon: moduleRegistry.settings.icon },
    ],
  },
];

export const allNavItems = navGroups.flatMap((g) => g.items);
