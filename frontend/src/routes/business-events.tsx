import { createFileRoute } from "@tanstack/react-router";
import { BusinessEventsPage } from "@/pages/BusinessEventsPage";

export const Route = createFileRoute("/business-events")({
  head: () => ({ meta: [{ title: "Business Events â€” DBCopilot" }] }),
  component: BusinessEventsPage,
});
