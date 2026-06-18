import { useQuery } from "@tanstack/react-query";
import { RetrievalMetricsService } from "@/services/retrievalMetricsService";
import { queryKeys } from "@/lib/query-keys";

export function useRetrievalMetrics(databaseId?: number | null) {
  return useQuery({
    queryKey: queryKeys.retrievalMetrics(databaseId ?? "default"),
    queryFn: () => RetrievalMetricsService.get(databaseId ?? 0),
    enabled: typeof databaseId === "number" && databaseId > 0,
  });
}
