import { createFileRoute } from "@tanstack/react-router";
import { ReadinessPage } from "@/pages/ReadinessPage";

export const Route = createFileRoute("/readiness")({
  head: () => ({ meta: [{ title: "AI Readiness — DBCopilot" }] }),
  component: ReadinessPage,
});
