import { useQuery } from "@tanstack/react-query";
import { BusinessEventsService } from "@/services/businessEventsService";

export function useBusinessEvents(databaseId?: number | null) {
  return useQuery({
    queryKey: ["business-events", databaseId ?? "default"],
    queryFn: () => BusinessEventsService.list(Number(databaseId ?? 0)),
    enabled: typeof databaseId === "number" && databaseId > 0,
  });
}
