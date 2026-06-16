import type { GovernanceEvidence, GovernancePackage } from "@/types/backend";

export type GovernanceFindingViewModel = {
  id: string;
  tableId: number;
  tableName: string;
  schemaName: string;
  columnName: string;
  classification: string;
  piiDetected: boolean;
  piiType: string;
  riskLevel: "high" | "medium" | "low";
  confidence: number;
  classificationSource: string;
  businessMeaning: string;
  recommendedAction: string;
  governanceReasoning: string;
  evidenceChips: string[];
  ruleMatchChips: string[];
  samplePatternChips: string[];
  promptTokens: number;
  completionTokens: number;
  reasoningTokens: number;
  finishReason: string;
  latencyMs: number;
};

export type GovernanceDetailViewModel = {
  tableId: number;
  tableName: string;
  schemaName: string;
  columnName: string;
  dataType: string;
  businessMeaning: string;
  governanceReasoning: string;
  sensitivityExplanation: string;
  complianceTags: string[];
  evidenceChips: string[];
  ruleMatchChips: string[];
  samplePatternChips: string[];
  promptTokens: number;
  completionTokens: number;
  reasoningTokens: number;
  finishReason: string;
  latencyMs: number;
  promptId?: string | null;
  promptVersion?: string | null;
  modelName?: string | null;
  traceId?: string | null;
};

function toChipList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value
    .map((item) => {
      if (typeof item === "string") return item;
      if (item && typeof item === "object") {
        const record = item as Record<string, unknown>;
        return String(
          record.evidence_type ??
            record.rule_name ??
            record.pattern ??
            record.source ??
            record.type ??
            record.reason ??
            record.name ??
            "",
        ).trim();
      }
      return "";
    })
    .filter(Boolean);
}

export function mapGovernancePackages(packages: GovernancePackage[]): GovernanceFindingViewModel[] {
  return packages.flatMap((pkg) =>
    pkg.pii_columns.map((column) => {
      const riskLevel = (column.risk_level as "high" | "medium" | "low") ?? "low";
      const evidenceChips = [
        ...(pkg.evidence ?? []).slice(0, 4).map((item) => String((item as Record<string, unknown>).evidence_type ?? (item as Record<string, unknown>).type ?? "Evidence")),
        ...(pkg.rule_matches ?? []).slice(0, 3).map((item) => String((item as Record<string, unknown>).rule_name ?? (item as Record<string, unknown>).pattern ?? "Rule")),
      ].filter(Boolean);
      return {
        id: `${pkg.table_id}:${column.column_name}`,
        tableId: pkg.table_id,
        tableName: pkg.table_name,
        schemaName: pkg.schema_name,
        columnName: column.column_name,
        classification: column.pii_type ?? (column.is_pii ? "PII" : "Non-PII"),
        piiDetected: column.is_pii,
        piiType: column.pii_type ?? "",
        riskLevel,
        confidence: column.confidence_score ?? pkg.confidence_score ?? 0,
        classificationSource: column.governance_reasoning ? "AI + Rules" : "Rules",
        businessMeaning: column.business_meaning ?? pkg.business_purpose ?? "",
        recommendedAction:
          riskLevel === "high"
            ? "Restrict access and review controls"
            : riskLevel === "medium"
              ? "Review and confirm tagging"
              : "Monitor and retain",
        governanceReasoning: column.governance_reasoning ?? "",
        evidenceChips,
        ruleMatchChips: toChipList(pkg.rule_matches).slice(0, 6),
        samplePatternChips: toChipList(pkg.sample_patterns).slice(0, 6),
        promptTokens: pkg.prompt_tokens ?? 0,
        completionTokens: pkg.completion_tokens ?? 0,
        reasoningTokens: pkg.reasoning_tokens ?? 0,
        finishReason: pkg.finish_reason ?? "unknown",
        latencyMs: pkg.latency_ms ?? 0,
      };
    }),
  );
}

export function mapGovernanceDetail(
  pkg: GovernancePackage | null,
  evidence?: GovernanceEvidence | null,
): GovernanceDetailViewModel | null {
  if (!pkg) return null;
  const primaryColumn = pkg.pii_columns[0] ?? pkg.risk_columns[0] ?? pkg.sensitive_columns[0] ?? null;
  const evidenceChips = [
    ...toChipList(pkg.evidence).slice(0, 6),
    ...(evidence?.evidence ?? []).slice(0, 4).map((item) =>
      String((item as Record<string, unknown>).evidence_type ?? (item as Record<string, unknown>).evidence_source ?? "Evidence"),
    ),
  ].filter(Boolean);
  const detail: GovernanceDetailViewModel = {
    tableId: pkg.table_id,
    tableName: pkg.table_name,
    schemaName: pkg.schema_name,
    columnName: primaryColumn?.column_name ?? "Table",
    dataType: "Structured",
    businessMeaning: primaryColumn?.business_meaning ?? pkg.business_purpose ?? "No business meaning captured.",
    governanceReasoning: primaryColumn?.governance_reasoning ?? pkg.table_summary ?? "No AI reasoning captured.",
    sensitivityExplanation:
      primaryColumn?.is_pii
        ? `${primaryColumn.pii_type ?? "Sensitive"} classification based on metadata, context, and governance evidence.`
        : "No sensitive field detected in the selected package.",
    complianceTags: [
      primaryColumn?.is_pii ? "GDPR" : "GDPR-ready",
      primaryColumn?.risk_level === "high" ? "HIPAA" : "HIPAA-review",
      primaryColumn?.risk_level === "high" ? "PCI DSS" : "PCI DSS-review",
    ].filter(Boolean) as string[],
    evidenceChips,
    ruleMatchChips: toChipList(pkg.rule_matches).slice(0, 8),
    samplePatternChips: toChipList(pkg.sample_patterns).slice(0, 8),
    promptTokens: pkg.prompt_tokens ?? 0,
    completionTokens: pkg.completion_tokens ?? 0,
    reasoningTokens: pkg.reasoning_tokens ?? 0,
    finishReason: pkg.finish_reason ?? "unknown",
    latencyMs: pkg.latency_ms ?? 0,
    promptId: pkg.prompt_id,
    promptVersion: pkg.prompt_version,
    modelName: pkg.model_name,
    traceId: pkg.trace_id,
  };
  return detail;
}
