import { Database, Activity, CheckCircle2, XCircle, ShieldCheck, BookOpenText, Network, TrendingUp, Boxes, Sparkles, ArrowRight, RefreshCw, Play, History, FileDiff, Brain, Lightbulb } from "lucide-react";
import { Link } from "@tanstack/react-router";
import { PageHeader } from "@/components/page-header";
import { MetricCard } from "@/components/metric-card";
import { StatusBadge, type StatusKind } from "@/components/status-badge";
import { CoverageBar } from "@/components/coverage-bar";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { EmptyState } from "@/components/empty-state";
import { ActiveDatabaseBadge } from "@/components/common/ActiveDatabaseBadge";
import { TraceLink } from "@/components/common/TraceLink";
import { useDatabaseContext } from "@/context/database-context";
import { useDashboard } from "@/hooks/useDashboard";
import { useJobs, useStageProgress } from "@/hooks/useJobs";
import { useReadiness } from "@/hooks/useReadiness";
import { useRemediation } from "@/hooks/useRemediation";
import { useBusinessEvents } from "@/hooks/useBusinessEvents";
import { useBusinessInsights } from "@/hooks/useBusinessInsights";
import { useBusinessIntelligence } from "@/hooks/useBusinessIntelligence";
import { useAgentMemoryHistory } from "@/hooks/useAgentMemory";
import { useSemanticCache } from "@/hooks/useSemanticCache";
import { useRetrievalEvaluation } from "@/hooks/useRetrievalEvaluation";
import { useReadinessHistory } from "@/hooks/useReadinessHistory";
import { ReadinessTrendCard } from "@/components/readiness/ReadinessTrendCard";

