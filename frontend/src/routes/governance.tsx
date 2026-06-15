import { createFileRoute } from "@tanstack/react-router";
import { GovernancePage } from "@/pages/GovernancePage";

export const Route = createFileRoute("/governance")({
  head: () => ({ meta: [{ title: "Governance Intelligence — DBCopilot" }] }),
  component: GovernancePage,
});
