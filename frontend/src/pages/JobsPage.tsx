import { Fragment, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCw, Filter, Clock, Hash, Cpu, Activity, ChevronRight, ChevronDown, Eye, EyeOff } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { StatusBadge } from "@/components/status-badge";
import { CoverageBar } from "@/components/coverage-bar";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ScrollArea } from "@/components/ui/scroll-area";
import { EmptyState } from "@/components/empty-state";
import { jobsApi } from "@/api/jobs";
import { metadataApi } from "@/api/metadata";
import type { PipelineJob } from "@/types/backend";
import { useDatabaseContext } from "@/context/database-context";
import { useStageProgress } from "@/hooks/useJobs";
import { usePipelineExecutions, useStageExecutions } from "@/hooks/usePipelineExecutions";
import { useBusinessInsights } from "@/hooks/useBusinessInsights";
import { useBusinessIntelligence } from "@/hooks/useBusinessIntelligence";
import { TraceLink } from "@/components/common/TraceLink";
import { queryKeys } from "@/lib/query-keys";

const normalizeJobStatus = (status?: string | null) => {
  const value = (status ?? "unknown").trim().toLowerCase();
  if (["completed", "complete", "done", "success"].includes(value)) return "success";
  if (["running", "in_progress", "in-progress", "processing"].includes(value)) return "running";
  if (["queued", "pending"].includes(value)) return "queued";
  if (["failed", "error", "failure"].includes(value)) return "failed";
  if (["cancelled", "canceled", "partial"].includes(value)) return "warning";
  if (["paused", "stopped"].includes(value)) return "paused";
  return "unknown";
};