export function DashboardPage() {
  const { selectedDatabase } = useDatabaseContext();
  const databaseId = selectedDatabase?.database_id ?? null;
  const { data } = useDashboard(databaseId);
  const { data: readiness } = useReadiness(databaseId);
  const { data: remediation } = useRemediation(databaseId);
  const { data: jobs = [] } = useJobs(20);
  const { data: stageProgress } = useStageProgress(databaseId);
  const { data: businessEvents } = useBusinessEvents(databaseId);
  const { data: businessInsights } = useBusinessInsights(databaseId);
  const { data: agentMemory } = useAgentMemoryHistory(databaseId, 5);
  const { data: semanticCache } = useSemanticCache(databaseId);
  const { data: retrievalEvaluation } = useRetrievalEvaluation(databaseId);
  const { data: readinessHistory } = useReadinessHistory(databaseId);
  const [opportunitiesQuery, dataProductsQuery, warehouseDesignsQuery, recommendationsQuery, predictiveReadinessQuery] = useBusinessIntelligence(databaseId);
  const insights = businessInsights?.insights ?? [];
  const opportunities = opportunitiesQuery.data?.opportunities ?? [];
  const dataProducts = dataProductsQuery.data?.data_products ?? [];
  const warehouseDesigns = warehouseDesignsQuery.data?.warehouse_designs ?? [];
  const recommendations = recommendationsQuery.data?.recommendations ?? [];
  const predictiveReadiness = predictiveReadinessQuery.data?.predictive_readiness;
  const readinessScores = readiness?.scores;
  const firstStage = stageProgress?.stages?.[0] as
    | {
        estimated_input_tokens?: number | null;
        actual_input_tokens?: number | null;
        actual_output_tokens?: number | null;
        completion_truncated?: boolean | null;
      }
    | undefined;

  const coverage = [
    { label: "Governance", value: Math.min(100, data?.governance_coverage ?? 0), icon: ShieldCheck, to: "/governance" },
    { label: "Semantics", value: Math.min(100, data?.semantic_coverage ?? 0), icon: BookOpenText, to: "/semantics" },
    { label: "Relationships", value: Math.min(100, data?.relationship_coverage ?? 0), icon: Network, to: "/relationships" },
    { label: "KPI", value: Math.min(100, data?.kpi_count ? 100 : 0), icon: TrendingUp, to: "/kpi" },
  ];
  const activity = jobs.slice(0, 5).map((job) => ({
    time: job.completed_at ?? job.started_at ?? "n/a",
    title: `Job #${job.id} ${job.job_type}`,
    meta: `db ${job.database_id} · ${job.progress_percentage}% · ${job.failure_reason ?? "no failure"}`,
    status: job.status?.toLowerCase() as StatusKind,
  }));
  const pipeline = stageProgress?.stages?.length
    ? stageProgress.stages.map((stage) => ({
        stage: stage.stage,
        value: stage.progress_percentage,
        status: stage.status as StatusKind,
      }))
    : [
        { stage: "Metadata", value: data?.schemas ? 100 : 0, status: data?.schemas ? "success" : "neutral" },
        { stage: "Governance", value: data?.governance_coverage ? 100 : 0, status: data?.governance_coverage ? "success" : "neutral" },
        { stage: "Semantics", value: data?.semantic_coverage ? 100 : 0, status: data?.semantic_coverage ? "success" : "neutral" },
        { stage: "Relationships", value: data?.relationship_coverage ? 100 : 0, status: data?.relationship_coverage ? "success" : "neutral" },
        { stage: "KPI", value: data?.kpi_count ? 100 : 0, status: data?.kpi_count ? "success" : "neutral" },
        { stage: "Embeddings", value: data?.embeddings_total ? Math.min(100, (data.embeddings_ready / Math.max(1, data.embeddings_total)) * 100) : 0, status: data?.embeddings_ready ? "success" : "neutral" },
        { stage: "Readiness", value: readinessScores?.overall_score ?? data?.readiness_score ?? 0, status: (readiness?.readiness_status?.toLowerCase() as StatusKind) ?? "neutral" },
      ];
  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Platform"
        title="Dashboard"
        description="Real-time health of metadata sync, AI intelligence generation, and downstream agent readiness."
        actions={
          <>
            <ActiveDatabaseBadge />
            <Badge variant="outline" className="gap-1.5 text-[11px]">
              Cache {data?.cache_status ?? "live"}
            </Badge>
            <Button variant="outline" size="sm" className="gap-1.5" onClick={() => window.location.reload()}>
              <RefreshCw className="h-3.5 w-3.5" /> Refresh
            </Button>
            <Button asChild size="sm" className="gap-1.5 bg-gradient-to-br from-primary to-primary-glow text-primary-foreground shadow-[var(--shadow-glow)] hover:opacity-95">
              <Link to="/jobs">
                <Play className="h-3.5 w-3.5" /> Run pipeline
              </Link>
            </Button>
          </>
        }
      />
      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          label="Current database"
          value={selectedDatabase?.database_name ?? "n/a"}
          hint={selectedDatabase ? `#${selectedDatabase.database_id} · ${selectedDatabase.db_type}` : "No database selected"}
          icon={Database}
          tone="default"
        />
        <MetricCard label="Total databases" value={String(data?.total_databases ?? 0)} hint="Connected sources" icon={Database} tone="info" />
        <MetricCard label="Tables in current DB" value={String(data?.tables ?? 0)} hint="Selected database only" icon={Boxes} tone="success" />
        <MetricCard label="Active jobs" value={String(data?.active_jobs ?? 0)} hint="Running or queued" icon={Activity} tone="default" />
        <MetricCard label="Completed (24h)" value={String(data?.completed_jobs_24h ?? 0)} hint="Pipeline completions" icon={CheckCircle2} tone="success" />
        <MetricCard label="Failed (24h)" value={String(data?.failed_jobs_24h ?? 0)} hint="Pipeline failures" icon={XCircle} tone="danger" />
      </section>
      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Prompt packages" value={String(data?.prompt_packages ?? 0)} hint="Canonical prompt artifacts" icon={Sparkles} tone="info" />
        <MetricCard label="Latest prompt" value={data?.latest_prompt_at ? new Date(data.latest_prompt_at).toLocaleString() : "n/a"} hint="Most recent generation" icon={History} tone="default" />
        <MetricCard label="Prompt observability" value={String(data?.prompt_packages ?? 0)} hint="Versioned and traceable" icon={FileDiff} tone="success" />
        <MetricCard label="Prompt embeddings" value={String(data?.prompt_embeddings ?? 0)} hint="Generated prompt vectors" icon={Brain} tone="success" />
      </section>
      <section className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <MetricCard label="Semantic cache" value={String(data?.semantic_cache_entries ?? semanticCache?.caches?.length ?? 0)} hint="Cached retrieval responses" icon={FileDiff} tone="info" />
        <MetricCard label="Retrieval evaluations" value={String(data?.retrieval_evaluations ?? retrievalEvaluation?.evaluations?.length ?? 0)} hint="Search and rerank quality" icon={Activity} tone="default" />
        <MetricCard label="Retrieval logs" value={String(data?.retrieval_logs ?? 0)} hint="Hybrid search runs" icon={History} tone="success" />
      </section>
      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Estimated input" value={String(firstStage?.estimated_input_tokens ?? 0)} hint="prompt tokens" icon={Sparkles} tone="info" />
        <MetricCard label="Actual input" value={String(firstStage?.actual_input_tokens ?? 0)} hint="observed prompt tokens" icon={Activity} tone="default" />
        <MetricCard label="Actual output" value={String(firstStage?.actual_output_tokens ?? 0)} hint="observed completion tokens" icon={FileDiff} tone="success" />
        <MetricCard label="Truncated" value={firstStage?.completion_truncated ? "yes" : "no"} hint="finish reason" icon={XCircle} tone="warning" />
      </section>
      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <MetricCard
          label="Remediation actions"
          value={String(remediation?.remediations?.length ?? 0)}
          hint="Readiness follow-ups written during recompute"
          icon={Lightbulb}
          tone="warning"
        />
        <MetricCard
          label="Readiness history"
          value={String(readinessHistory?.snapshots?.length ?? 0)}
          hint="Persisted maturity snapshots"
          icon={History}
          tone="info"
        />
      </section>
      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Lifecycle events" value={String(businessEvents?.events?.length ?? 0)} hint="Detected from metadata" icon={Activity} tone="info" />
        <MetricCard label="Top event" value={businessEvents?.events?.[0]?.event_name ?? "n/a"} hint={businessEvents?.events?.[0]?.event_type ?? "no event yet"} icon={Sparkles} tone="success" />
      </section>
      <section className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Business event evidence</CardTitle>
            <CardDescription>Source tables and traceability for detected lifecycle events.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {businessEvents?.events?.length ? (
              businessEvents.events.slice(0, 3).map((event, index) => (
                <div key={`${event.id ?? event.event_name}-${index}`} className="rounded-md border border-border bg-card p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="text-sm font-medium text-foreground">{event.event_name}</div>
                    <Badge variant="outline" className="text-[10px] uppercase">{event.event_type ?? "unknown"}</Badge>
                  </div>
                  <div className="mt-2 text-xs text-muted-foreground">
                    Confidence: {Math.round((event.confidence_score ?? 0) * 100)}%{event.trace_id ? ` · Trace ${event.trace_id}` : ""}
                  </div>
                  <TraceLink traceId={event.trace_id} label="Open trace" className="mt-2 text-[11px]" />
                  <div className="mt-2 text-xs text-muted-foreground">
                    Source tables: {(event.source_tables ?? []).length ? event.source_tables.join(", ") : "n/a"}
                  </div>
                </div>
              ))
            ) : (
              <EmptyState icon={Activity} title="No business events yet" description="Lifecycle events will appear after sync detects metadata-driven business events." />
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Business insight traceability</CardTitle>
            <CardDescription>Trace IDs and evidence behind persisted cross-package insights.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {insights.length ? (
              insights.slice(0, 3).map((insight) => (
                <div key={insight.id ?? insight.insight_text} className="rounded-md border border-border bg-card p-3">
                  <div className="text-sm font-medium text-foreground">{insight.insight_text}</div>
                  <div className="mt-2 text-xs text-muted-foreground">
                    Trace: {insight.trace_id ?? "n/a"} · Confidence: {Math.round((insight.confidence_score ?? 0) * 100)}%
                  </div>
                  <TraceLink traceId={insight.trace_id} label="Open trace" className="mt-2 text-[11px]" />
                  <div className="mt-2 flex flex-wrap gap-2">
                    {(insight.evidence ?? []).slice(0, 5).map((item, index) => (
                      <Badge key={`${insight.id ?? index}`} variant="outline" className="text-[10px] uppercase">
                        {String((item as Record<string, unknown>).evidence_type ?? (item as Record<string, unknown>).source ?? "evidence")}
                      </Badge>
                    ))}
                  </div>
                </div>
              ))
            ) : (
              <EmptyState icon={Sparkles} title="No business insights yet" description="Run sync to generate traceable business insights from persisted packages." />
            )}
          </CardContent>
        </Card>
      </section>
      <section className="grid grid-cols-1 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between gap-4 space-y-0">
            <div className="space-y-1">
              <CardTitle className="text-base">Business insights</CardTitle>
              <CardDescription>AI-generated cross-package insights from governance, semantics, relationships, and KPI signals.</CardDescription>
            </div>
            <Badge variant="outline" className="border-border text-[11px] text-muted-foreground">
              live
            </Badge>
          </CardHeader>
          <CardContent className="space-y-3">
            {insights.length ? (
              insights.slice(0, 3).map((insight) => (
                <div key={insight.id ?? insight.insight_text} className="rounded-lg border border-border bg-card p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <div className="text-sm font-medium text-foreground">{insight.insight_text}</div>
                    <Badge variant="outline" className="text-[10px] uppercase">
                      {insight.impact_level ?? "unknown"}
                    </Badge>
                  </div>
                  <div className="mt-2 text-xs text-muted-foreground">
                    Confidence: {Math.round((insight.confidence_score ?? 0) * 100)}%{insight.trace_id ? ` · Trace ${insight.trace_id}` : ""}
                  </div>
                  <TraceLink traceId={insight.trace_id} label="Open trace" className="mt-2 text-[11px]" />
                </div>
              ))
            ) : (
              <EmptyState
                icon={Sparkles}
                title="No business insights yet"
                description="Run sync to generate cross-package insights from governance, semantics, relationships, and KPIs."
              />
            )}
          </CardContent>
        </Card>
      </section>
      <section className="grid grid-cols-1 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between gap-4 space-y-0">
            <div className="space-y-1">
              <CardTitle className="text-base">Business intelligence packages</CardTitle>
              <CardDescription>Opportunity recommendations, data products, warehouse designs, recommendations, and predictive readiness.</CardDescription>
            </div>
            <Badge variant="outline" className="border-border text-[11px] text-muted-foreground">
              live
            </Badge>
          </CardHeader>
          <CardContent>
            <Tabs defaultValue="opportunities">
              <TabsList className="flex flex-wrap">
                <TabsTrigger value="opportunities">Opportunities</TabsTrigger>
                <TabsTrigger value="data-products">Data Products</TabsTrigger>
                <TabsTrigger value="warehouse">Warehouse</TabsTrigger>
                <TabsTrigger value="recommendations">Recommendations</TabsTrigger>
                <TabsTrigger value="predictive">Predictive</TabsTrigger>
              </TabsList>
              <TabsContent value="opportunities" className="pt-4">
                <div className="space-y-2">
                  {opportunities.length ? opportunities.slice(0, 3).map((item) => (
                    <div key={item.id ?? item.recommendation_text} className="rounded-md border border-border bg-card p-3">
                      <div className="text-sm font-medium text-foreground">{item.recommendation_text}</div>
                      <div className="mt-1 text-xs text-muted-foreground">{item.recommendation_type ?? "opportunity"} · {Math.round((item.confidence_score ?? 0) * 100)}%</div>
                    </div>
                  )) : <EmptyState icon={Sparkles} title="No opportunities yet" description="Run sync to generate AI opportunity recommendations." />}
                </div>
              </TabsContent>
              <TabsContent value="data-products" className="pt-4">
                <div className="space-y-2">
                  {dataProducts.length ? dataProducts.slice(0, 3).map((item) => (
                    <div key={item.id ?? item.product_name} className="rounded-md border border-border bg-card p-3">
                      <div className="text-sm font-medium text-foreground">{item.product_name}</div>
                      <div className="mt-1 text-xs text-muted-foreground">{item.product_type ?? "data product"} · {Math.round((item.confidence_score ?? 0) * 100)}%</div>
                    </div>
                  )) : <EmptyState icon={Boxes} title="No data products yet" description="Run sync to infer curated data products." />}
                </div>
              </TabsContent>
              <TabsContent value="warehouse" className="pt-4">
                <div className="space-y-2">
                  {warehouseDesigns.length ? warehouseDesigns.slice(0, 3).map((item) => (
                    <div key={item.id ?? item.design_name} className="rounded-md border border-border bg-card p-3">
                      <div className="text-sm font-medium text-foreground">{item.design_name}</div>
                      <div className="mt-1 text-xs text-muted-foreground">{item.design_type ?? "design"} · {Math.round((item.confidence_score ?? 0) * 100)}%</div>
                    </div>
                  )) : <EmptyState icon={Network} title="No warehouse designs yet" description="Run sync to infer warehouse structures." />}
                </div>
              </TabsContent>
              <TabsContent value="recommendations" className="pt-4">
                <div className="space-y-2">
                  {recommendations.length ? recommendations.slice(0, 3).map((item) => (
                    <div key={item.id ?? item.recommendation_text} className="rounded-md border border-border bg-card p-3">
                      <div className="text-sm font-medium text-foreground">{item.recommendation_text}</div>
                      <div className="mt-1 text-xs text-muted-foreground">{item.priority ?? "medium"} · {Math.round((item.confidence_score ?? 0) * 100)}%</div>
                    </div>
                  )) : <EmptyState icon={Activity} title="No recommendations yet" description="Run sync to generate actionable recommendations." />}
                </div>
              </TabsContent>
              <TabsContent value="predictive" className="pt-4">
                {predictiveReadiness ? (
                  <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                    <MetricCard label="Agent readiness" value={`${Math.round((predictiveReadiness.agent_readiness_score ?? 0) * 100)}%`} icon={Sparkles} tone="info" />
                    <MetricCard label="Text-to-SQL" value={`${Math.round((predictiveReadiness.text_to_sql_score ?? 0) * 100)}%`} icon={Activity} tone="success" />
                    <MetricCard label="RAG" value={`${Math.round((predictiveReadiness.rag_score ?? 0) * 100)}%`} icon={Activity} tone="default" />
                  </div>
                ) : (
                  <EmptyState icon={Sparkles} title="No predictive readiness yet" description="Run sync to score the database for agents, analytics, and forecasting." />
                )}
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>
      </section>
      <section className="grid grid-cols-1 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between gap-4 space-y-0">
            <div className="space-y-1">
              <CardTitle className="text-base">Agent memory</CardTitle>
              <CardDescription>Recent query history and long-term memory records for the selected database.</CardDescription>
            </div>
            <Badge variant="outline" className="border-border text-[11px] text-muted-foreground">
              live
            </Badge>
          </CardHeader>
          <CardContent className="space-y-3">
            {(agentMemory?.results?.length ?? 0) ? (
              agentMemory!.results.slice(0, 3).map((item) => (
                <div key={item.id} className="rounded-md border border-border bg-card p-3">
                  <div className="flex items-center justify-between gap-3">
                    <div className="truncate text-sm font-medium text-foreground">{item.query_text}</div>
                    <Badge variant="outline" className="text-[10px] uppercase">{item.memory_type}</Badge>
                  </div>
                  <div className="mt-1 line-clamp-2 text-xs text-muted-foreground">{item.response_text ?? "No response stored."}</div>
                  <div className="mt-2 text-[11px] text-muted-foreground">
                    Trace: {item.trace_id ?? "n/a"} · Tags: {item.tags?.length ? item.tags.join(", ") : "none"}
                    <TraceLink traceId={item.trace_id} label="Open trace" className="ml-1 text-[11px]" />
                  </div>
                </div>
              ))
            ) : (
              <EmptyState icon={History} title="No agent memory yet" description="Agent history will appear once interactions are stored." />
            )}
          </CardContent>
        </Card>
      </section>
      <section className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader className="flex flex-row items-center justify-between gap-4 space-y-0">
            <div className="space-y-1">
              <CardTitle className="text-base">Intelligence coverage</CardTitle>
              <CardDescription>Per-package coverage across all connected sources.</CardDescription>
            </div>
            <Badge variant="outline" className="border-border text-[11px] text-muted-foreground">
              live
            </Badge>
          </CardHeader>
          <CardContent className="space-y-4">
            {coverage.length ? (
              coverage.map((c) => (
                <Link key={c.label} to={c.to} className="group flex items-center gap-3 rounded-lg border border-border bg-card p-3 transition hover:border-primary/40 hover:shadow-[var(--shadow-md)]">
                  <div className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-gradient-to-br from-primary/15 to-primary/0 text-primary">
                    <c.icon className="h-4 w-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-2 text-sm">
                      <span className="truncate font-medium text-foreground">{c.label}</span>
                      <span className="tabular-nums text-muted-foreground">{c.value}%</span>
                    </div>
                    <CoverageBar value={c.value} className="mt-1.5" />
                  </div>
                  <ArrowRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground opacity-0 transition group-hover:opacity-100" />
                </Link>
              ))
            ) : (
              <EmptyState icon={Sparkles} title="No intelligence packages yet" description="Connect a database and run sync to populate governance, semantics, relationships, KPI, and embeddings." />
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">AI Readiness</CardTitle>
            <CardDescription>Composite score across all intelligence packages.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="relative mx-auto grid h-40 w-40 place-items-center">
              <svg className="absolute inset-0 -rotate-90" viewBox="0 0 100 100">
                <circle cx="50" cy="50" r="44" fill="none" stroke="var(--muted)" strokeWidth="8" />
              </svg>
              <div className="text-center">
                <div className="text-3xl font-semibold tracking-tight text-foreground">{readinessScores?.overall_score ?? data?.readiness_score ?? 0}</div>
                <div className="text-[10px] uppercase tracking-wider text-muted-foreground">Ready</div>
              </div>
            </div>
            <Separator />
            <ul className="space-y-2 text-xs">
              <li className="flex items-center justify-between">
                <span className="text-muted-foreground">Governance</span>
                <span className="font-medium tabular-nums text-foreground">{readinessScores?.metadata_score ?? 0}</span>
              </li>
              <li className="flex items-center justify-between">
                <span className="text-muted-foreground">Semantics</span>
                <span className="font-medium tabular-nums text-foreground">{readinessScores?.semantic_score ?? 0}</span>
              </li>
              <li className="flex items-center justify-between">
                <span className="text-muted-foreground">Agent context</span>
                <span className="font-medium tabular-nums text-foreground">{readinessScores?.prompt_score ?? 0}</span>
              </li>
            </ul>
            <Button asChild variant="outline" size="sm" className="w-full">
              <Link to="/readiness">
                View full report <ArrowRight className="ml-1 h-3.5 w-3.5" />
              </Link>
            </Button>
          </CardContent>
        </Card>
      </section>
      <section className="grid grid-cols-1 gap-4">
        <ReadinessTrendCard snapshots={readinessHistory?.snapshots ?? []} />
      </section>
      <section className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader className="flex flex-row items-center justify-between gap-4 space-y-0">
            <div className="space-y-1">
              <CardTitle className="text-base">Pipeline health</CardTitle>
              <CardDescription>Current execution across the intelligence pipeline.</CardDescription>
            </div>
            <Button asChild variant="ghost" size="sm" className="text-xs">
              <Link to="/jobs">
                Open jobs <ArrowRight className="ml-1 h-3 w-3" />
              </Link>
            </Button>
          </CardHeader>
          <CardContent>
            {pipeline.length ? (
              <ol className="relative">
                {pipeline.map((p, i) => (
                  <li key={p.stage} className="grid grid-cols-[24px_minmax(0,1fr)_auto] items-center gap-3 py-2.5">
                    <div className="relative grid place-items-center">
                      <div className="h-2 w-2 rounded-full bg-primary shadow-[0_0_0_4px_var(--background),0_0_0_5px_var(--border)]" />
                      {i !== pipeline.length - 1 && <div className="absolute top-3 h-[26px] w-px bg-border" />}
                    </div>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 text-sm">
                        <span className="truncate font-medium text-foreground">{p.stage}</span>
                      </div>
                      <CoverageBar value={p.value} className="mt-1" />
                    </div>
                    <StatusBadge status={p.status} />
                  </li>
                ))}
              </ol>
            ) : (
              <EmptyState icon={Activity} title="No pipeline activity" description="Pipeline status will appear here after the first backend sync." />
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Recent activity</CardTitle>
            <CardDescription>Latest jobs and platform events.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {activity.length ? (
              activity.map((a, i) => (
                <div key={i} className="flex items-start gap-3 border-b border-border pb-3 last:border-none last:pb-0">
                  <div className="mt-0.5">
                    <StatusBadge status={a.status} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-medium text-foreground">{a.title}</div>
                    <div className="truncate text-xs text-muted-foreground">{a.meta}</div>
                  </div>
                  <span className="shrink-0 text-[11px] text-muted-foreground">{a.time}</span>
                </div>
              ))
            ) : (
              <EmptyState icon={Activity} title="No recent activity" description="Activity will populate once jobs start running." />
            )}
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
