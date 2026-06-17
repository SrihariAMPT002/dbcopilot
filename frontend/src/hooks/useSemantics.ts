import { useQuery } from "@tanstack/react-query";
import { SemanticService } from "@/services/semanticsService";

export function useSemantics(databaseId?: number | null) {
  return useQuery({
    queryKey: ["semantics", databaseId ?? "default"],
    queryFn: () => SemanticService.getPackage(Number(databaseId ?? 0)),
    enabled: typeof databaseId === "number" && databaseId > 0,
  });
}

export function useSemanticEvidence(databaseId?: number | null) {
  return useQuery({
    queryKey: ["semantic-evidence", databaseId ?? "default"],
    queryFn: () => SemanticService.getEvidence(Number(databaseId ?? 0)),
    enabled: typeof databaseId === "number" && databaseId > 0,
  });
}
