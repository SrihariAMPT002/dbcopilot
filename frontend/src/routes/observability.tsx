import { createFileRoute } from "@tanstack/react-router";
import { ObservabilityPage } from "@/pages/ObservabilityPage";

export const Route = createFileRoute("/observability")({
  head: () => ({ meta: [{ title: "AI Observability — DBCopilot" }] }),
  component: ObservabilityPage,
});
