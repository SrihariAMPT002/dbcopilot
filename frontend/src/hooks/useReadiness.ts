import { useQuery } from "@tanstack/react-query";
import { ReadinessService } from "@/services/readinessService";
import { queryKeys } from "@/lib/query-keys";

export function useReadiness(databaseId?: number | null) {
  return useQuery({
    queryKey: queryKeys.readiness(databaseId ?? "default"),
    queryFn: () => ReadinessService.getSnapshot(Number(databaseId)),
    enabled: typeof databaseId === "number" && Number.isFinite(databaseId) && databaseId > 0,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });
}
