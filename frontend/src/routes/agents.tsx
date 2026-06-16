import { createFileRoute } from "@tanstack/react-router";
import { AgentsPage } from "@/pages/AgentsPage";

export const Route = createFileRoute("/agents")({
  head: () => ({ meta: [{ title: "Agents — DBCopilot" }] }),
  component: AgentsPage,
});
