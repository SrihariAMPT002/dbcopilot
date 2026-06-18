import { useQuery } from "@tanstack/react-query";
import { RetrievalMetricsService } from "@/services/retrievalMetricsService";

export function useRetrievalMetrics(databaseId?: number | null) {
  return useQuery({
    queryKey: ["retrieval", "metrics", databaseId ?? "default"],
    queryFn: () => RetrievalMetricsService.get(databaseId ?? 0),
    enabled: typeof databaseId === "number" && databaseId > 0,
  });
}
