import { Fragment, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCw, Filter, Clock, Hash, Cpu, Activity, ChevronRight, ChevronDown, ArrowRight } from "lucide-react";
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
import { TraceLink } from "@/components/common/TraceLink";

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
  const [selectedJobId, setSelectedJobId] = useState<number>(1);

  const { data: jobs = [] } = useQuery({
    queryKey: ["jobs", statusFilter],
    queryFn: () => jobsApi.list(300),
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
    mutationFn: () => metadataApi.diagnose(Number(selectedDb ?? 0)),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["jobs"] }),
  });

  const selectedJob = dbJobs.find((j) => j.id === selectedJobId);
  const { data: stageProgress } = useStageProgress(selectedDb);
  const { data: businessInsights } = useBusinessInsights(selectedDb);
  const { data: pipelineExecutions } = usePipelineExecutions(selectedDb, 10);
  const { data: stageExecutions } = useStageExecutions(selectedDb, pipelineExecutions?.executions?.[0]?.id ?? null, 20);
  const insights = businessInsights?.insights ?? [];

  const stageCards =
    stageProgress?.stages?.length
      ? stageProgress.stages
      : ["SYNC", "GOVERNANCE", "SEMANTIC_ENRICHMENT", "RELATIONSHIP_GRAPH", "KPI", "EMBEDDINGS", "PROMPT_GENERATION"].map((stage) => ({
          stage,
          status: "pending",
          progress_percentage: 0,
          retries: 0,
        }));

  const statusFilters = ["ALL", "QUEUED", "RUNNING", "FAILED", "COMPLETED", "CANCELLED"];
  const typeFilters = ["ALL", "SYNC", "SEMANTIC_ENRICHMENT", "EMBEDDINGS", "RELATIONSHIP_GRAPH", "PROMPT_GENERATION", "READINESS", "ARTIFACT_PACKAGING", "AI_CONTEXT"];

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Platform"
        title="Jobs & operations"
        description="All sync jobs, AI jobs, and pipeline executions with trace IDs, model usage, and error logs."
        actions={
          <>
            <Button
              variant="outline"
              size="sm"
              className="gap-1.5"
              onClick={() => document.getElementById("job-filters")?.scrollIntoView({ behavior: "smooth", block: "start" })}
            >
              <Filter className="h-3.5 w-3.5" /> Filters
            </Button>
            <Button variant="outline" size="sm" className="gap-1.5" onClick={() => queryClient.invalidateQueries({ queryKey: ["jobs"] })}>
              <RefreshCw className="h-3.5 w-3.5" /> Refresh
            </Button>
          </>
        }
      />

      <section className="grid gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader>
            <CardTitle className="text-base">Active pipeline</CardTitle>
            <CardDescription>Current execution across sync, governance, semantics, relationships, KPI, embeddings, and prompt generation.</CardDescription>
          </CardHeader>
          <CardContent>
            {dbJobs.length ? (
              <ol className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-7">
                {stageCards.map((item: any) => (
                  <li key={item.stage} className="rounded-md border border-border bg-card p-3">
                    <div className="mb-2 flex items-center justify-between gap-2">
                      <span className="truncate text-xs font-medium text-foreground">{item.stage.replaceAll("_", " ")}</span>
                      <Badge variant="outline" className="text-[10px] uppercase">
                        {item.status}
                      </Badge>
                    </div>
                    <CoverageBar value={item.progress_percentage} />
                  </li>
                ))}
              </ol>
            ) : (
              <EmptyState icon={Activity} title="No active pipeline" description="Run a sync to populate pipeline stages and execution history." />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Business insights</CardTitle>
            <CardDescription>AI-generated cross-package insights from persisted intelligence packages.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {insights.length ? (
              insights.slice(0, 3).map((insight) => (
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
                  <div className="mt-2 flex flex-wrap gap-2">
                    {(insight.evidence ?? []).slice(0, 5).map((item, index) => (
                      <Badge key={`${insight.id ?? index}`} variant="outline" className="text-[10px] uppercase">
                        {String((item as Record<string, unknown>).evidence_type ?? (item as Record<string, unknown>).type ?? "evidence")}
                      </Badge>
                    ))}
                  </div>
                </div>
              ))
            ) : (
              <EmptyState icon={Activity} title="No business insights" description="Business insights will appear after sync generates persisted intelligence packages." />
            )}
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
            {pipelineExecutions?.executions?.length ? (
              pipelineExecutions.executions.map((execution) => (
                <div key={execution.id} className="rounded-md border border-border bg-card p-3">
                  <div className="flex items-center justify-between gap-2">
                    <div className="text-sm font-medium text-foreground">Execution #{execution.id}</div>
                    <Badge variant="outline" className="text-[10px] uppercase">
                      {normalizeJobStatus(execution.status)}
                    </Badge>
                  </div>
                  <div className="mt-1 text-xs text-muted-foreground">Trace: {execution.trace_id ?? "n/a"} · Model: {execution.model_name ?? "n/a"}</div>
                  <TraceLink traceId={execution.trace_id} label="Open trace" className="mt-2 text-[11px]" />
                  <div className="mt-1 text-xs text-muted-foreground">
                    Started: {execution.start_time ?? "n/a"} · Duration: {execution.duration_seconds?.toFixed(2) ?? "n/a"}s
                  </div>
                  <div className="mt-2 flex flex-wrap gap-2 text-[10px] uppercase">
                    <Badge variant="outline">In {execution.estimated_input_tokens ?? 0}</Badge>
                    <Badge variant="outline">Out {execution.actual_output_tokens ?? 0}</Badge>
                    <Badge variant="outline">Trunc {execution.completion_truncated ? "yes" : "no"}</Badge>
                  </div>
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
                  <div className="mt-1 text-xs text-muted-foreground">
                    Execution order: {stage.execution_order ?? "n/a"} · Trace: {stage.trace_id ?? "n/a"}
                  </div>
                  <TraceLink traceId={stage.trace_id} label="Open trace" className="mt-2 text-[11px]" />
                  <div className="mt-1 text-xs text-muted-foreground">Error: {stage.error_message ?? "none"}</div>
                  <div className="mt-2 flex flex-wrap gap-2 text-[10px] uppercase">
                    <Badge variant="outline">Est {stage.estimated_input_tokens ?? 0}</Badge>
                    <Badge variant="outline">Act {stage.actual_input_tokens ?? 0}</Badge>
                    <Badge variant="outline">Trunc {stage.completion_truncated ? "yes" : "no"}</Badge>
                  </div>
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
              <CardDescription>Click a job to inspect trace, prompt, model, and logs.</CardDescription>
            </div>
              <Input value={String(selectedJobId)} onChange={(e) => setSelectedJobId(Number(e.target.value) || 1)} placeholder="Job ID" className="h-9 w-24" />
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
                    <TableHead>Duration</TableHead>
                    <TableHead>Retries</TableHead>
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
                                <span className="truncate text-sm font-medium text-foreground">Job #{j.id}</span>
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
                            <TableCell className="text-xs text-muted-foreground">{j.started_at ? "running" : "n/a"}</TableCell>
                            <TableCell className="text-xs tabular-nums text-muted-foreground">0</TableCell>
                          </TableRow>
                          {isOpen ? (
                            <TableRow className="bg-muted/20 hover:bg-muted/20">
                              <TableCell />
                              <TableCell colSpan={6}>
                                <JobDetail job={j} />
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
              <Button variant="outline" size="sm" onClick={() => setExpanded(selectedJobId)}>
                Inspect Job
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Selected job</CardTitle>
            <CardDescription>Streamlit-style drilldown for trace, prompt, model, and logs.</CardDescription>
          </CardHeader>
          <CardContent>{selectedJob ? <JobDetail job={selectedJob} /> : <EmptyState icon={Activity} title="No job selected" description="Choose a job to inspect trace and logs." />}</CardContent>
        </Card>
      </section>
    </div>
  );
}

function JobDetail({ job }: { job: PipelineJob }) {
  return (
    <div className="grid grid-cols-1 gap-3 lg:grid-cols-[1fr_1fr]">
      <div className="grid grid-cols-2 gap-2">
        <Meta icon={Hash} label="Job ID" value={String(job.id)} mono />
        <Meta icon={Clock} label="Started" value={job.started_at ?? "n/a"} mono />
        <Meta icon={Cpu} label="Type" value={job.job_type} />
        <Meta icon={Activity} label="Status" value={job.status ?? "unknown"} />
      </div>
      <div className="space-y-2">
        <div className="text-[11px] uppercase tracking-wider text-muted-foreground">Logs</div>
        <ScrollArea className="max-h-44 rounded-md border border-border bg-[var(--muted)]/40">
          <div className="whitespace-pre-wrap p-3 font-mono text-[11px] leading-relaxed text-foreground">{`[job ${job.id}] ${job.job_type} ${job.status}
progress=${job.progress_percentage}%
failure=${job.failure_reason ?? "n/a"}`}</div>
        </ScrollArea>
        <TraceLink traceId={job.trace_id} label="Open trace" className="text-xs" />
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
