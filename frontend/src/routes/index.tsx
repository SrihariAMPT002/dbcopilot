import { createFileRoute } from "@tanstack/react-router";
import { DashboardPage } from "@/pages/DashboardPage";

export const Route = createFileRoute("/")({
  head: () => ({ meta: [{ title: "Dashboard — DBCopilot" }, { name: "description", content: "Operational overview of connected databases, sync jobs, AI intelligence coverage, and platform readiness." }] }),
  component: DashboardPage,
});
