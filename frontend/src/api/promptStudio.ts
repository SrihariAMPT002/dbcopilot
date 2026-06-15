import { request } from "./client";
import type { PromptBundle, PromptInventoryItem, PromptTemplate } from "@/types/backend";

export const promptStudioApi = {
  templates: () => request<{ templates: PromptTemplate[] }>("/prompt-studio/templates"),
  inventory: () => request<{ prompts: PromptInventoryItem[] }>("/prompt-studio/inventory"),
  bundle: (databaseId: number) => request<PromptBundle>(`/prompt-studio/download-bundle/${databaseId}`),
};
