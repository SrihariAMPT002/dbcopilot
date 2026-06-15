import { useQuery } from "@tanstack/react-query";
import { ReadinessService } from "@/services/readinessService";

export function useReadiness(databaseId: number) {
  return useQuery({
    queryKey: ["readiness", databaseId],
    queryFn: () => ReadinessService.getSnapshot(databaseId),
  });
}
