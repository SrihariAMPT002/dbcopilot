import { semanticsApi } from "@/api/semantics";

export const SemanticService = {
  getPackage: semanticsApi.package,
  getEvidence: semanticsApi.evidence,
};
