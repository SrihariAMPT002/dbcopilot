import { promptStudioApi } from "@/api/promptStudio";

export const PromptStudioService = {
  getTemplates: promptStudioApi.templates,
  getInventory: promptStudioApi.inventory,
  getBundle: promptStudioApi.bundle,
};
