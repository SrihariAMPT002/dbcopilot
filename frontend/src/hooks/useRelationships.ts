import { useQuery } from "@tanstack/react-query";
import { RelationshipService } from "@/services/relationshipsService";

export function useRelationships(databaseId?: number | null) {
  return useQuery({
    queryKey: ["relationships", databaseId ?? "default"],
    queryFn: () => RelationshipService.getPackage(Number(databaseId ?? 0)),
    enabled: typeof databaseId === "number" && databaseId > 0,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });
}
