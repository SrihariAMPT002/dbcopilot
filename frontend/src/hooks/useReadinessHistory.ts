import { useQuery } from "@tanstack/react-query";
import { ReadinessService } from "@/services/readinessService";
import { queryKeys } from "@/lib/query-keys";

export function useReadinessHistory(
  databaseId?: number | null,
  filters?: { maturityLevel?: string | null; minScore?: number | null; maxScore?: number | null },
) {
  return useQuery({
    queryKey: queryKeys.readinessHistory(
      databaseId ?? "default",
      filters?.maturityLevel ?? "all",
      filters?.minScore ?? "all",
      filters?.maxScore ?? "all",
    ),
    queryFn: () => ReadinessService.getHistory(databaseId ?? 0, filters),
    enabled: typeof databaseId === "number" && databaseId > 0,
  });
}
