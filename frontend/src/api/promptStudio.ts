import { request } from "./client";
import type {
  PromptBundle,
  PromptGenerationRequest,
  PromptGenerationResponse,
  PromptInventoryItem,
  PromptPackageListResponse,
  PromptTemplate,
  PromptVersionListResponse,
  PromptObservabilityListResponse,
  PromptEvaluation,
  PromptOptimizationRequest,
  PromptEvaluationRequest,
} from "@/types/backend";

export const promptStudioApi = {
  templates: () => request<{ templates: PromptTemplate[] }>("/prompt-studio/templates"),
  inventory: () => request<{ prompts: PromptInventoryItem[] }>("/prompt-studio/inventory"),
  bundle: (databaseId: number) => request<PromptBundle>(`/prompt-studio/download-bundle/${databaseId}`),
  generate: (payload: PromptGenerationRequest) =>
    request<PromptGenerationResponse>("/prompt-studio/generate", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  packages: (databaseId: number) => request<PromptPackageListResponse>(`/prompt-studio/${databaseId}`),
  versions: (promptPackageId: number) => request<PromptVersionListResponse>(`/prompt-studio/${promptPackageId}/versions`),
  observability: (promptPackageId: number) =>
    request<PromptObservabilityListResponse>(`/prompt-studio/${promptPackageId}/observability`),
  optimize: (payload: PromptOptimizationRequest) =>
    request<PromptGenerationResponse>("/prompt-studio/optimize", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  evaluate: (payload: PromptEvaluationRequest) =>
    request<PromptEvaluation>("/prompt-studio/evaluate", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};
