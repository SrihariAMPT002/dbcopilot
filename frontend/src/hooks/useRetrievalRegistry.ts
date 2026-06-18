import { useQuery } from "@tanstack/react-query";
import { RetrievalMetricsService } from "@/services/retrievalMetricsService";
import { queryKeys } from "@/lib/query-keys";

export function useRetrievalRegistry() {
  return useQuery({
    queryKey: queryKeys.retrievalRegistry(),
    queryFn: () => RetrievalMetricsService.registry(),
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });
}
