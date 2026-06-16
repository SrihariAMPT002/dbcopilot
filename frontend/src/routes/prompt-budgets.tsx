import { createFileRoute } from "@tanstack/react-router";
import { PromptBudgetsPage } from "@/pages/PromptBudgetsPage";

export const Route = createFileRoute("/prompt-budgets")({
  head: () => ({ meta: [{ title: "Prompt Budgets — DBCopilot" }] }),
  component: PromptBudgetsPage,
});
