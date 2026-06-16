import { TrendingUp, Ruler, Layers3, GitBranch, ExternalLink } from "lucide-react";
import { Link } from "@tanstack/react-router";
import { PageHeader } from "@/components/page-header";
import { MetricCard } from "@/components/metric-card";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { CoverageBar } from "@/components/coverage-bar";
import { useKPIs } from "@/hooks/useKpis";
import { useDatabaseContext } from "@/context/database-context";
import { useBusinessInsights } from "@/hooks/useBusinessInsights";

export function KPIPage() {
  const { selectedDatabaseId } = useDatabaseContext();
  const dbId = selectedDatabaseId ?? 1;
  const { data } = useKPIs(dbId);
  const { data: businessInsights } = useBusinessInsights(dbId);
  const candidates = (data?.evidence ?? []).filter((item) => item.candidate_type || item.metric);
  const enriched = {
    name: data?.kpi_name,
    description: data?.description,
    formula: data?.formula,
    category: data?.category,
    confidence_score: data?.confidence_score,
  };

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Intelligence"
        title="KPI package"
        description="Canonical KPI package generated from deterministic candidates and AI-enriched reasoning."
      />
      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard label="Package confidence" value={`${Math.round((data?.confidence_score ?? 0) * 100)}%`} icon={TrendingUp} tone="info" />
        <MetricCard label="Category" value={data?.category ?? "discovered"} icon={Ruler} />
        <MetricCard label="Trace ID" value={data?.trace_id ?? "n/a"} icon={GitBranch} tone="success" />
        <MetricCard label="Evidence items" value={String(data?.evidence?.length ?? 0)} icon={Layers3} progress={Math.min(100, (data?.evidence?.length ?? 0) * 10)} tone="success" />
      </section>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">KPI package</CardTitle>
          <CardDescription>Primary persisted KPI artifact for the selected database.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Tabs defaultValue="summary">
            <TabsList>
              <TabsTrigger value="summary">Summary</TabsTrigger>
              <TabsTrigger value="comparison">Comparison</TabsTrigger>
              <TabsTrigger value="evidence">Evidence</TabsTrigger>
            </TabsList>
            <TabsContent value="summary" className="space-y-3 pt-4">
              <div className="grid gap-3 md:grid-cols-2">
                <div className="rounded-md border border-border bg-card p-3">
                  <div className="text-xs uppercase tracking-wide text-muted-foreground">KPI name</div>
                  <div className="mt-1 text-sm font-medium">{data?.kpi_name ?? "No KPI package yet"}</div>
                </div>
                <div className="rounded-md border border-border bg-card p-3">
                  <div className="text-xs uppercase tracking-wide text-muted-foreground">Formula</div>
                  <div className="mt-1 text-sm font-medium">{data?.formula ?? "n/a"}</div>
                </div>
              </div>
              <div className="rounded-md border border-border bg-card p-3">
                <div className="text-xs uppercase tracking-wide text-muted-foreground">Description</div>
                <div className="mt-1 text-sm text-muted-foreground">{data?.description ?? "No KPI package persisted yet."}</div>
                <CoverageBar value={Math.round((data?.confidence_score ?? 0) * 100)} className="mt-3" />
              </div>
            </TabsContent>
            <TabsContent value="comparison" className="pt-4">
              <div className="grid gap-4 lg:grid-cols-2">
                <div className="space-y-3 rounded-md border border-border bg-card p-4">
                  <div className="text-sm font-semibold text-foreground">Deterministic candidate</div>
                  {candidates.length ? (
                    candidates.slice(0, 5).map((item, index) => (
                      <div key={`${item.metric ?? index}`} className="rounded-md border border-dashed border-border p-3">
                        <div className="text-sm font-medium">{String(item.metric ?? "Candidate")}</div>
                        <div className="text-xs uppercase tracking-wide text-muted-foreground">{String(item.candidate_type ?? "candidate")}</div>
                        <div className="mt-2 text-xs text-muted-foreground">Confidence: {Math.round((Number(item.confidence ?? 0) || 0) * 100)}%</div>
                      </div>
                    ))
                  ) : (
                    <div className="text-sm text-muted-foreground">No deterministic KPI candidates yet.</div>
                  )}
                </div>
                <div className="space-y-3 rounded-md border border-border bg-card p-4">
                  <div className="text-sm font-semibold text-foreground">AI-enriched KPI package</div>
                  <div className="rounded-md border border-dashed border-border p-3">
                    <div className="text-sm font-medium">{enriched.name ?? "No KPI generated yet"}</div>
                    <div className="text-xs uppercase tracking-wide text-muted-foreground">{enriched.category ?? "enriched"}</div>
                    <div className="mt-2 text-sm text-muted-foreground">{enriched.description ?? "AI did not persist a package yet."}</div>
                    <div className="mt-2 text-xs text-muted-foreground">Formula: {enriched.formula ?? "n/a"}</div>
                    <div className="mt-2 text-xs text-muted-foreground">Confidence: {Math.round((enriched.confidence_score ?? 0) * 100)}%</div>
                  </div>
                </div>
              </div>
            </TabsContent>
            <TabsContent value="evidence" className="pt-4">
              <div className="space-y-2">
                {(data?.evidence ?? []).length ? (
                  (data?.evidence ?? []).map((item, index) => (
                    <div key={`${index}-${String(item.metric ?? item.name ?? "evidence")}`} className="rounded-md border border-border bg-card p-3 text-sm">
                      <div className="font-medium text-foreground">{String(item.metric ?? item.name ?? "Evidence")}</div>
                      <pre className="mt-2 overflow-x-auto text-xs text-muted-foreground">{JSON.stringify(item, null, 2)}</pre>
                    </div>
                  ))
                ) : (
                  <div className="text-sm text-muted-foreground">No KPI evidence yet.</div>
                )}
              </div>
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
        <CardTitle className="text-base">KPI traceability</CardTitle>
        <CardDescription>Persisted KPI evidence and linked business insight trace IDs.</CardDescription>
      </CardHeader>
        <CardContent className="grid gap-4 lg:grid-cols-2">
          <div className="space-y-2">
            <div className="text-sm font-medium text-foreground">Business insight traces</div>
            {businessInsights?.insights?.length ? (
              businessInsights.insights.slice(0, 3).map((insight) => (
                <div key={insight.id ?? insight.insight_text} className="rounded-md border border-border bg-card p-3">
                  <div className="text-sm font-medium">{insight.insight_text}</div>
                  <div className="mt-1 text-xs text-muted-foreground">
                    Trace: {insight.trace_id ?? "n/a"} · Impact: {insight.impact_level ?? "unknown"}
                  </div>
                  {insight.trace_id ? (
                    <a
                      href={`/jobs?trace_id=${encodeURIComponent(insight.trace_id)}`}
                      className="mt-2 inline-flex items-center gap-1 text-xs text-primary underline-offset-2 hover:underline"
                    >
                      Trace drill-down <ExternalLink className="h-3 w-3" />
                    </a>
                  ) : null}
                </div>
              ))
            ) : (
              <div className="text-sm text-muted-foreground">No linked business insights yet.</div>
            )}
          </div>
          <div className="space-y-2">
            <div className="text-sm font-medium text-foreground">KPI evidence payload</div>
            {(data?.evidence ?? []).length ? (
              (data?.evidence ?? []).slice(0, 4).map((item, index) => (
                <div key={`trace-${index}`} className="rounded-md border border-border bg-card p-3">
                  <div className="text-xs uppercase tracking-wide text-muted-foreground">{String(item.metric ?? item.name ?? "evidence")}</div>
                  <pre className="mt-2 overflow-x-auto text-[11px] text-muted-foreground">{JSON.stringify(item, null, 2)}</pre>
                </div>
              ))
            ) : (
              <div className="text-sm text-muted-foreground">No KPI evidence payload yet.</div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
