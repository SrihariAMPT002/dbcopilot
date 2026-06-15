import { createFileRoute } from "@tanstack/react-router";
import { SemanticsPage } from "@/pages/SemanticsPage";

export const Route = createFileRoute("/semantics")({
  head: () => ({ meta: [{ title: "Semantic Intelligence — DBCopilot" }] }),
  component: SemanticsPage,
});
