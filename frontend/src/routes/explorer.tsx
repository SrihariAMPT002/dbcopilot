import { createFileRoute } from "@tanstack/react-router";
import { ExplorerPage } from "@/pages/ExplorerPage";

export const Route = createFileRoute("/explorer")({
  head: () => ({ meta: [{ title: "Database Explorer — DBCopilot" }] }),
  component: ExplorerPage,
});
