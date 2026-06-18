import { useQuery } from "@tanstack/react-query";
import { BusinessEventsService } from "@/services/businessEventsService";
import { queryKeys } from "@/lib/query-keys";

export function useBusinessEvents(databaseId?: number | null) {
  return useQuery({
    queryKey: queryKeys.businessEvents(databaseId ?? "default"),
    queryFn: () => BusinessEventsService.list(Number(databaseId ?? 0)),
    enabled: typeof databaseId === "number" && databaseId > 0,
  });
}

export function useBusinessEventsHealth(databaseId?: number | null) {
  return useQuery({
    queryKey: queryKeys.businessEventsHealth(databaseId ?? "default"),
    queryFn: () => BusinessEventsService.health(Number(databaseId ?? 0)),
    enabled: typeof databaseId === "number" && databaseId > 0,
    staleTime: 60_000,
  });
}
