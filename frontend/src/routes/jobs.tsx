import { createFileRoute } from "@tanstack/react-router";
import { JobsPage } from "@/pages/JobsPage";

export const Route = createFileRoute("/jobs")({
  head: () => ({ meta: [{ title: "Jobs & Operations — DBCopilot" }] }),
  component: JobsPage,
});
