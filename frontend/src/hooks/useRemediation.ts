import { useQuery } from "@tanstack/react-query";
import { ReadinessService } from "@/services/readinessService";

export function useRemediation(databaseId?: number | null) {
  return useQuery({
    queryKey: ["readiness-remediation", databaseId ?? "default"],
    queryFn: () => ReadinessService.getRemediation(databaseId ?? 0),
    enabled: typeof databaseId === "number" && databaseId > 0,
  });
}
