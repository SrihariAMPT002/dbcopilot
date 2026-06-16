import { useEffect, useMemo, useState } from "react";
import { Activity, Download, EyeOff, Filter, ShieldAlert, ShieldCheck } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { MetricCard } from "@/components/metric-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { CoverageBar } from "@/components/coverage-bar";
import { TraceLink } from "@/components/common/TraceLink";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { cn } from "@/lib/utils";
import { useDatabaseContext } from "@/context/database-context";
import { useGovernance, useGovernanceEvidence, useGovernanceSummary } from "@/hooks/useGovernance";
import { mapGovernanceDetail, mapGovernancePackages, type GovernanceFindingViewModel } from "@/mappers/governanceMapper";

export function GovernancePage() {
  const { selectedDatabaseId } = useDatabaseContext();
  const dbId = selectedDatabaseId ?? 1;
  const { data: summary } = useGovernanceSummary(dbId);
  const { data } = useGovernance(dbId);
  const packages = data?.packages ?? [];
  const [selectedTableId, setSelectedTableId] = useState<number | null>(packages[0]?.table_id ?? null);
  const selectedPackage = useMemo(
    () => packages.find((pkg) => pkg.table_id === selectedTableId) ?? packages[0] ?? null,
    [packages, selectedTableId],
  );
  const { data: evidence } = useGovernanceEvidence(selectedPackage?.table_id ?? null);

  useEffect(() => {
    if (selectedTableId == null && packages.length > 0) {
      setSelectedTableId(packages[0].table_id);
    }
  }, [packages, selectedTableId]);

  const rows: GovernanceFindingViewModel[] = useMemo(() => mapGovernancePackages(packages), [packages]);
  const selectedDetail = useMemo(() => mapGovernanceDetail(selectedPackage, evidence), [selectedPackage, evidence]);

  const tableSummary = packages.map((pkg) => ({
    id: pkg.table_id,
    name: `${pkg.schema_name}.${pkg.table_name}`,
    piiCols: pkg.pii_columns.length,
    highRisk: pkg.risk_columns.length,
    coverage: pkg.confidence_score ? Math.round(pkg.confidence_score * 100) : 0,
  }));

  const avgConfidence = packages.length
    ? (packages.reduce((a, p) => a + (p.confidence_score ?? 0), 0) / packages.length).toFixed(2)
    : "0.00";

  const riskRate = summary?.table_count ? Math.round((summary.risk_columns / Math.max(1, summary.table_count)) * 100) : 0;
  const piiRate = summary?.table_count ? Math.round((summary.pii_columns / Math.max(1, summary.table_count)) * 100) : 0;

  const exportPackage = () => {
    const blob = new Blob([JSON.stringify({ summary, packages, evidence: evidence ?? null }, null, 2)], { type: "application/json;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `governance-${dbId}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Intelligence"
        title="Governance"
        description="Live PII classifications, evidence, risk levels, and package telemetry."
        actions={
          <>
            <Badge variant="outline" className="text-[11px]">
              db {dbId}
            </Badge>
            <Button variant="outline" size="sm" className="gap-1.5" onClick={() => document.getElementById("governance-packages")?.scrollIntoView({ behavior: "smooth", block: "start" })}>
              <Filter className="h-3.5 w-3.5" />
              Focus findings
            </Button>
            <Button variant="outline" size="sm" className="gap-1.5" onClick={exportPackage}>
              <Download className="h-3.5 w-3.5" />
              Export package
            </Button>
          </>
        }
      />

      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard label="Governance coverage" value={String(summary?.table_count ?? packages.length)} hint="tables with persisted packages" icon={ShieldCheck} progress={Math.min(100, summary?.governance_packages ? (summary.table_count / Math.max(1, summary.governance_packages)) * 100 : 0)} tone="success" />
        <MetricCard label="PII columns" value={String(summary?.pii_columns ?? 0)} hint="from live packages" icon={EyeOff} tone="warning" />
        <MetricCard label="High-risk columns" value={String(summary?.risk_columns ?? 0)} hint="recommend access policy" icon={ShieldAlert} tone="danger" />
        <MetricCard label="Avg confidence" value={avgConfidence} hint="persisted package confidence" icon={Activity} tone="info" />
      </section>

      <section className="grid grid-cols-1 gap-4 md:grid-cols-3 xl:grid-cols-6">
        <KpiTile label="Total tables" value={String(summary?.table_count ?? packages.length)} onClick={() => document.getElementById("governance-packages")?.scrollIntoView({ behavior: "smooth", block: "start" })} />
        <KpiTile label="Sensitive tables" value={String(summary?.sensitive_columns ?? 0)} tone="danger" />
        <KpiTile label="PII rate" value={`${piiRate}%`} tone="warning" />
        <KpiTile label="Risk rate" value={`${riskRate}%`} tone="danger" />
        <KpiTile label="Coverage" value={`${Math.min(100, Math.round((summary?.governance_packages ?? 0) ? ((summary?.table_count ?? 0) / Math.max(1, summary!.governance_packages)) * 100 : 0))}%`} tone="success" />
        <KpiTile label="Risk findings" value={String(summary?.risk_columns ?? 0)} tone="warning" />
      </section>

      <section className="grid grid-cols-1 gap-4 xl:grid-cols-[1.2fr_0.8fr]">
        <Card id="governance-packages">
          <CardHeader>
            <CardTitle className="text-base">Governance packages</CardTitle>
            <CardDescription>All persisted governance findings grouped by table and column.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow className="bg-muted/40 hover:bg-muted/40">
                    <TableHead>Table</TableHead>
                    <TableHead>Column</TableHead>
                    <TableHead>PII</TableHead>
                    <TableHead>Risk</TableHead>
                    <TableHead className="text-right">Confidence</TableHead>
                    <TableHead>Business purpose</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rows.length ? (
                    rows.map((row) => (
                      <TableRow key={row.id} className={cn("cursor-pointer", selectedTableId === row.tableId && "bg-muted/30")} onClick={() => setSelectedTableId(row.tableId)}>
                        <TableCell>
                          <div className="text-sm text-muted-foreground">{row.schemaName}.{row.tableName}</div>
                        </TableCell>
                        <TableCell className="font-medium text-foreground">{row.columnName}</TableCell>
                        <TableCell>
                          <Badge variant={row.piiDetected ? "destructive" : "secondary"} className="text-[10px] uppercase">
                            {row.piiDetected ? "Detected" : "Not detected"}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <RiskBadge risk={row.riskLevel} />
                        </TableCell>
                        <TableCell className="text-right tabular-nums text-sm">{row.confidence.toFixed(2)}</TableCell>
                        <TableCell className="text-xs text-muted-foreground">{row.businessMeaning || "No business purpose captured."}</TableCell>
                      </TableRow>
                    ))
                  ) : (
                    <TableRow>
                      <TableCell colSpan={6} className="text-sm text-muted-foreground">
                        No governance packages found for this database.
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </div>

            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow className="bg-muted/40 hover:bg-muted/40">
                    <TableHead>Table</TableHead>
                    <TableHead className="text-right">PII cols</TableHead>
                    <TableHead className="text-right">High risk</TableHead>
                    <TableHead className="min-w-[180px]">Coverage</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {tableSummary.length ? (
                    tableSummary.map((table) => (
                      <TableRow key={table.id} className="cursor-pointer" onClick={() => setSelectedTableId(table.id)}>
                        <TableCell className="font-mono text-sm">{table.name}</TableCell>
                        <TableCell className="text-right tabular-nums">{table.piiCols}</TableCell>
                        <TableCell className="text-right tabular-nums">{table.highRisk}</TableCell>
                        <TableCell>
                          <CoverageBar value={table.coverage} />
                        </TableCell>
                      </TableRow>
                    ))
                  ) : (
                    <TableRow>
                      <TableCell colSpan={4} className="text-sm text-muted-foreground">
                        No table summaries available.
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>

        <Card className="xl:sticky xl:top-4 xl:self-start">
          <CardHeader>
            <CardTitle className="text-base">Governance detail</CardTitle>
            <CardDescription>{selectedPackage ? `${selectedPackage.schema_name}.${selectedPackage.table_name}` : "Select a table"}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 text-sm">
            <div className="grid grid-cols-2 gap-3">
              <DetailStat label="Prompt tokens" value={String(evidence?.prompt_tokens ?? selectedPackage?.prompt_tokens ?? 0)} />
              <DetailStat label="Completion tokens" value={String(evidence?.completion_tokens ?? selectedPackage?.completion_tokens ?? 0)} />
              <DetailStat label="Reasoning tokens" value={String(evidence?.reasoning_tokens ?? selectedPackage?.reasoning_tokens ?? 0)} />
              <DetailStat label="Latency" value={`${Math.round(evidence?.latency_ms ?? selectedPackage?.latency_ms ?? 0)} ms`} />
              <DetailStat label="Finish reason" value={evidence?.finish_reason ?? selectedPackage?.finish_reason ?? "unknown"} />
              <DetailStat label="Model" value={selectedPackage?.model_name ?? selectedDetail?.modelName ?? "gpt-5-nano"} />
              <DetailStat label="Confidence" value={`${Math.round((selectedPackage?.confidence_score ?? 0) * 100)}%`} />
            </div>

            <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
              <TraceLink traceId={selectedPackage?.trace_id} label="Open trace" />
              <Badge variant="outline">{selectedDetail?.promptVersion ?? selectedPackage?.prompt_version ?? "v1"}</Badge>
            </div>

            <SectionChips title="Detection evidence" chips={selectedDetail?.evidenceChips ?? []} emptyLabel="No persisted evidence yet." />
            <div>
              <div className="mb-2 text-xs uppercase tracking-wider text-muted-foreground">Business meaning</div>
              <div className="rounded-md border border-border bg-background p-3 text-sm text-muted-foreground">
                {selectedDetail?.businessMeaning || "No business meaning captured."}
              </div>
            </div>
            <SectionChips title="Rule matches" chips={selectedDetail?.ruleMatchChips ?? []} emptyLabel="No rule matches persisted." secondary />
            <SectionChips title="Sample patterns" chips={selectedDetail?.samplePatternChips ?? []} emptyLabel="No sample patterns persisted." />
          </CardContent>
        </Card>
      </section>
    </div>
  );
}

function KpiTile({ label, value, tone = "default", onClick }: { label: string; value: string; tone?: "default" | "danger" | "warning" | "success"; onClick?: () => void }) {
  return (
    <button type="button" onClick={onClick} className="rounded-xl border border-border bg-card p-4 text-left shadow-sm transition hover:border-primary/40">
      <div className="text-xs uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className={cn("mt-1 text-2xl font-semibold", tone === "danger" && "text-destructive", tone === "warning" && "text-[var(--warning)]", tone === "success" && "text-[var(--success)]")}>{value}</div>
    </button>
  );
}

function DetailStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-border bg-muted/20 p-3">
      <div className="text-[11px] uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="mt-1 font-medium text-foreground">{value}</div>
    </div>
  );
}

function SectionChips({ title, chips, emptyLabel, secondary = false }: { title: string; chips: string[]; emptyLabel: string; secondary?: boolean }) {
  return (
    <div>
      <div className="mb-2 text-xs uppercase tracking-wider text-muted-foreground">{title}</div>
      <div className="flex flex-wrap gap-2">
        {chips.length ? (
          chips.map((chip) => (
            <Badge key={chip} variant={secondary ? "secondary" : "outline"} className="text-[10px] uppercase">
              {chip}
            </Badge>
          ))
        ) : (
          <div className="rounded-md border border-dashed border-border p-3 text-xs text-muted-foreground">{emptyLabel}</div>
        )}
      </div>
    </div>
  );
}

function RiskBadge({ risk }: { risk: "high" | "medium" | "low" }) {
  return (
    <Badge
      variant="outline"
      className={cn(
        "rounded-full text-[10px] uppercase tracking-wider",
        risk === "high" && "border-destructive/40 bg-destructive/10 text-destructive",
        risk === "medium" && "border-[var(--warning)]/40 bg-[var(--warning)]/15 text-[var(--warning)]",
        risk === "low" && "border-[var(--success)]/40 bg-[var(--success)]/10 text-[var(--success)]",
      )}
    >
      {risk}
    </Badge>
  );
}
