import { useMemo } from "react";
import { GitBranch, Layers3, Loader2, Ruler, TrendingUp } from "lucide-react";
import { useDatabaseContext } from "@/context/database-context";
import { useKPIs } from "@/hooks/useKpis";
import { useBusinessInsights } from "@/hooks/useBusinessInsights";
import { PageHeader } from "@/components/page-header";
import { MetricCard } from "@/components/metric-card";
import { TraceLink } from "@/components/common/TraceLink";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { CoverageBar } from "@/components/coverage-bar";
import { EmptyState } from "@/components/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, XAxis, YAxis } from "recharts";

type KpiRecord = Record<string, unknown>;

const trendChartConfig: ChartConfig = {
  confidence: { label: "Confidence", color: "hsl(var(--primary))" },
  coverage: { label: "Coverage", color: "hsl(var(--success))" },
};

export function KPIPage() {
  const { selectedDatabase } = useDatabaseContext();
  const dbId = selectedDatabase?.database_id ?? null;
  const { data, isLoading, isError, error, refetch } = useKPIs(dbId);
  const { data: businessInsights } = useBusinessInsights(dbId);

  const catalog = (data?.catalog ?? []) as KpiRecord[];
  const definitions = (data?.definitions ?? []) as KpiRecord[];
  const lineage = (data?.lineage ?? []) as KpiRecord[];
  const clusters = (data?.clusters ?? []) as KpiRecord[];
  const candidates = catalog.filter((item) => item.candidate_type || item.metric || item.name);

  const primaryCandidate = candidates[0] ?? {};
  const primaryDefinition = definitions[0] ?? {};
  const enriched = {
    name: (data?.kpi_name ?? primaryCandidate.name ?? primaryCandidate.metric) as string | undefined,
    description: (data?.description ?? primaryCandidate.description) as string | undefined,
    formula: (data?.formula ?? primaryDefinition.formula) as string | undefined,
    category: (data?.category ?? primaryCandidate.category) as string | undefined,
    confidence_score: data?.confidence_score ?? Number(primaryCandidate.confidence ?? primaryCandidate.confidence_score ?? 0),
  };

  const trendData = useMemo(
    () =>
      [
        { label: "Coverage", confidence: Math.round((data?.coverage_percentage ?? 0) * 100) / 100, coverage: Math.round((data?.coverage?.coverage_score ?? 0) * 100) / 100 },
        { label: "Confidence", confidence: Math.round((data?.confidence_score ?? 0) * 100), coverage: Math.round((data?.coverage?.confidence_score ?? 0) * 100) },
        { label: "Freshness", confidence: Math.round((data?.coverage?.artifact_fresh ? 100 : 0)), coverage: Math.round((data?.coverage?.artifact_fresh ? 100 : 0)) },
      ],
    [data],
  );

  if (isLoading) {
    return (
      <div className="space-y-6">
        <PageHeader eyebrow="Intelligence" title="KPI package" description="Canonical KPI package generated from deterministic candidates and AI-enriched reasoning." />
        <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Skeleton className="h-28 rounded-xl" />
          <Skeleton className="h-28 rounded-xl" />
          <Skeleton className="h-28 rounded-xl" />
          <Skeleton className="h-28 rounded-xl" />
        </section>
        <Skeleton className="h-[520px] rounded-2xl" />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="space-y-6">
        <PageHeader eyebrow="Intelligence" title="KPI package" description="Canonical KPI package generated from deterministic candidates and AI-enriched reasoning." />
        <Card className="border-destructive/30 bg-destructive/5">
          <CardHeader>
            <CardTitle className="text-base text-destructive">KPI data unavailable</CardTitle>
            <CardDescription>{error instanceof Error ? error.message : "Failed to load KPI intelligence for the selected database."}</CardDescription>
          </CardHeader>
          <CardContent>
            <button type="button" onClick={() => void refetch()} className="rounded-md border border-border bg-background px-3 py-2 text-sm font-medium text-foreground transition hover:border-primary/40">
              Retry load
            </button>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!data || (!catalog.length && !definitions.length && !lineage.length && !clusters.length)) {
    return (
      <div className="space-y-6">
        <PageHeader eyebrow="Intelligence" title="KPI package" description="Canonical KPI package generated from deterministic candidates and AI-enriched reasoning." />
        <EmptyState
          icon={TrendingUp}
          title="No KPI package yet"
          description="Run KPI intelligence generation after sync to populate catalog items, definitions, lineage, and traces."
          action={
            <button type="button" onClick={() => void refetch()} className="rounded-md border border-border bg-background px-3 py-2 text-sm font-medium text-foreground transition hover:border-primary/40">
              Refresh
            </button>
          }
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Intelligence" title="KPI package" description="Canonical KPI package generated from deterministic candidates and AI-enriched reasoning." />
      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard label="Package confidence" value={`${Math.round((data?.confidence_score ?? 0) * 100)}%`} icon={TrendingUp} tone="info" />
        <MetricCard label="Category" value={data?.category ?? "discovered"} icon={Ruler} />
        <MetricCard label="Trace ID" value={data?.trace_id ?? "n/a"} icon={GitBranch} tone="success" />
        <MetricCard label="Catalog items" value={String(catalog.length)} icon={Layers3} progress={Math.min(100, catalog.length * 10)} tone="success" />
      </section>

      <section className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">KPI trend view</CardTitle>
            <CardDescription>Coverage, confidence, and freshness indicators from the persisted KPI package.</CardDescription>
          </CardHeader>
          <CardContent>
            <ChartContainer config={trendChartConfig} className="h-[280px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={trendData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="label" tickLine={false} axisLine={false} />
                  <YAxis tickLine={false} axisLine={false} />
                  <ChartTooltip content={<ChartTooltipContent />} />
                  <Bar dataKey="confidence" fill="var(--color-confidence)" radius={[8, 8, 0, 0]} />
                  <Bar dataKey="coverage" fill="var(--color-coverage)" radius={[8, 8, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </ChartContainer>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">KPI package</CardTitle>
            <CardDescription>Deterministic candidates on the left, AI-enriched KPI on the right.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-3 md:grid-cols-2">
              <div className="rounded-md border border-border bg-card p-3">
                <div className="text-xs uppercase tracking-wide text-muted-foreground">KPI name</div>
                <div className="mt-1 text-sm font-medium">{enriched.name ?? "No KPI package yet"}</div>
              </div>
              <div className="rounded-md border border-border bg-card p-3">
                <div className="text-xs uppercase tracking-wide text-muted-foreground">Formula</div>
                <div className="mt-1 text-sm font-medium">{enriched.formula ?? "n/a"}</div>
              </div>
            </div>
            <div className="rounded-md border border-border bg-card p-3">
              <div className="text-xs uppercase tracking-wide text-muted-foreground">Description</div>
              <div className="mt-1 text-sm text-muted-foreground">{enriched.description ?? "No KPI package persisted yet."}</div>
              <CoverageBar value={Math.round((data?.confidence_score ?? 0) * 100)} className="mt-3" />
            </div>
            <div className="grid gap-4 lg:grid-cols-2">
              <div className="space-y-3 rounded-md border border-border bg-card p-4">
                <div className="text-sm font-semibold text-foreground">Deterministic candidates</div>
                {candidates.length ? (
                  candidates.slice(0, 5).map((item, index) => (
                    <div key={`${String(item.metric ?? item.name ?? index)}`} className="rounded-md border border-dashed border-border p-3">
                      <div className="text-sm font-medium">{String(item.metric ?? item.name ?? "Candidate")}</div>
                      <div className="text-xs uppercase tracking-wide text-muted-foreground">{String(item.candidate_type ?? item.category ?? "candidate")}</div>
                      <div className="mt-2 text-xs text-muted-foreground">Confidence: {Math.round((Number(item.confidence ?? item.confidence_score ?? 0) || 0) * 100)}%</div>
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
          </CardContent>
        </Card>
      </section>

      <section className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">KPI lineage</CardTitle>
            <CardDescription>Definitions, lineage, and catalog items from the persisted package.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid gap-3 md:grid-cols-2">
              <div className="rounded-md border border-border bg-card p-3">
                <div className="text-xs uppercase tracking-wide text-muted-foreground">Definitions</div>
                <div className="mt-1 text-sm text-foreground">{String(definitions.length)}</div>
              </div>
              <div className="rounded-md border border-border bg-card p-3">
                <div className="text-xs uppercase tracking-wide text-muted-foreground">Lineage entries</div>
                <div className="mt-1 text-sm text-foreground">{String(lineage.length)}</div>
              </div>
            </div>
            <div className="rounded-md border border-border bg-card p-3">
              <div className="text-xs uppercase tracking-wide text-muted-foreground">Clusters</div>
              <div className="mt-1 text-sm text-foreground">
                {clusters.length
                  ? clusters
                      .slice(0, 3)
                      .map((cluster) => String((cluster as Record<string, unknown>).cluster_name ?? (cluster as Record<string, unknown>).cluster_id ?? "cluster"))
                      .join(", ")
                  : "No KPI clusters captured yet."}
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
              <TraceLink traceId={data?.trace_id} label="Open trace" />
              <Badge variant="outline">{data?.prompt_version ?? "clustered"}</Badge>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Business insights</CardTitle>
            <CardDescription>Linked KPI-driven insights generated from the same database context.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {businessInsights?.insights?.length ? (
              businessInsights.insights.slice(0, 3).map((insight) => (
                <div key={insight.id ?? insight.insight_text} className="rounded-md border border-border bg-card p-3">
                  <div className="text-sm font-medium">{insight.insight_text}</div>
                  <div className="mt-1 text-xs text-muted-foreground">Trace: {insight.trace_id ?? "n/a"} · Impact: {insight.impact_level ?? "unknown"}</div>
                  <TraceLink traceId={insight.trace_id} label="Open trace" className="mt-2 text-xs" />
                  <div className="mt-2 flex flex-wrap gap-2">
                    {(insight.evidence ?? []).slice(0, 4).map((item, index) => (
                      <Badge key={`${insight.id ?? index}`} variant="outline" className="text-[10px] uppercase">
                        {String((item as Record<string, unknown>).evidence_type ?? (item as Record<string, unknown>).type ?? "evidence")}
                      </Badge>
                    ))}
                  </div>
                </div>
              ))
            ) : (
              <div className="text-sm text-muted-foreground">No linked business insights yet.</div>
            )}
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
