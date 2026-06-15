import { Fragment, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCw, Filter, Clock, Hash, Cpu, Activity, ChevronRight, ChevronDown } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { StatusBadge, type StatusKind } from "@/components/status-badge";
import { CoverageBar } from "@/components/coverage-bar";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ScrollArea } from "@/components/ui/scroll-area";
import { EmptyState } from "@/components/empty-state";
import { connectionsApi } from "@/api/connections";
import { jobsApi } from "@/api/jobs";
import { metadataApi } from "@/api/metadata";
import type { PipelineJob } from "@/types/backend";
import { useDatabaseContext } from "@/context/database-context";

export function JobsPage() {
  const queryClient = useQueryClient();
  const { data: connections = [] } = useQuery({ queryKey: ["connections"], queryFn: connectionsApi.list });
  const { selectedDatabaseId: selectedDb, setSelectedDatabaseId } = useDatabaseContext();
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
    if (statusFilter !== "ALL") rows = rows.filter((j) => j.status === statusFilter);
    if (jobTypeFilter !== "ALL") rows = rows.filter((j) => j.job_type === jobTypeFilter);
    return rows;
  }, [jobTypeFilter, jobs, selectedDb, statusFilter]);

  const dbJobs = filteredJobs;
  const counts = useMemo(
    () => dbJobs.reduce<Record<string, number>>((acc, job) => ({ ...acc, [job.status]: (acc[job.status] ?? 0) + 1 }), {}),
    [dbJobs],
  );

  const runMutation = useMutation({
    mutationFn: () => metadataApi.diagnose(Number(selectedDb ?? 0)),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["jobs"] }),
  });

  const selectedJob = dbJobs.find((j) => j.id === selectedJobId);

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Platform"
        title="Jobs & operations"
        description="All sync jobs, AI jobs, and pipeline executions with trace IDs, model usage, and error logs."
        actions={
          <>
            <Button variant="outline" size="sm" className="gap-1.5">
              <Filter className="h-3.5 w-3.5" /> Filter
            </Button>
            <Button variant="outline" size="sm" className="gap-1.5" onClick={() => queryClient.invalidateQueries({ queryKey: ["jobs"] })}>
              <RefreshCw className="h-3.5 w-3.5" /> Refresh
            </Button>
          </>
        }
      />
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Active pipeline</CardTitle>
          <CardDescription>Current execution across sync, governance, semantics, relationships, KPI, and embeddings.</CardDescription>
        </CardHeader>
        <CardContent>
          {dbJobs.length ? (
            <ol className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-7">
              {["SYNC", "GOVERNANCE", "SEMANTIC_ENRICHMENT", "RELATIONSHIP_GRAPH", "KPI", "EMBEDDINGS", "PROMPT_GENERATION"].map((stage) => (
                <li key={stage} className="rounded-md border border-border bg-card p-3">
                  <div className="mb-2 flex items-center justify-between gap-2">
                    <span className="truncate text-xs font-medium text-foreground">{stage.replaceAll("_", " ")}</span>
                    <StatusBadge status={(counts["RUNNING"] ? "running" : "queued") as StatusKind} />
                  </div>
                  <CoverageBar value={stage === "SYNC" ? 100 : 0} />
                </li>
              ))}
            </ol>
          ) : (
            <EmptyState icon={Activity} title="No active pipeline" description="Run a sync to populate pipeline stages and execution history." />
          )}
        </CardContent>
      </Card>
      <Card>
        <CardHeader className="flex flex-row items-end justify-between gap-3 space-y-0">
          <div>
            <CardTitle className="text-base">Job history</CardTitle>
            <CardDescription>Click a job to inspect trace, prompt, model, and logs.</CardDescription>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <Input value={String(selectedDb ?? "")} onChange={(e) => setSelectedDatabaseId(Number(e.target.value) || null)} placeholder="Database id" className="h-9 w-32" />
            <Input value={String(selectedJobId)} onChange={(e) => setSelectedJobId(Number(e.target.value) || 1)} placeholder="Job ID" className="h-9 w-24" />
          </div>
        </CardHeader>
        <CardContent>
          <div className="mb-3 flex flex-wrap gap-2">
            {["ALL", "QUEUED", "RUNNING", "FAILED", "COMPLETED", "CANCELLED"].map((s) => (
              <Button key={s} variant={statusFilter === s ? "default" : "outline"} size="sm" onClick={() => setStatusFilter(s)}>
                {s}
              </Button>
            ))}
          </div>
          <div className="mb-3 flex flex-wrap gap-2">
            {["ALL", "SYNC", "SEMANTIC_ENRICHMENT", "EMBEDDINGS", "RELATIONSHIP_GRAPH", "PROMPT_GENERATION", "READINESS", "ARTIFACT_PACKAGING", "AI_CONTEXT"].map((s) => (
              <Button key={s} variant={jobTypeFilter === s ? "default" : "outline"} size="sm" onClick={() => setJobTypeFilter(s)}>
                {s}
              </Button>
            ))}
          </div>
          <Tabs defaultValue="all">
            <TabsList>
              <TabsTrigger value="all">All</TabsTrigger>
              <TabsTrigger value="sync">Sync</TabsTrigger>
              <TabsTrigger value="ai">AI</TabsTrigger>
              <TabsTrigger value="pipeline">Pipelines</TabsTrigger>
            </TabsList>
            <TabsContent value="all" className="pt-4">
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
                                  <Badge variant="outline" className="text-[10px] uppercase tracking-wider">{j.job_type}</Badge>
                                  <span className="truncate text-sm font-medium text-foreground">Job #{j.id}</span>
                                </div>
                                <div className="font-mono text-[11px] text-muted-foreground">{j.id}</div>
                              </TableCell>
                              <TableCell className="text-sm text-muted-foreground">{j.database_id}</TableCell>
                              <TableCell><CoverageBar value={j.progress_percentage} tone={j.status === "FAILED" ? "danger" : "primary"} /></TableCell>
                              <TableCell><StatusBadge status={j.status.toLowerCase() as StatusKind} /></TableCell>
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
            </TabsContent>
          </Tabs>
          <div className="mt-4 flex flex-wrap gap-2">
            <Button variant="outline" size="sm" onClick={() => runMutation.mutate()}>
              Run diagnostics
            </Button>
            <Button variant="outline" size="sm" onClick={() => setExpanded(selectedJobId)}>
              Inspect Job
            </Button>
          </div>
        </CardContent>
      </Card>
      {selectedJob ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Selected job</CardTitle>
            <CardDescription>Streamlit-style drilldown for trace, prompt, model, and logs.</CardDescription>
          </CardHeader>
          <CardContent>
            <JobDetail job={selectedJob} />
          </CardContent>
        </Card>
      ) : null}
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
        <Meta icon={Activity} label="Status" value={job.status} />
      </div>
      <div className="space-y-2">
        <div className="text-[11px] uppercase tracking-wider text-muted-foreground">Logs</div>
        <ScrollArea className="max-h-44 rounded-md border border-border bg-[var(--muted)]/40">
          <pre className="whitespace-pre-wrap p-3 font-mono text-[11px] leading-relaxed text-foreground">
            {`[job ${job.id}] ${job.job_type} ${job.status}
progress=${job.progress_percentage}%
failure=${job.failure_reason ?? "n/a"}`}
          </pre>
        </ScrollArea>
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