export function JobsPage() {
  const queryClient = useQueryClient();
  const { selectedDatabaseId: selectedDb } = useDatabaseContext();
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [jobTypeFilter, setJobTypeFilter] = useState("ALL");
  const [expanded, setExpanded] = useState<number | null>(null);
  const [selectedJobId, setSelectedJobId] = useState<number | null>(null);
  const [viewMode, setViewMode] = useState<"business" | "technical">("business");

  const { data: jobs = [] } = useQuery({
    queryKey: queryKeys.jobs(statusFilter),
    queryFn: () => jobsApi.list(300),
    refetchInterval: 5000,
  });

  const filteredJobs = useMemo(() => {
    let rows = jobs;
    if (selectedDb) rows = rows.filter((j) => j.database_id === selectedDb);
    if (statusFilter !== "ALL") rows = rows.filter((j) => normalizeJobStatus(j.status).toUpperCase() === statusFilter);
    if (jobTypeFilter !== "ALL") rows = rows.filter((j) => j.job_type === jobTypeFilter);
    return rows;
  }, [jobTypeFilter, jobs, selectedDb, statusFilter]);

  const dbJobs = filteredJobs;
  const counts = useMemo(
    () =>
      dbJobs.reduce<Record<string, number>>((acc, job) => {
        const key = normalizeJobStatus(job.status);
        return { ...acc, [key]: (acc[key] ?? 0) + 1 };
      }, {}),
    [dbJobs],
  );

  const runMutation = useMutation({
    mutationFn: () => {
      if (!selectedDb) {
        throw new Error("Select a database before running diagnostics.");
      }
      return metadataApi.diagnose(selectedDb);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.jobs(statusFilter) }),
  });

  const selectedJob = dbJobs.find((j) => j.id === selectedJobId);
  const { data: stageProgress } = useStageProgress(selectedDb);
  const { data: businessInsights } = useBusinessInsights(selectedDb);
  const [opportunitiesQuery, dataProductsQuery, warehouseDesignsQuery, recommendationsQuery, predictiveReadinessQuery] =
    useBusinessIntelligence(selectedDb);
  const { data: pipelineExecutions } = usePipelineExecutions(selectedDb, 10);
  const { data: stageExecutions } = useStageExecutions(selectedDb, pipelineExecutions?.executions?.[0]?.id ?? null, 20);
  const insights = businessInsights?.insights ?? [];
  const opportunities = opportunitiesQuery.data?.opportunities ?? [];
  const dataProducts = dataProductsQuery.data?.data_products ?? [];
  const warehouseDesigns = warehouseDesignsQuery.data?.warehouse_designs ?? [];
  const recommendations = recommendationsQuery.data?.recommendations ?? [];
  const predictiveReadiness = predictiveReadinessQuery.data?.predictive_readiness;
  const pipelineStages =
    stageProgress?.stages?.length
      ? stageProgress.stages
      : ["metadata", "governance", "semantics", "relationships", "kpi", "prompt", "embeddings", "readiness"].map((stage) => ({
          stage,
          status: "pending",
          progress_percentage: 0,
          retries: 0,
          depends_on: [],
        }));

  const postReadinessCards = [
    {
      label: "Opportunity recommendations",
      count: opportunities.length,
      status: opportunities.length ? "success" : "pending",
      tone: "Opportunities generated after readiness completes.",
    },
    {
      label: "Data products",
      count: dataProducts.length,
      status: dataProducts.length ? "success" : "pending",
      tone: "Curated datasets inferred from persisted intelligence.",
    },
    {
      label: "Warehouse designs",
      count: warehouseDesigns.length,
      status: warehouseDesigns.length ? "success" : "pending",
      tone: "Proposed fact and dimension structures.",
    },
    {
      label: "Recommendations",
      count: recommendations.length,
      status: recommendations.length ? "success" : "pending",
      tone: "Actionable follow-ups generated after readiness.",
    },
    {
      label: "Predictive readiness",
      count: predictiveReadiness ? 1 : 0,
      status: predictiveReadiness ? "success" : "pending",
      tone: "Agent, RAG, text-to-SQL, and forecasting readiness.",
    },
  ];

  const statusFilters = ["ALL", "QUEUED", "RUNNING", "FAILED", "COMPLETED", "CANCELLED"];
  const typeFilters = ["ALL", "SYNC", "SEMANTIC_ENRICHMENT", "EMBEDDINGS", "RELATIONSHIP_GRAPH", "PROMPT_GENERATION", "READINESS", "ARTIFACT_PACKAGING", "AI_CONTEXT"];
  const overallProgress = stageProgress?.overall_progress_percentage ?? 0;
  const selectedExecutionTrace = selectedJob?.execution_trace;

  const stageIcon = (status?: string | null) => {
    const value = (status ?? "unknown").toLowerCase();
    if (["completed", "complete", "done", "success"].includes(value)) return "✓";
    if (["running", "in_progress", "in-progress", "processing"].includes(value)) return "⟳";
    if (["failed", "error", "failure"].includes(value)) return "✗";
    if (["queued", "pending"].includes(value)) return "…";
    return "•";
  };

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Platform"
        title="Jobs & operations"
        description="Business-first pipeline progress with optional technical drill-down."
        actions={
          <>
            <Badge variant="outline" className="gap-1.5 text-[11px]">
              Progress {stageProgress?.cache_status ?? "live"}
            </Badge>
            <Button
              variant="outline"
              size="sm"
              className="gap-1.5"
              onClick={() => document.getElementById("job-filters")?.scrollIntoView({ behavior: "smooth", block: "start" })}
            >
              <Filter className="h-3.5 w-3.5" /> Filters
            </Button>
            <Button variant="outline" size="sm" className="gap-1.5" onClick={() => queryClient.invalidateQueries({ queryKey: queryKeys.jobs(statusFilter) })}>
              <RefreshCw className="h-3.5 w-3.5" /> Refresh
            </Button>
          </>
        }
      />

      <section className="grid gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader>
            <CardTitle className="text-base">Full sync pipeline</CardTitle>
            <CardDescription>Metadata → Governance → Semantics → Relationships → KPI → Prompt → Embeddings → Readiness.</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="rounded-xl border border-border bg-muted/20 p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="text-xs uppercase tracking-wider text-muted-foreground">Database analysis</div>
                    <div className="text-2xl font-semibold text-foreground">{Math.round(overallProgress)}% complete</div>
                    <div className="text-xs text-muted-foreground">
                      {stageProgress?.overall_status === "running"
                        ? "Running now"
                        : stageProgress?.overall_status === "failed"
                          ? "One or more stages failed"
                          : "Idle"}
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-[10px] uppercase sm:grid-cols-4">
                    <Badge variant="outline">Completed {stageProgress?.completed_stages ?? 0}</Badge>
                    <Badge variant="outline">Running {stageProgress?.running_stages ?? 0}</Badge>
                    <Badge variant="outline">Failed {stageProgress?.failed_stages ?? 0}</Badge>
                    <Badge variant="outline">Pending {stageProgress?.pending_stages ?? 0}</Badge>
                  </div>
                </div>
                <div className="mt-4">
                  <CoverageBar value={overallProgress} />
                </div>
              </div>
              {dbJobs.length ? (
                <ol className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
                  {pipelineStages.map((item: any, index: number) => (
                    <li key={item.stage} className="rounded-md border border-border bg-card p-3">
                      <div className="mb-2 flex items-center justify-between gap-2">
                        <span className="truncate text-xs font-medium text-foreground">
                          {index + 1}. {item.stage.replaceAll("_", " ")}
                        </span>
                        <Badge variant="outline" className="text-[10px] uppercase">
                          {stageIcon(item.status)}
                        </Badge>
                      </div>
                      <CoverageBar value={item.progress_percentage} />
                      <div className="mt-2 flex items-center justify-between text-[11px] text-muted-foreground">
                        <span>{item.status}</span>
                        <span>{Math.round(item.progress_percentage ?? 0)}%</span>
                      </div>
                      <div className="mt-1 text-[11px] text-muted-foreground">
                        {item.failure_reason ? item.failure_reason : item.depends_on?.length ? `Depends on ${item.depends_on.join(", ")}` : "Ready"}
                      </div>
                    </li>
                  ))}
                </ol>
              ) : (
                <EmptyState icon={Activity} title="No active pipeline" description="Run a sync to populate pipeline stages and execution history." />
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Post-readiness work</CardTitle>
            <CardDescription>Business-intelligence generation that runs after readiness completes.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-1">
              {postReadinessCards.map((item) => (
                <div key={item.label} className="rounded-md border border-border bg-card p-3">
                  <div className="flex items-center justify-between gap-2">
                    <div className="text-sm font-medium text-foreground">{item.label}</div>
                    <Badge variant="outline" className="text-[10px] uppercase">
                      {item.status}
                    </Badge>
                  </div>
                  <div className="mt-1 text-2xl font-semibold text-foreground">{item.count}</div>
                  <div className="mt-1 text-xs text-muted-foreground">{item.tone}</div>
                </div>
              ))}
            </div>
            <div className="rounded-md border border-border bg-muted/20 p-3">
              <div className="text-xs uppercase tracking-wider text-muted-foreground">Recent insight traceability</div>
              {insights.length ? (
                <div className="mt-2 space-y-2">
                  {insights.slice(0, 3).map((insight) => (
                    <div key={insight.id ?? insight.insight_text} className="rounded-md border border-border bg-card p-3">
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <div className="truncate text-sm font-medium text-foreground">{insight.insight_text}</div>
                          <div className="mt-1 text-xs text-muted-foreground">Confidence: {Math.round((insight.confidence_score ?? 0) * 100)}%</div>
                          <div className="mt-1 text-xs text-muted-foreground">Trace: {insight.trace_id ?? "n/a"}</div>
                        </div>
                        <Badge variant="outline" className="text-[10px] uppercase">
                          {insight.impact_level ?? "unknown"}
                        </Badge>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState icon={Activity} title="No post-readiness work yet" description="Business-intelligence packages appear after readiness completes successfully." />
              )}
            </div>
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Pipeline executions</CardTitle>
            <CardDescription>Persisted end-to-end runs for the selected database.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            <div className="flex justify-end">
              <Button variant="outline" size="sm" onClick={() => setViewMode((mode) => (mode === "business" ? "technical" : "business"))}>
                {viewMode === "business" ? (
                  <>
                    <Eye className="mr-1.5 h-3.5 w-3.5" />
                    Technical view
                  </>
                ) : (
                  <>
                    <EyeOff className="mr-1.5 h-3.5 w-3.5" />
                    Business view
                  </>
                )}
              </Button>
            </div>
            {pipelineExecutions?.executions?.length ? (
              pipelineExecutions.executions.map((execution) => (
                <div key={execution.id} className="rounded-md border border-border bg-card p-3">
                  <div className="flex items-center justify-between gap-2">
                    <div className="text-sm font-medium text-foreground">Sync Run #{execution.id}</div>
                    <Badge variant="outline" className="text-[10px] uppercase">
                      {normalizeJobStatus(execution.status)}
                    </Badge>
                  </div>
                  {viewMode === "technical" ? (
                    <>
                      <div className="mt-1 flex flex-wrap gap-2 text-[10px] uppercase">
                        <Badge variant="outline">Context {execution.used_context ? "yes" : "no"}</Badge>
                        <Badge variant="outline">Source {execution.context_source ?? "persisted"}</Badge>
                        <Badge variant="outline">Fallback {execution.fallback_reason ?? "none"}</Badge>
                      </div>
                      <div className="mt-1 text-xs text-muted-foreground">
                        Trace: {execution.trace_id ?? "n/a"} · Model: {execution.model_name ?? "n/a"}
                      </div>
                      <TraceLink traceId={execution.trace_id} label="Open trace" className="mt-2 text-[11px]" />
                      <div className="mt-1 text-xs text-muted-foreground">
                        Started: {execution.start_time ?? "n/a"} · Duration: {execution.duration_seconds?.toFixed(2) ?? "n/a"}s
                      </div>
                      <div className="mt-2 rounded-md border border-border bg-muted/20 p-2 text-[11px] text-muted-foreground">
                        {execution.pipeline_context_json ? "Pipeline context snapshot persisted for this run." : "No pipeline context snapshot persisted."}
                      </div>
                      <div className="mt-2 flex flex-wrap gap-2 text-[10px] uppercase">
                        <Badge variant="outline">Est In {execution.estimated_input_tokens ?? 0}</Badge>
                        <Badge variant="outline">Act In {execution.actual_input_tokens ?? 0}</Badge>
                        <Badge variant="outline">Est Out {execution.estimated_output_tokens ?? 0}</Badge>
                        <Badge variant="outline">Act Out {execution.actual_output_tokens ?? 0}</Badge>
                        <Badge variant="outline">Trunc {execution.completion_truncated ? "yes" : "no"}</Badge>
                      </div>
                    </>
                  ) : (
                    <div className="mt-2 grid gap-2 sm:grid-cols-3">
                      <div className="rounded-md bg-muted/30 p-2">
                        <div className="text-[10px] uppercase tracking-wider text-muted-foreground">Summary</div>
                        <div className="mt-1 text-sm text-foreground">Persisted sync run for the selected database.</div>
                      </div>
                      <div className="rounded-md bg-muted/30 p-2">
                        <div className="text-[10px] uppercase tracking-wider text-muted-foreground">Started</div>
                        <div className="mt-1 text-sm text-foreground">{execution.start_time ?? "n/a"}</div>
                      </div>
                      <div className="rounded-md bg-muted/30 p-2">
                        <div className="text-[10px] uppercase tracking-wider text-muted-foreground">Duration</div>
                        <div className="mt-1 text-sm text-foreground">{execution.duration_seconds?.toFixed(2) ?? "n/a"}s</div>
                      </div>
                    </div>
                  )}
                </div>
              ))
            ) : (
              <EmptyState icon={Activity} title="No pipeline executions yet" description="Trigger a run to persist execution history." />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Stage executions</CardTitle>
            <CardDescription>Per-stage persisted audit trail for the latest run.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {stageExecutions?.stage_executions?.length ? (
              stageExecutions.stage_executions.map((stage) => (
                <div key={stage.id} className="rounded-md border border-border bg-card p-3">
                  <div className="flex items-center justify-between gap-2">
                    <div className="text-sm font-medium text-foreground">{stage.stage_name}</div>
                    <Badge variant="outline" className="text-[10px] uppercase">
                      {normalizeJobStatus(stage.status)}
                    </Badge>
                  </div>
                  {viewMode === "technical" ? (
                    <>
                      <div className="mt-1 flex flex-wrap gap-2 text-[10px] uppercase">
                        <Badge variant="outline">Context {stage.used_context ? "yes" : "no"}</Badge>
                        <Badge variant="outline">Source {stage.context_source ?? "persisted"}</Badge>
                        <Badge variant="outline">Fallback {stage.fallback_reason ?? "none"}</Badge>
                      </div>
                      <div className="mt-1 text-xs text-muted-foreground">
                        Execution order: {stage.execution_order ?? "n/a"} · Trace: {stage.trace_id ?? "n/a"}
                      </div>
                      <TraceLink traceId={stage.trace_id} label="Open trace" className="mt-2 text-[11px]" />
                      <div className="mt-1 text-xs text-muted-foreground">Error: {stage.error_message ?? "none"}</div>
                      <div className="mt-2 flex flex-wrap gap-2 text-[10px] uppercase">
                        <Badge variant="outline">Est In {stage.estimated_input_tokens ?? 0}</Badge>
                        <Badge variant="outline">Act In {stage.actual_input_tokens ?? 0}</Badge>
                        <Badge variant="outline">Est Out {stage.estimated_output_tokens ?? 0}</Badge>
                        <Badge variant="outline">Act Out {stage.actual_output_tokens ?? 0}</Badge>
                        <Badge variant="outline">Trunc {stage.completion_truncated ? "yes" : "no"}</Badge>
                      </div>
                    </>
                  ) : (
                    <div className="mt-1 text-xs text-muted-foreground">
                      Stage completed in {stage.duration_seconds?.toFixed(2) ?? "n/a"}s
                    </div>
                  )}
                </div>
              ))
            ) : (
              <EmptyState icon={Activity} title="No stage executions yet" description="Stage execution records appear after a run completes." />
            )}
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-4 xl:grid-cols-[1fr_360px]">
        <Card>
          <CardHeader className="flex flex-row items-end justify-between gap-3 space-y-0">
            <div>
              <CardTitle className="text-base">Job history</CardTitle>
              <CardDescription>Sync Run history with database name, duration, and status.</CardDescription>
            </div>
            <Input
              value={selectedJobId ?? ""}
              onChange={(e) => {
                const next = Number(e.target.value);
                setSelectedJobId(Number.isFinite(next) && next > 0 ? next : null);
              }}
              placeholder="Job ID"
              className="h-9 w-24"
            />
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="grid gap-3 xl:grid-cols-[1fr_1fr]">
              <section id="job-filters" className="rounded-xl border border-border bg-muted/20 p-3">
                <div className="mb-2 flex items-center justify-between gap-2">
                  <div>
                    <div className="text-xs uppercase tracking-wider text-muted-foreground">Status filters</div>
                    <div className="text-sm font-medium text-foreground">Use the quick chips to narrow job state.</div>
                  </div>
                  <Badge variant="outline" className="text-[10px] uppercase">
                    {dbJobs.length} shown
                  </Badge>
                </div>
                <div className="flex flex-wrap gap-2">
                  {statusFilters.map((s) => (
                    <Button key={s} variant={statusFilter === s ? "default" : "outline"} size="sm" onClick={() => setStatusFilter(s)}>
                      {s}
                    </Button>
                  ))}
                </div>
              </section>

              <section className="rounded-xl border border-border bg-muted/20 p-3">
                <div className="mb-2 flex items-center justify-between gap-2">
                  <div>
                    <div className="text-xs uppercase tracking-wider text-muted-foreground">Job types</div>
                    <div className="text-sm font-medium text-foreground">Separate sync, AI, and readiness jobs.</div>
                  </div>
                  <Badge variant="outline" className="text-[10px] uppercase">
                    {counts.success ?? 0} success
                  </Badge>
                </div>
                <div className="flex flex-wrap gap-2">
                  {typeFilters.map((s) => (
                    <Button key={s} variant={jobTypeFilter === s ? "default" : "outline"} size="sm" onClick={() => setJobTypeFilter(s)}>
                      {s}
                    </Button>
                  ))}
                </div>
              </section>
            </div>

            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow className="bg-muted/40 hover:bg-muted/40">
                    <TableHead className="w-8"></TableHead>
                    <TableHead>Job</TableHead>
                    <TableHead>Source</TableHead>
                    <TableHead className="min-w-[140px]">Progress</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Started</TableHead>
                    <TableHead>Progress%</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {dbJobs.length ? (
                    dbJobs.map((j) => {
                      const isOpen = expanded === j.id;
                      return (
                        <Fragment key={j.id}>
                          <TableRow className="cursor-pointer hover:bg-muted/30" onClick={() => setExpanded(isOpen ? null : j.id)}>
                            <TableCell className="text-muted-foreground">{isOpen ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}</TableCell>
                            <TableCell>
                              <div className="flex min-w-0 items-center gap-2">
                                <Badge variant="outline" className="text-[10px] uppercase tracking-wider">
                                  {j.job_type}
                                </Badge>
                                <span className="truncate text-sm font-medium text-foreground">Sync Run #{j.id}</span>
                              </div>
                              <div className="font-mono text-[11px] text-muted-foreground">{j.id}</div>
                            </TableCell>
                            <TableCell className="text-sm text-muted-foreground">{j.database_id}</TableCell>
                            <TableCell>
                              <CoverageBar value={j.progress_percentage} tone={j.status === "FAILED" ? "danger" : "primary"} />
                            </TableCell>
                            <TableCell>
                              <StatusBadge status={j.status} />
                            </TableCell>
                            <TableCell className="text-xs text-muted-foreground">{j.started_at ?? "n/a"}</TableCell>
                            <TableCell className="text-xs tabular-nums text-muted-foreground">{Math.round(j.progress_percentage ?? 0)}%</TableCell>
                          </TableRow>
                          {isOpen ? (
                            <TableRow className="bg-muted/20 hover:bg-muted/20">
                              <TableCell />
                              <TableCell colSpan={6}>
                                <JobDetail job={j} technical={viewMode === "technical"} />
                              </TableCell>
                            </TableRow>
                          ) : null}
                        </Fragment>
                      );
                    })
                  ) : (
                    <TableRow>
                      <TableCell colSpan={7} className="py-10">
                        <EmptyState icon={Activity} title="No jobs yet" description="Execution history will appear here after sync and AI runs complete." />
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </div>

            <div className="flex flex-wrap gap-2">
              <Button variant="outline" size="sm" onClick={() => runMutation.mutate()}>
                Run diagnostics
              </Button>
              <Button variant="outline" size="sm" onClick={() => selectedJobId && setExpanded(selectedJobId)} disabled={!selectedJobId}>
                Inspect Job
              </Button>
              <Button variant="outline" size="sm" onClick={() => queryClient.invalidateQueries({ queryKey: queryKeys.jobs(statusFilter) })}>
                <RefreshCw className="mr-1.5 h-3.5 w-3.5" /> Auto refresh now
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Selected job</CardTitle>
            <CardDescription>Business view by default; technical trace details are optional.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {selectedJob ? (
              <>
                <JobDetail job={selectedJob} technical={viewMode === "technical"} />
                <div className="rounded-md border border-border bg-muted/20 p-3">
                  <div className="flex items-center justify-between gap-2">
                    <div>
                      <div className="text-[11px] uppercase tracking-wider text-muted-foreground">Execution lineage</div>
                      <div className="text-sm font-medium text-foreground">Job to trace graph</div>
                    </div>
                    <Badge variant="outline" className="text-[10px] uppercase">
                      {selectedJob.status}
                    </Badge>
                  </div>
                  <div className="mt-3 space-y-2">
                    <LineageNode
                      step={1}
                      label="Job"
                      value={`#${selectedJob.id}`}
                      href={selectedExecutionTrace?.trace_id ?? selectedJob.trace_id ? `/observability?trace_id=${encodeURIComponent(selectedExecutionTrace?.trace_id ?? selectedJob.trace_id ?? "")}` : undefined}
                    />
                    <LineageConnector />
                    <LineageNode
                      step={2}
                      label="Pipeline execution"
                      value={String(selectedExecutionTrace?.pipeline_execution_id ?? "n/a")}
                      href={selectedExecutionTrace?.trace_id ? `/observability?trace_id=${encodeURIComponent(selectedExecutionTrace.trace_id)}` : undefined}
                    />
                    <LineageConnector />
                    <LineageNode
                      step={3}
                      label="Stage execution"
                      value={String(selectedExecutionTrace?.stage_execution_id ?? "n/a")}
                      href={selectedExecutionTrace?.trace_id ? `/observability?trace_id=${encodeURIComponent(selectedExecutionTrace.trace_id)}` : undefined}
                    />
                    <LineageConnector />
                    <LineageNode
                      step={4}
                      label="Trace"
                      value={selectedExecutionTrace?.trace_id ?? selectedJob.trace_id ?? "n/a"}
                      href={selectedExecutionTrace?.trace_id ?? selectedJob.trace_id ? `/observability?trace_id=${encodeURIComponent(selectedExecutionTrace?.trace_id ?? selectedJob.trace_id ?? "")}` : undefined}
                    />
                    <LineageConnector />
                    <LineageNode
                      step={5}
                      label="Prompt version"
                      value={selectedExecutionTrace?.prompt_version ?? "n/a"}
                      href={selectedExecutionTrace?.trace_id ? `/prompt-studio?trace_id=${encodeURIComponent(selectedExecutionTrace.trace_id)}` : undefined}
                    />
                  </div>
                </div>
              </>
            ) : (
              <EmptyState icon={Activity} title="No job selected" description="Choose a job to inspect trace and logs." />
            )}
          </CardContent>
        </Card>
      </section>
    </div>
  );
}

function JobDetail({ job, technical }: { job: PipelineJob; technical: boolean }) {
  return (
    <div className="grid grid-cols-1 gap-3 lg:grid-cols-[1fr_1fr]">
      <div className="grid grid-cols-2 gap-2">
        <Meta icon={Hash} label="Job ID" value={String(job.id)} mono />
        <Meta icon={Clock} label="Started" value={job.started_at ?? "n/a"} mono />
        <Meta icon={Cpu} label="Type" value={job.job_type} />
        <Meta icon={Activity} label="Status" value={job.status ?? "unknown"} />
      </div>
      <div className="space-y-2">
        <div className="text-[11px] uppercase tracking-wider text-muted-foreground">{technical ? "Logs" : "Summary"}</div>
        <ScrollArea className="max-h-44 rounded-md border border-border bg-[var(--muted)]/40">
          <div className="whitespace-pre-wrap p-3 font-mono text-[11px] leading-relaxed text-foreground">
            {technical
              ? `[job ${job.id}] ${job.job_type} ${job.status}
progress=${job.progress_percentage}%
failure=${job.failure_reason ?? "n/a"}`
              : `Sync run ${job.id} for database ${job.database_id}
status=${job.status}
progress=${Math.round(job.progress_percentage ?? 0)}%`}
          </div>
        </ScrollArea>
        {technical ? <TraceLink traceId={job.trace_id} label="Open trace" className="text-xs" /> : null}
      </div>
    </div>
  );
}

function Meta({ icon: Icon, label, value, mono }: { icon: typeof Hash; label: string; value: string; mono?: boolean }) {
  return (
    <div className="rounded-md border border-border bg-card p-2.5">
      <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-muted-foreground">
        <Icon className="h-3 w-3" /> {label}
      </div>
      <div className={`mt-1 truncate text-sm text-foreground ${mono ? "font-mono text-[12px]" : ""}`}>{value}</div>
    </div>
  );
}

function LineageNode({ step, label, value, href }: { step: number; label: string; value: string; href?: string }) {
  const content = (
    <div className="flex items-center gap-3 rounded-xl border border-border bg-card px-3 py-3 shadow-sm transition-all hover:border-primary/40 hover:bg-primary/5">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-border bg-muted/40 text-[11px] font-semibold text-foreground">
        {step}
      </div>
      <div className="min-w-0 flex-1">
        <div className="text-[11px] uppercase tracking-wider text-muted-foreground">{label}</div>
        <div className="truncate text-sm font-medium text-foreground">{value}</div>
      </div>
    </div>
  );

  if (!href) return content;
  return (
    <a href={href} className="block">
      {content}
    </a>
  );
}

function LineageConnector() {
  return (
    <div className="flex justify-center">
      <div className="h-4 w-px bg-gradient-to-b from-primary/50 to-border" />
    </div>
  );
}
