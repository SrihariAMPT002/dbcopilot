import { governanceApi } from "@/api/governance";

export const GovernanceService = {
  getPackages: governanceApi.packages,
  getSummary: governanceApi.summary,
  getEvidence: governanceApi.evidence,
};
