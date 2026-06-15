import { useQuery } from "@tanstack/react-query";
import { RelationshipService } from "@/services/relationshipsService";

export function useRelationships(databaseId: number) {
  return useQuery({
    queryKey: ["relationships", databaseId],
    queryFn: () => RelationshipService.getPackage(databaseId),
  });
}
