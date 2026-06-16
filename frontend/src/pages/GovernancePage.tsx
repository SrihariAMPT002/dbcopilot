import { useEffect, useMemo, useState } from "react";
import { Activity, Download, EyeOff, Filter, ShieldAlert, ShieldCheck, ExternalLink } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { MetricCard } from "@/components/metric-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { CoverageBar } from "@/components/coverage-bar";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { cn } from "@/lib/utils";
import { useDatabaseContext } from "@/context/database-context";
import { useGovernance, useGovernanceEvidence, useGovernanceSummary } from "@/hooks/useGovernance";

type Row = {
  tableId: number;
  table: string;
  col: string;
  classification: string;
  risk: "high" | "medium" | "low";
  confidence: number;
  purpose: string;
  rowEvidence: Array<Record<string, unknown>>;
  ruleMatches: Array<Record<string, unknown>>;
  samplePatterns: Array<Record<string, unknown> | string>;
  promptTokens?: number | null;
  completionTokens?: number | null;
  reasoningTokens?: number | null;
  finishReason?: string | null;
  latencyMs?: number | null;
};

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

  const rows: Row[] = useMemo(
    () =>
      packages.flatMap((pkg) =>
        pkg.pii_columns.map((c) => ({
          tableId: pkg.table_id,
          table: `${pkg.schema_name}.${pkg.table_name}`,
          col: c.column_name,
          classification: c.pii_type ?? (c.is_pii ? "PII" : "non_pii"),
          risk: (c.risk_level as "high" | "medium" | "low") ?? "low",
          confidence: c.confidence_score ?? 0,
          purpose: c.business_meaning ?? pkg.business_purpose ?? "",
          rowEvidence: pkg.evidence ?? [],
          ruleMatches: pkg.rule_matches ?? [],
          samplePatterns: pkg.sample_patterns ?? [],
          promptTokens: pkg.prompt_tokens,
          completionTokens: pkg.completion_tokens,
          reasoningTokens: pkg.reasoning_tokens,
          finishReason: pkg.finish_reason,
          latencyMs: pkg.latency_ms,
        })),
      ),
    [packages],
  );

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

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Intelligence"
        title="Governance"
        description="Live PII classifications, rule matches, evidence, and governance package telemetry."
        actions={
          <>
            <Badge variant="outline" className="text-[11px]">
              db {dbId}
            </Badge>
            <Button variant="outline" size="sm" className="gap-1.5">
              <Filter className="h-3.5 w-3.5" />
              Filter
            </Button>
            <Button variant="outline" size="sm" className="gap-1.5">
              <Download className="h-3.5 w-3.5" />
              Export package
            </Button>
          </>
        }
      />

      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          label="Governance coverage"
          value={String(summary?.table_count ?? packages.length)}
          hint="tables with persisted packages"
          icon={ShieldCheck}
          progress={Math.min(100, summary?.governance_packages ? (summary.table_count / Math.max(1, summary.governance_packages)) * 100 : 0)}
          tone="success"
        />
        <MetricCard
          label="PII columns"
          value={String(summary?.pii_columns ?? 0)}
          hint="from live packages"
          icon={EyeOff}
          tone="warning"
        />
        <MetricCard
          label="High-risk columns"
          value={String(summary?.risk_columns ?? 0)}
          hint="recommend access policy"
          icon={ShieldAlert}
          tone="danger"
        />
        <MetricCard
          label="Avg confidence"
          value={avgConfidence}
          hint="persisted package confidence"
          icon={Activity}
          tone="info"
        />
      </section>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader>
            <CardTitle className="text-base">Governance package</CardTitle>
            <CardDescription>Column-level classifications generated for the active source.</CardDescription>
          </CardHeader>
          <CardContent>
            <Tabs defaultValue="columns">
              <TabsList>
                <TabsTrigger value="columns">Columns</TabsTrigger>
                <TabsTrigger value="tables">Tables</TabsTrigger>
              </TabsList>
              <TabsContent value="columns" className="pt-4">
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow className="bg-muted/40 hover:bg-muted/40">
                        <TableHead>Column</TableHead>
                        <TableHead>Classification</TableHead>
                        <TableHead>Risk</TableHead>
                        <TableHead className="text-right">Confidence</TableHead>
                        <TableHead>Business purpose</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {rows.length ? (
                        rows.map((r) => (
                          <TableRow
                            key={`${r.table}.${r.col}`}
                            className={cn(
                              "cursor-pointer",
                              selectedTableId === r.tableId && "bg-muted/30",
                            )}
                            onClick={() => setSelectedTableId(r.tableId)}
                          >
                            <TableCell>
                              <div className="text-sm">
                                <span className="text-muted-foreground">{r.table}.</span>
                                <span className="font-medium text-foreground">{r.col}</span>
                              </div>
                            </TableCell>
                            <TableCell className="text-sm">{r.classification}</TableCell>
                            <TableCell>
                              <RiskBadge risk={r.risk} />
                            </TableCell>
                            <TableCell className="text-right tabular-nums text-sm">{r.confidence.toFixed(2)}</TableCell>
                            <TableCell className="text-xs text-muted-foreground">{r.purpose}</TableCell>
                          </TableRow>
                        ))
                      ) : (
                        <TableRow>
                          <TableCell colSpan={5} className="text-sm text-muted-foreground">
                            No governance packages found for this database.
                          </TableCell>
                        </TableRow>
                      )}
                    </TableBody>
                  </Table>
                </div>
              </TabsContent>
              <TabsContent value="tables" className="pt-4">
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
                      tableSummary.map((t) => (
                        <TableRow key={t.id} className="cursor-pointer" onClick={() => setSelectedTableId(t.id)}>
                          <TableCell className="font-mono text-sm">{t.name}</TableCell>
                          <TableCell className="text-right tabular-nums">{t.piiCols}</TableCell>
                          <TableCell className="text-right tabular-nums">{t.highRisk}</TableCell>
                          <TableCell>
                            <CoverageBar value={t.coverage} />
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
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Governance evidence</CardTitle>
            <CardDescription>
              {selectedPackage ? `${selectedPackage.schema_name}.${selectedPackage.table_name}` : "Select a table"}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 text-sm">
            <div className="rounded-md border border-border bg-muted/20 p-3">
              <div className="flex items-center justify-between">
                <span className="text-xs uppercase tracking-wider text-muted-foreground">Telemetry</span>
                <Badge variant="outline">{evidence?.finish_reason ?? selectedPackage?.finish_reason ?? "unknown"}</Badge>
              </div>
              <div className="mt-3 grid grid-cols-2 gap-3 text-xs">
                <div>
                  <div className="text-muted-foreground">Prompt tokens</div>
                  <div className="font-medium tabular-nums">{evidence?.prompt_tokens ?? selectedPackage?.prompt_tokens ?? 0}</div>
                </div>
                <div>
                  <div className="text-muted-foreground">Completion tokens</div>
                  <div className="font-medium tabular-nums">{evidence?.completion_tokens ?? selectedPackage?.completion_tokens ?? 0}</div>
                </div>
                <div>
                  <div className="text-muted-foreground">Reasoning tokens</div>
                  <div className="font-medium tabular-nums">{evidence?.reasoning_tokens ?? selectedPackage?.reasoning_tokens ?? 0}</div>
                </div>
                <div>
                  <div className="text-muted-foreground">Latency</div>
                  <div className="font-medium tabular-nums">{Math.round(evidence?.latency_ms ?? selectedPackage?.latency_ms ?? 0)} ms</div>
                </div>
              </div>
              {(selectedPackage?.trace_id || evidence?.evidence?.[0]) && (
                <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                  {selectedPackage?.trace_id ? (
                    <a
                      href={`/jobs?trace_id=${encodeURIComponent(selectedPackage.trace_id)}`}
                      className="inline-flex items-center gap-1 text-primary underline-offset-2 hover:underline"
                    >
                      Trace drill-down <ExternalLink className="h-3 w-3" />
                    </a>
                  ) : null}
                </div>
              )}
            </div>

            <div>
              <div className="mb-2 text-xs uppercase tracking-wider text-muted-foreground">Evidence</div>
              <div className="space-y-2">
                {(evidence?.evidence ?? []).length ? (
                  evidence!.evidence.map((item) => (
                    <div key={item.id} className="rounded-md border border-border bg-background p-3">
                      <div className="flex items-center justify-between gap-2">
                        <div className="font-medium">{item.evidence_type}</div>
                        <Badge variant="outline" className="text-[10px] uppercase">
                          {item.evidence_source}
                        </Badge>
                      </div>
                      <pre className="mt-2 overflow-auto rounded bg-muted/30 p-2 text-[11px] leading-5 text-muted-foreground">
                        {JSON.stringify(item.evidence_json, null, 2)}
                      </pre>
                    </div>
                  ))
                ) : (
                  <div className="rounded-md border border-dashed border-border p-3 text-xs text-muted-foreground">
                    No persisted evidence yet.
                  </div>
                )}
              </div>
            </div>

            <div>
              <div className="mb-2 text-xs uppercase tracking-wider text-muted-foreground">Rule matches</div>
              <pre className="max-h-56 overflow-auto rounded-md border border-border bg-muted/20 p-3 text-[11px] leading-5 text-muted-foreground">
                {JSON.stringify(selectedPackage?.rule_matches ?? [], null, 2)}
              </pre>
            </div>

            <div>
              <div className="mb-2 text-xs uppercase tracking-wider text-muted-foreground">Sample patterns</div>
              <pre className="max-h-44 overflow-auto rounded-md border border-border bg-muted/20 p-3 text-[11px] leading-5 text-muted-foreground">
                {JSON.stringify(selectedPackage?.sample_patterns ?? [], null, 2)}
              </pre>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Governance traceability</CardTitle>
          <CardDescription>Prompt telemetry, evidence, and column-level reasoning for the selected governance package.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {selectedPackage ? (
            <>
              <div className="grid gap-3 md:grid-cols-4">
                <MetricCard label="Prompt tokens" value={String(selectedPackage.prompt_tokens ?? 0)} icon={Activity} tone="info" />
                <MetricCard label="Completion tokens" value={String(selectedPackage.completion_tokens ?? 0)} icon={Activity} tone="default" />
                <MetricCard label="Reasoning tokens" value={String(selectedPackage.reasoning_tokens ?? 0)} icon={Activity} tone="warning" />
                <MetricCard label="Latency" value={`${Math.round(selectedPackage.latency_ms ?? 0)} ms`} icon={Activity} tone="success" />
              </div>
              <div className="grid gap-3 lg:grid-cols-2">
                <div className="space-y-2">
                  <div className="text-xs uppercase tracking-wider text-muted-foreground">Rule matches</div>
                  <pre className="max-h-56 overflow-auto rounded-md border border-border bg-muted/20 p-3 text-[11px] leading-5 text-muted-foreground">
                    {JSON.stringify(selectedPackage.rule_matches ?? [], null, 2)}
                  </pre>
                </div>
                <div className="space-y-2">
                  <div className="text-xs uppercase tracking-wider text-muted-foreground">Evidence payload</div>
                  <pre className="max-h-56 overflow-auto rounded-md border border-border bg-muted/20 p-3 text-[11px] leading-5 text-muted-foreground">
                    {JSON.stringify(selectedPackage.evidence ?? [], null, 2)}
                  </pre>
                </div>
              </div>
            </>
          ) : (
            <div className="text-sm text-muted-foreground">No governance package selected.</div>
          )}
        </CardContent>
      </Card>
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
