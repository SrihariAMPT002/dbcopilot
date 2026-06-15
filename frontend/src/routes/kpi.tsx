import { createFileRoute } from "@tanstack/react-router";
import { KPIPage } from "@/pages/KPIPage";

export const Route = createFileRoute("/kpi")({
  head: () => ({ meta: [{ title: "KPI Intelligence — DBCopilot" }] }),
  component: KPIPage,
});
