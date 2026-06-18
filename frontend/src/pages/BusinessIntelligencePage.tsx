import { useMemo } from "react";
import { Activity, Boxes, Brain, Sparkles, TrendingUp } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { ActiveDatabaseBadge } from "@/components/common/ActiveDatabaseBadge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/empty-state";
import { Badge } from "@/components/ui/badge";
import { useDatabaseContext } from "@/context/database-context";
import { useBusinessInsights } from "@/hooks/useBusinessInsights";
import { useBusinessIntelligence } from "@/hooks/useBusinessIntelligence";
import { useDashboard } from "@/hooks/useDashboard";

export function BusinessIntelligencePage() {
  const { selectedDatabase } = useDatabaseContext();
  const databaseId = selectedDatabase?.database_id ?? null;
  const { data, isLoading, isError, error } = useDashboard(databaseId);
  const { data: businessInsights } = useBusinessInsights(databaseId);
  const [opportunitiesQuery, dataProductsQuery, warehouseDesignsQuery, recommendationsQuery, predictiveReadinessQuery, healthQuery] = useBusinessIntelligence(databaseId);

  const insights = businessInsights?.insights ?? [];
  const opportunities = opportunitiesQuery.data?.opportunities ?? [];
  const dataProducts = dataProductsQuery.data?.data_products ?? [];
  const warehouseDesigns = warehouseDesignsQuery.data?.warehouse_designs ?? [];
  const recommendations = recommendationsQuery.data?.recommendations ?? [];
  const predictiveReadiness = predictiveReadinessQuery.data?.predictive_readiness;
  const health = healthQuery.data?.packages ?? {};

  const summaryCards = useMemo(
    () => [
      { label: "Insights", value: insights.length, icon: Sparkles },
      { label: "Opportunities", value: opportunities.length, icon: Activity },
      { label: "Data products", value: dataProducts.length, icon: Boxes },
      { label: "Readiness", value: predictiveReadiness ? Math.round((predictiveReadiness.agent_readiness_score ?? 0) * 100) : 0, icon: Brain },
    ],
    [dataProducts.length, insights.length, opportunities.length, predictiveReadiness],
  );

  if (isLoading || opportunitiesQuery.isLoading || dataProductsQuery.isLoading || warehouseDesignsQuery.isLoading || recommendationsQuery.isLoading || predictiveReadinessQuery.isLoading || healthQuery.isLoading) {
    return (
      <div className="space-y-6">
        <PageHeader eyebrow="AI Surface" title="Business intelligence" description="Cross-package insights, opportunities, products, designs, and predictive readiness." actions={<ActiveDatabaseBadge />} />
        <Card className="border-border bg-card shadow-sm">
          <CardContent className="p-6 text-sm text-muted-foreground">Loading business intelligence packages...</CardContent>
        </Card>
      </div>
    );
  }

  if (isError || opportunitiesQuery.isError || dataProductsQuery.isError || warehouseDesignsQuery.isError || recommendationsQuery.isError || predictiveReadinessQuery.isError || healthQuery.isError) {
    const message =
      (error instanceof Error && error.message) ||
      (opportunitiesQuery.error instanceof Error && opportunitiesQuery.error.message) ||
      (recommendationsQuery.error instanceof Error && recommendationsQuery.error.message) ||
      "Failed to load business intelligence.";
    return (
      <div className="space-y-6">
        <PageHeader eyebrow="AI Surface" title="Business intelligence" description="Cross-package insights, opportunities, products, designs, and predictive readiness." actions={<ActiveDatabaseBadge />} />
        <Card className="border-destructive/30 bg-destructive/5">
          <CardHeader>
            <CardTitle className="text-base text-destructive">Business intelligence unavailable</CardTitle>
            <CardDescription>{message}</CardDescription>
          </CardHeader>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="AI Surface" title="Business intelligence" description="Cross-package insights, opportunities, products, designs, and predictive readiness." actions={<ActiveDatabaseBadge />} />

      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {summaryCards.map((card) => (
          <Card key={card.label} className="border-border bg-card shadow-sm">
            <CardContent className="p-4">
              <div className="text-xs uppercase tracking-wider text-muted-foreground">{card.label}</div>
              <div className="mt-2 text-2xl font-semibold text-foreground">{card.value}</div>
            </CardContent>
          </Card>
        ))}
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <Card className="border-border bg-card shadow-sm">
          <CardHeader>
            <CardTitle className="text-base">Package health</CardTitle>
            <CardDescription>Empty packages are shown explicitly so gaps are visible.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {Object.entries(health).map(([key, item]) => (
              <div key={key} className="flex items-center justify-between rounded-md border border-border bg-card p-3">
                <div>
                  <div className="text-sm font-medium text-foreground">{key}</div>
                  <div className="text-xs text-muted-foreground">{item.state}</div>
                </div>
                <Badge variant="outline" className="text-[10px] tabular-nums">{item.count}</Badge>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card className="border-border bg-card shadow-sm">
          <CardHeader>
            <CardTitle className="text-base">Business insights</CardTitle>
            <CardDescription>Traceable cross-package insights generated from governance, semantics, relationships, and KPI signals.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {insights.length ? insights.slice(0, 3).map((insight) => (
              <div key={insight.id ?? insight.insight_text} className="rounded-md border border-border bg-card p-3">
                <div className="text-sm font-medium text-foreground">{insight.insight_text}</div>
                <div className="mt-1 text-xs text-muted-foreground">Trace {insight.trace_id ?? "n/a"} · Confidence {Math.round((insight.confidence_score ?? 0) * 100)}%</div>
              </div>
            )) : <EmptyState icon={Sparkles} title="No business insights yet" description="Run sync to generate BI insights." />}
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <Card className="border-border bg-card shadow-sm">
          <CardHeader>
            <CardTitle className="text-base">Opportunities</CardTitle>
            <CardDescription>Canonical opportunity recommendations.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {opportunities.length ? opportunities.slice(0, 3).map((item) => (
              <div key={item.id ?? item.recommendation_text} className="rounded-md border border-border bg-card p-3">
                <div className="text-sm font-medium text-foreground">{item.recommendation_text}</div>
                <div className="mt-1 text-xs text-muted-foreground">{item.recommendation_type ?? "opportunity"} · {Math.round((item.confidence_score ?? 0) * 100)}%</div>
              </div>
            )) : <EmptyState icon={Activity} title="No opportunities yet" description="Run sync to generate opportunity recommendations." />}
          </CardContent>
        </Card>

        <Card className="border-border bg-card shadow-sm">
          <CardHeader>
            <CardTitle className="text-base">Predictive readiness</CardTitle>
            <CardDescription>Readiness for analytics and agent activation.</CardDescription>
          </CardHeader>
          <CardContent>
            {predictiveReadiness ? (
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                <div className="rounded-md border border-border bg-card p-3">
                  <div className="text-[11px] uppercase tracking-wider text-muted-foreground">Agent</div>
                  <div className="mt-1 text-sm font-medium text-foreground">{Math.round((predictiveReadiness.agent_readiness_score ?? 0) * 100)}%</div>
                </div>
                <div className="rounded-md border border-border bg-card p-3">
                  <div className="text-[11px] uppercase tracking-wider text-muted-foreground">RAG</div>
                  <div className="mt-1 text-sm font-medium text-foreground">{Math.round((predictiveReadiness.rag_score ?? 0) * 100)}%</div>
                </div>
                <div className="rounded-md border border-border bg-card p-3">
                  <div className="text-[11px] uppercase tracking-wider text-muted-foreground">SQL</div>
                  <div className="mt-1 text-sm font-medium text-foreground">{Math.round((predictiveReadiness.text_to_sql_score ?? 0) * 100)}%</div>
                </div>
              </div>
            ) : (
              <EmptyState icon={Brain} title="No predictive readiness yet" description="Run sync to calculate predictive readiness." />
            )}
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <Card className="border-border bg-card shadow-sm">
          <CardHeader>
            <CardTitle className="text-base">Data products</CardTitle>
            <CardDescription>Curated products inferred from the intelligence graph.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {dataProducts.length ? dataProducts.slice(0, 3).map((item) => (
              <div key={item.id ?? item.product_name} className="rounded-md border border-border bg-card p-3">
                <div className="text-sm font-medium text-foreground">{item.product_name}</div>
                <div className="mt-1 text-xs text-muted-foreground">{item.product_type ?? "data product"} · {Math.round((item.confidence_score ?? 0) * 100)}%</div>
              </div>
            )) : <EmptyState icon={Boxes} title="No data products yet" description="Run sync to infer curated data products." />}
          </CardContent>
        </Card>

        <Card className="border-border bg-card shadow-sm">
          <CardHeader>
            <CardTitle className="text-base">Warehouse designs</CardTitle>
            <CardDescription>Designs derived from relationships and business flow.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {warehouseDesigns.length ? warehouseDesigns.slice(0, 3).map((item) => (
              <div key={item.id ?? item.design_name} className="rounded-md border border-border bg-card p-3">
                <div className="text-sm font-medium text-foreground">{item.design_name}</div>
                <div className="mt-1 text-xs text-muted-foreground">{item.design_type ?? "design"} · {Math.round((item.confidence_score ?? 0) * 100)}%</div>
              </div>
            )) : <EmptyState icon={TrendingUp} title="No warehouse designs yet" description="Run sync to infer warehouse structures." />}
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
