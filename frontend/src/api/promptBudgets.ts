import { request } from "./client";
import type { PromptBudgetResponse } from "@/types/backend";

export const promptBudgetsApi = {
  list: () => request<PromptBudgetResponse>("/prompt-budgets"),
};
