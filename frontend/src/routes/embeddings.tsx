import { createFileRoute } from "@tanstack/react-router";
import { EmbeddingsPage } from "@/pages/EmbeddingsPage";

export const Route = createFileRoute("/embeddings")({
  head: () => ({ meta: [{ title: "Embeddings & Retrieval — DBCopilot" }] }),
  component: EmbeddingsPage,
});
