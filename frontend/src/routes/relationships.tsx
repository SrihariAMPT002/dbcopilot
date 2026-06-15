import { createFileRoute } from "@tanstack/react-router";
import { RelationshipsPage } from "@/pages/RelationshipsPage";

export const Route = createFileRoute("/relationships")({
  head: () => ({ meta: [{ title: "Relationship Intelligence — DBCopilot" }] }),
  component: RelationshipsPage,
});
