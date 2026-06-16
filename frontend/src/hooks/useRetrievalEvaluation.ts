import { useQuery } from "@tanstack/react-query";
import { RetrievalEvaluationService } from "@/services/retrievalEvaluationService";

export function useRetrievalEvaluation(databaseId?: number | null) {
  return useQuery({
    queryKey: ["retrieval-evaluation", databaseId ?? "default"],
    queryFn: () => RetrievalEvaluationService.list(databaseId ?? 0),
    enabled: typeof databaseId === "number" && databaseId > 0,
  });
}
