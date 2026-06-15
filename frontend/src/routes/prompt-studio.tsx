import { createFileRoute } from "@tanstack/react-router";
import { PromptStudioPage } from "@/pages/PromptStudioPage";

export const Route = createFileRoute("/prompt-studio")({
  head: () => ({ meta: [{ title: "Prompt Studio — DBCopilot" }] }),
  component: PromptStudioPage,
});
