import { useQuery } from "@tanstack/react-query";
import { SemanticService } from "@/services/semanticsService";

export function useSemantics(databaseId: number) {
  return useQuery({
    queryKey: ["semantics", databaseId],
    queryFn: () => SemanticService.getPackage(databaseId),
  });
}
