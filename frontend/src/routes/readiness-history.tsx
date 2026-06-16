import { createFileRoute } from "@tanstack/react-router";
import { ReadinessHistoryPage } from "@/pages/ReadinessHistoryPage";

export const Route = createFileRoute("/readiness-history")({
  head: () => ({ meta: [{ title: "Readiness History — DBCopilot" }] }),
  component: ReadinessHistoryPage,
});
