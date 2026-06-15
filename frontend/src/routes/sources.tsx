import { createFileRoute } from "@tanstack/react-router";
import { SourcesPage } from "@/pages/SourcesPage";

export const Route = createFileRoute("/sources")({
  head: () => ({ meta: [{ title: "Connected Sources — DBCopilot" }] }),
  component: SourcesPage,
});
