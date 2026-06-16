import { useQuery } from "@tanstack/react-query";
import { PromptBudgetService } from "@/services/promptBudgetService";

export function usePromptBudgets() {
  return useQuery({
    queryKey: ["prompt-budgets"],
    queryFn: PromptBudgetService.list,
  });
}
