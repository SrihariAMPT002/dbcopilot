import { promptStudioApi } from "@/api/promptStudio";

export const PromptStudioService = {
  getTemplates: promptStudioApi.templates,
  getInventory: promptStudioApi.inventory,
  getBundle: promptStudioApi.bundle,
  generate: promptStudioApi.generate,
  getPackages: promptStudioApi.packages,
  getVersions: promptStudioApi.versions,
  getObservability: promptStudioApi.observability,
  optimize: promptStudioApi.optimize,
  evaluate: promptStudioApi.evaluate,
};
