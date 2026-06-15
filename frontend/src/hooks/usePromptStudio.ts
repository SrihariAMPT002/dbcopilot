import { useQuery } from "@tanstack/react-query";
import { PromptStudioService } from "@/services/promptStudioService";

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
