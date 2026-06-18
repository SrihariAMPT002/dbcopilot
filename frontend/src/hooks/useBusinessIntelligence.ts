import { useQueries } from "@tanstack/react-query";
import { BusinessIntelligenceService } from "@/services/businessIntelligenceService";

export function useBusinessIntelligence(databaseId?: number | null) {
  return useQueries({
    queries: [
      {
        queryKey: ["business-intelligence", "opportunities", databaseId ?? "default"],
        queryFn: () => BusinessIntelligenceService.opportunities(Number(databaseId ?? 0)),
        enabled: typeof databaseId === "number" && databaseId > 0,
      },
      {
        queryKey: ["business-intelligence", "data-products", databaseId ?? "default"],
        queryFn: () => BusinessIntelligenceService.dataProducts(Number(databaseId ?? 0)),
        enabled: typeof databaseId === "number" && databaseId > 0,
      },
      {
        queryKey: ["business-intelligence", "warehouse-designs", databaseId ?? "default"],
        queryFn: () => BusinessIntelligenceService.warehouseDesigns(Number(databaseId ?? 0)),
        enabled: typeof databaseId === "number" && databaseId > 0,
      },
      {
        queryKey: ["business-intelligence", "recommendations", databaseId ?? "default"],
        queryFn: () => BusinessIntelligenceService.recommendations(Number(databaseId ?? 0)),
        enabled: typeof databaseId === "number" && databaseId > 0,
      },
      {
        queryKey: ["business-intelligence", "predictive-readiness", databaseId ?? "default"],
        queryFn: () => BusinessIntelligenceService.predictiveReadiness(Number(databaseId ?? 0)),
        enabled: typeof databaseId === "number" && databaseId > 0,
      },
      {
        queryKey: ["business-intelligence", "health", databaseId ?? "default"],
        queryFn: () => BusinessIntelligenceService.health(Number(databaseId ?? 0)),
        enabled: typeof databaseId === "number" && databaseId > 0,
      },
    ],
  });
}
