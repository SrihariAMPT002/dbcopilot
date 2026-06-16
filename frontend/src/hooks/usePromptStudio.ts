import { useQuery } from "@tanstack/react-query";
import { useMutation } from "@tanstack/react-query";
import { PromptStudioService } from "@/services/promptStudioService";
import type { PromptGenerationRequest } from "@/types/backend";

export function usePromptTemplates() {
  return useQuery({
    queryKey: ["prompt-templates"],
    queryFn: PromptStudioService.getTemplates,
  });
}

export function usePromptInventory() {
  return useQuery({
    queryKey: ["prompt-inventory"],
    queryFn: PromptStudioService.getInventory,
  });
}

export function usePromptBundle(databaseId: number) {
  return useQuery({
    queryKey: ["prompt-bundle", databaseId],
    queryFn: () => PromptStudioService.getBundle(databaseId),
  });
}

export function useGeneratePrompt() {
  return useMutation({
    mutationFn: (payload: PromptGenerationRequest) => PromptStudioService.generate(payload),
  });
}

export function usePromptPackages(databaseId: number) {
  return useQuery({
    queryKey: ["prompt-packages", databaseId],
    queryFn: () => PromptStudioService.getPackages(databaseId),
  });
}

export function usePromptVersions(promptPackageId: number | null) {
  return useQuery({
    queryKey: ["prompt-versions", promptPackageId],
    queryFn: () => PromptStudioService.getVersions(promptPackageId as number),
    enabled: promptPackageId !== null,
  });
}

export function usePromptObservability(promptPackageId: number | null) {
  return useQuery({
    queryKey: ["prompt-observability", promptPackageId],
    queryFn: () => PromptStudioService.getObservability(promptPackageId as number),
    enabled: promptPackageId !== null,
  });
}

export function useOptimizePrompt() {
  return useMutation({
    mutationFn: (payload: { prompt_package_id: number }) => PromptStudioService.optimize(payload),
  });
}

export function useEvaluatePrompt() {
  return useMutation({
    mutationFn: (payload: { prompt_package_id: number }) => PromptStudioService.evaluate(payload),
  });
}
