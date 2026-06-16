import { useQuery } from "@tanstack/react-query";
import { ReadinessService } from "@/services/readinessService";

export function useReadinessHistory(
  databaseId?: number | null,
  filters?: { maturityLevel?: string | null; minScore?: number | null; maxScore?: number | null },
) {
  return useQuery({
    queryKey: ["readiness-history", databaseId ?? "default", filters?.maturityLevel ?? "all", filters?.minScore ?? "all", filters?.maxScore ?? "all"],
    queryFn: () => ReadinessService.getHistory(databaseId ?? 0, filters),
    enabled: typeof databaseId === "number" && databaseId > 0,
  });
}
