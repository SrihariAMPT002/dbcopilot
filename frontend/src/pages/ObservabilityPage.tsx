import { useEffect, useMemo, useState, type ComponentType } from "react";
import { Clock3, Copy, Download, Search, Server, Sparkles, TextQuote, Workflow, Zap, Link as LinkIcon, RefreshCw } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { EmptyState } from "@/components/empty-state";
import { useDatabaseContext } from "@/context/database-context";
import { useLifecycleEvents, useObservabilityTraceDetail, useObservabilityTraces } from "@/hooks/useObservability";
import { usePipelineExecutions } from "@/hooks/usePipelineExecutions";
import { usePromptPackages } from "@/hooks/usePromptStudio";
import { useConnections } from "@/hooks/useConnections";
import { cn } from "@/lib/utils";

export function ObservabilityPage() {
  const { selectedDatabase } = useDatabaseContext();
  const { data: connections = [] } = useConnections();
  const [module, setModule] = useState("all");
  const [model, setModel] = useState("all");
  const [query, setQuery] = useState("");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(() => {
    if (typeof window === "undefined") return null;
    return new URLSearchParams(window.location.search).get("trace_id");
  });
  const dbId = selectedDatabase?.database_id ?? null;
  const selectedConnection = connections.find((db) => db.id === dbId);
  const { data } = useObservabilityTraces(dbId, {
    module: module === "all" ? undefined : module,
    model_name: model === "all" ? undefined : model,
    trace_id: query.trim() || undefined,
    from_date: fromDate || undefined,
    to_date: toDate || undefined,
  });
  const { data: traceDetail } = useObservabilityTraceDetail(dbId, selectedTraceId);
  const { data: pipelineExecutions } = usePipelineExecutions(dbId, 10);
  const { data: promptPackages } = usePromptPackages(dbId);
  const { data: lifecycleEvents } = useLifecycleEvents(dbId);

  const traces = data?.traces ?? [];
  const models = useMemo(() => Array.from(new Set(traces.map((t) => t.model_name).filter(Boolean) as string[])), [traces]);
  const modules = useMemo(() => Array.from(new Set(traces.map((t) => t.module).filter(Boolean) as string[])), [traces]);
  const totalTokens = traces.reduce((sum, item) => sum + item.prompt_tokens + item.completion_tokens + item.reasoning_tokens, 0);
  const totalCost = traces.reduce((sum, item) => sum + item.estimated_cost_usd, 0);

  const promptVersions = traceDetail?.prompt_versions ?? [];
  const promptObservability = traceDetail?.prompt_observability ?? [];
  const lifecycle = lifecycleEvents?.events ?? [];

  useEffect(() => {
    const syncTraceFromUrl = () => {
      if (typeof window === "undefined") return;
      setSelectedTraceId(new URLSearchParams(window.location.search).get("trace_id"));
    };

    syncTraceFromUrl();
    window.addEventListener("popstate", syncTraceFromUrl);
    return () => window.removeEventListener("popstate", syncTraceFromUrl);
  }, []);

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Platform"
        title="AI observability"
        description="Trace visibility for prompts, pipeline executions, token usage, latency, cost estimates, and lifecycle events."
        actions={
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="gap-1.5 text-[11px]">
              <Server className="h-3.5 w-3.5" />
              DB {dbId}
            </Badge>
            <Button variant="outline" size="sm" onClick={() => window.location.reload()}>
              <RefreshCw className="mr-2 h-4 w-4" /> Refresh
            </Button>
            {selectedTraceId ? (
              <Button variant="outline" size="sm" onClick={() => navigator.clipboard.writeText(selectedTraceId)}>
                <Copy className="mr-2 h-4 w-4" /> Copy trace
              </Button>
            ) : null}
          </div>
        }
      />

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Metric label="Traces" value={String(traces.length)} icon={Workflow} />
        <Metric label="Tokens" value={String(totalTokens)} icon={Zap} />
        <Metric label="Estimated cost" value={`$${totalCost.toFixed(4)}`} icon={Clock3} />
        <Metric label="Prompt packages" value={String(promptPackages?.prompt_packages?.length ?? 0)} icon={Sparkles} />
      </section>

      <section className="grid gap-4 lg:grid-cols-[1.3fr_0.7fr]">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Trace filters</CardTitle>
            <CardDescription>Filter by database, module, model, date, and trace id.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3 lg:grid-cols-5">
            <Select value={module} onValueChange={setModule}>
              <SelectTrigger>
                <SelectValue placeholder="Module" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All modules</SelectItem>
                {modules.map((item) => (
                  <SelectItem key={item} value={item}>
                    {item}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={model} onValueChange={setModel}>
              <SelectTrigger>
                <SelectValue placeholder="Model" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All models</SelectItem>
                {models.map((item) => (
                  <SelectItem key={item} value={item}>
                    {item}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search trace_id" />
            <Input type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} />
            <Input type="date" value={toDate} onChange={(e) => setToDate(e.target.value)} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Trace summary</CardTitle>
            <CardDescription>{selectedDatabase ? selectedDatabase.name : "Select a database"}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm text-muted-foreground">
            <TraceSummary label="Last sync" value={selectedDatabase?.last_sync_at ? new Date(selectedDatabase.last_sync_at).toLocaleString() : "n/a"} />
            <TraceSummary label="Lifecycle" value={selectedDatabase?.lifecycle_status ?? "ACTIVE"} />
            <TraceSummary label="Total modules" value={String(modules.length)} />
            <TraceSummary label="Recent lifecycle events" value={String(lifecycle.length)} />
            <TraceSummary label="Linked job" value={String(traceDetail?.linked_job?.job_id ?? "n/a")} />
            <TraceSummary label="Pipeline execution" value={String(traceDetail?.linked_pipeline_execution?.pipeline_execution_id ?? "n/a")} />
            <TraceSummary label="Stage executions" value={String(traceDetail?.linked_stage_executions?.length ?? 0)} />
            <TraceSummary label="Prompt version" value={String(traceDetail?.linked_prompt_versions?.[0]?.version ?? traceDetail?.prompt_version ?? "n/a")} />
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-4 xl:grid-cols-[1fr_360px]">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Trace table</CardTitle>
            <CardDescription>Prompt, pipeline, and stage traces with execution details.</CardDescription>
          </CardHeader>
          <CardContent>
            {traces.length ? (
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow className="bg-muted/40 hover:bg-muted/40">
                      <TableHead>Trace</TableHead>
                      <TableHead>Prompt / Module</TableHead>
                      <TableHead>Model</TableHead>
                      <TableHead>Tokens</TableHead>
                      <TableHead>Latency</TableHead>
                      <TableHead>Status</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {traces.map((trace) => (
                      <TableRow
                        key={`${trace.source_type}-${trace.trace_id ?? trace.created_at}`}
                        className="cursor-pointer hover:bg-muted/30"
                        onClick={() => trace.trace_id && setSelectedTraceId(trace.trace_id)}
                      >
                        <TableCell>
                          <div className="font-mono text-[11px] text-foreground">{trace.trace_id ?? "n/a"}</div>
                          <div className="text-[11px] text-muted-foreground">{trace.source_type}</div>
                        </TableCell>
                        <TableCell>
                          <div className="text-sm text-foreground">{trace.prompt_id ?? "n/a"}</div>
                          <div className="text-[11px] text-muted-foreground">
                            {trace.module ?? "n/a"} · v{trace.prompt_version ?? "n/a"}
                          </div>
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">{trace.model_name ?? "n/a"}</TableCell>
                        <TableCell className="text-xs text-muted-foreground">
                          P {trace.prompt_tokens} / C {trace.completion_tokens} / R {trace.reasoning_tokens}
                          <div className="mt-1 flex flex-wrap gap-1">
                            <Badge variant="outline" className="text-[10px] uppercase">Est in {trace.estimated_input_tokens ?? 0}</Badge>
                            <Badge variant="outline" className="text-[10px] uppercase">Act in {trace.actual_input_tokens ?? 0}</Badge>
                            <Badge variant="outline" className="text-[10px] uppercase">Est out {trace.estimated_output_tokens ?? 0}</Badge>
                            <Badge variant="outline" className="text-[10px] uppercase">Act out {trace.actual_output_tokens ?? 0}</Badge>
                          </div>
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground">{Math.round(trace.latency_ms)} ms</TableCell>
                        <TableCell>
                          <Badge variant="outline" className="text-[10px] uppercase">
                            {trace.execution_status ?? trace.finish_reason ?? "unknown"}
                          </Badge>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            ) : (
              <EmptyState icon={Search} title="No traces found" description="Adjust filters or run a pipeline to collect observability traces." />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Token analytics</CardTitle>
            <CardDescription>Prompt, completion, reasoning, latency, and estimated cost.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <Metric label="Prompt tokens" value={String(traceDetail?.prompt_tokens ?? 0)} icon={TextQuote} />
            <Metric label="Completion tokens" value={String(traceDetail?.completion_tokens ?? 0)} icon={TextQuote} />
            <Metric label="Reasoning tokens" value={String(traceDetail?.reasoning_tokens ?? 0)} icon={TextQuote} />
            <Metric label="Estimated input" value={String(traceDetail?.estimated_input_tokens ?? 0)} icon={TextQuote} />
            <Metric label="Actual input" value={String(traceDetail?.actual_input_tokens ?? 0)} icon={TextQuote} />
            <Metric label="Estimated output" value={String(traceDetail?.estimated_output_tokens ?? 0)} icon={TextQuote} />
            <Metric label="Actual output" value={String(traceDetail?.actual_output_tokens ?? 0)} icon={TextQuote} />
            <Metric label="Prompt size" value={`${traceDetail?.prompt_size_bytes ?? 0} bytes`} icon={TextQuote} />
            <Metric label="Completion truncated" value={traceDetail?.completion_truncated ? "Yes" : "No"} icon={TextQuote} />
            <Metric label="Estimated cost" value={`$${(traceDetail?.estimated_cost_usd ?? 0).toFixed(4)}`} icon={Zap} />
            <Metric label="Latency" value={`${Math.round(traceDetail?.latency_ms ?? 0)} ms`} icon={Clock3} />
            <DetailPill label="Finish reason" value={traceDetail?.finish_reason ?? "n/a"} />
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Pipeline timeline</CardTitle>
            <CardDescription>Pipeline and stage execution history for the selected database.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {(pipelineExecutions?.executions ?? []).slice(0, 5).map((item) => (
              <div key={item.id} className="rounded-xl border border-border bg-gradient-to-br from-card via-card to-muted/30 p-4 shadow-sm">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="text-[11px] uppercase tracking-wider text-muted-foreground">Pipeline execution</div>
                    <div className="text-base font-semibold text-foreground">Execution #{item.id}</div>
                  </div>
                  <Badge variant="outline" className="text-[10px] uppercase">
                    {item.status}
                  </Badge>
                </div>
                <div className="mt-3 grid gap-2 sm:grid-cols-2">
                  <DetailPill label="Trace" value={item.trace_id ?? "n/a"} href={item.trace_id ? `/observability?trace_id=${encodeURIComponent(item.trace_id)}` : undefined} />
                  <DetailPill label="Model" value={item.model_name ?? "n/a"} />
                  <DetailPill label="Duration" value={`${item.duration_seconds?.toFixed(2) ?? "n/a"}s`} />
                  <DetailPill label="Error" value={item.error_message ?? "none"} />
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Lifecycle events</CardTitle>
            <CardDescription>Connection lifecycle, archive, restore, and deletion audit trail.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {lifecycle.length ? (
              lifecycle.slice(0, 6).map((event) => (
                <div key={event.id} className="rounded-xl border border-border bg-card p-4 shadow-sm">
                  <div className="flex items-center justify-between gap-2">
                    <div>
                      <div className="text-[11px] uppercase tracking-wider text-muted-foreground">Lifecycle event</div>
                      <div className="text-sm font-medium text-foreground">{event.event_type}</div>
                    </div>
                    <Button variant="ghost" size="sm" className="h-7 gap-1 px-2 text-[11px]" asChild>
                      <a href={`/observability?trace_id=${encodeURIComponent(event.trace_id ?? "")}`}>
                        <LinkIcon className="h-3.5 w-3.5" /> Open trace
                      </a>
                    </Button>
                  </div>
                  <div className="mt-1 text-xs text-muted-foreground">
                    {event.reason ?? "n/a"} · {event.created_at ? new Date(event.created_at).toLocaleString() : "n/a"}
                  </div>
                </div>
              ))
            ) : (
              <EmptyState icon={Workflow} title="No lifecycle events" description="Disconnect, archive, restore, or delete a database to populate lifecycle audit entries." />
            )}
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Prompt inspector</CardTitle>
            <CardDescription>Versions and observability records for the selected trace.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {promptVersions.length ? (
              promptVersions.slice(0, 3).map((version) => (
                <div key={String(version.id ?? version.trace_id ?? Math.random())} className="rounded-xl border border-border bg-gradient-to-br from-card to-muted/20 p-4 shadow-sm">
                  <div className="flex items-center justify-between gap-2">
                    <div className="text-sm font-medium text-foreground">Version {String(version.version ?? "n/a")}</div>
                    <Badge variant="outline" className="text-[10px] uppercase">
                      {String(version.model_name ?? "unknown")}
                    </Badge>
                  </div>
                  <div className="mt-3 flex items-center justify-between gap-2">
                    <Badge variant="outline" className="text-[10px] uppercase">
                      Trace {version.trace_id ?? "n/a"}
                    </Badge>
                    <Button variant="ghost" size="sm" className="h-7 gap-1 px-2 text-[11px]" asChild>
                      <a href={version.trace_id ? `/observability?trace_id=${encodeURIComponent(version.trace_id)}` : "#"}>
                        <LinkIcon className="h-3.5 w-3.5" /> Trace
                      </a>
                    </Button>
                  </div>
                  <div className="mt-3 rounded-lg border border-border/70 bg-background/70 p-3 text-xs leading-relaxed text-muted-foreground">
                    {String(version.generated_prompt ?? "").slice(0, 420)}
                  </div>
                </div>
              ))
            ) : (
              <EmptyState icon={Sparkles} title="No prompt versions selected" description="Select a trace to inspect prompt versions and observability." />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">AI response inspector</CardTitle>
            <CardDescription>Raw response, parsed response, validation, fallback usage, and retry count.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <Detail label="Deployment" value={traceDetail?.deployment ?? traceDetail?.model_name ?? "n/a"} />
            <Detail label="Artifact type" value={traceDetail?.artifact_type ?? "n/a"} />
            <Detail label="Module" value={traceDetail?.module ?? "n/a"} />
            <Detail label="Database" value={String(traceDetail?.database_id ?? dbId)} />
            <Detail label="Context source" value={(traceDetail as any)?.context_source ?? "persisted"} />
            <Detail label="Used context" value={(traceDetail as any)?.used_context ? "yes" : "no"} />
            <Detail label="Fallback reason" value={(traceDetail as any)?.fallback_reason ?? "none"} />
            <Detail label="Finish reason" value={traceDetail?.finish_reason ?? "n/a"} />
            <Detail label="Validation result" value={traceDetail?.execution_status ?? "n/a"} />
            <Detail label="Prompt tokens" value={String(traceDetail?.prompt_tokens ?? 0)} />
            <Detail label="Completion tokens" value={String(traceDetail?.completion_tokens ?? 0)} />
            <Detail label="Reasoning tokens" value={String(traceDetail?.reasoning_tokens ?? 0)} />
            <Detail label="Estimated cost" value={`$${(traceDetail?.estimated_cost_usd ?? 0).toFixed(4)}`} />
            <div className="rounded-xl border border-border bg-gradient-to-br from-card via-card to-muted/20 p-4 shadow-sm">
              <div className="flex items-center justify-between">
                <div className="text-[11px] uppercase tracking-wider text-muted-foreground">Prompt observability</div>
                <div className="flex items-center gap-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 gap-1 px-2 text-[11px]"
                    onClick={() =>
                      navigator.clipboard.writeText(
                        [
                          `trace_id=${traceDetail?.trace_id ?? "n/a"}`,
                          `model=${traceDetail?.model_name ?? "n/a"}`,
                          `finish_reason=${traceDetail?.finish_reason ?? "n/a"}`,
                          `prompt_tokens=${traceDetail?.prompt_tokens ?? 0}`,
                          `completion_tokens=${traceDetail?.completion_tokens ?? 0}`,
                        ].join("\n"),
                      )
                    }
                  >
                    <Copy className="h-3.5 w-3.5" /> Copy
                  </Button>
                  <Button variant="ghost" size="sm" className="h-7 gap-1 px-2 text-[11px]" onClick={() => downloadJson(`observability-trace-${selectedTraceId ?? "trace"}.json`, traceDetail ?? {})}>
                    <Download className="h-3.5 w-3.5" /> Download
                  </Button>
                </div>
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                {promptObservability.length ? promptObservability.slice(0, 8).map((item: any, index: number) => (
                  <div key={`${item.id ?? index}`} className="rounded-lg border border-border bg-background/70 px-3 py-2 text-xs text-muted-foreground shadow-sm">
                    <div className="font-medium text-foreground">{String(item.model_name ?? "prompt")} · {String(item.finish_reason ?? "n/a")}</div>
                    <div className="mt-1 flex flex-wrap gap-2">
                      <Badge variant="outline" className="text-[10px] uppercase">Prompt {item.prompt_tokens ?? 0}</Badge>
                      <Badge variant="outline" className="text-[10px] uppercase">Completion {item.completion_tokens ?? 0}</Badge>
                      <Badge variant="outline" className="text-[10px] uppercase">Reasoning {item.reasoning_tokens ?? 0}</Badge>
                      <Badge variant="outline" className="text-[10px] uppercase">Trunc {item.completion_truncated ? "yes" : "no"}</Badge>
                    </div>
                  </div>
                )) : <div className="text-xs text-muted-foreground">No prompt observability records yet.</div>}
              </div>
            </div>
            <div className="rounded-lg border border-border bg-muted/20 p-3 text-xs text-muted-foreground">
              {traceDetail?.pipeline_executions?.length
                ? "This trace has a persisted pipeline context snapshot and execution history."
                : "No persisted pipeline context snapshot is attached to this trace."}
            </div>
          </CardContent>
        </Card>
      </section>

      <Sheet open={Boolean(selectedTraceId)} onOpenChange={(open) => !open && setSelectedTraceId(null)}>
        <SheetContent className="w-full overflow-y-auto sm:max-w-3xl">
          <SheetHeader>
            <SheetTitle>Trace details</SheetTitle>
            <SheetDescription>{selectedTraceId ?? "n/a"}</SheetDescription>
          </SheetHeader>
          <div className="mt-6 space-y-4">
            <div className="grid gap-3 sm:grid-cols-2">
              <Detail label="Trace ID" value={traceDetail?.trace_id ?? "n/a"} href={traceDetail?.trace_id ? `/observability?trace_id=${encodeURIComponent(traceDetail.trace_id)}` : undefined} />
              <Detail label="Prompt ID" value={traceDetail?.prompt_id ?? "n/a"} href={traceDetail?.trace_id ? `/prompt-studio?trace_id=${encodeURIComponent(traceDetail.trace_id)}` : undefined} />
              <Detail label="Prompt version" value={traceDetail?.prompt_version ?? "n/a"} href={traceDetail?.trace_id ? `/prompt-studio?trace_id=${encodeURIComponent(traceDetail.trace_id)}` : undefined} />
              <Detail label="Model" value={traceDetail?.model_name ?? "n/a"} />
              <Detail label="Deployment" value={traceDetail?.deployment ?? "n/a"} />
              <Detail label="Module" value={traceDetail?.module ?? "n/a"} />
              <Detail label="Artifact type" value={traceDetail?.artifact_type ?? "n/a"} />
              <Detail label="Database" value={String(traceDetail?.database_id ?? dbId)} />
              <Detail label="Execution status" value={traceDetail?.execution_status ?? "n/a"} />
              <Detail label="Finish reason" value={traceDetail?.finish_reason ?? "n/a"} />
              <Detail label="Prompt tokens" value={String(traceDetail?.prompt_tokens ?? 0)} />
              <Detail label="Completion tokens" value={String(traceDetail?.completion_tokens ?? 0)} />
              <Detail label="Reasoning tokens" value={String(traceDetail?.reasoning_tokens ?? 0)} />
              <Detail label="Estimated input tokens" value={String(traceDetail?.estimated_input_tokens ?? 0)} />
              <Detail label="Actual input tokens" value={String(traceDetail?.actual_input_tokens ?? 0)} />
              <Detail label="Estimated output tokens" value={String(traceDetail?.estimated_output_tokens ?? 0)} />
              <Detail label="Actual output tokens" value={String(traceDetail?.actual_output_tokens ?? 0)} />
              <Detail label="Prompt size bytes" value={String(traceDetail?.prompt_size_bytes ?? 0)} />
              <Detail label="Completion truncated" value={traceDetail?.completion_truncated ? "Yes" : "No"} />
              <Detail label="Estimated cost" value={`$${(traceDetail?.estimated_cost_usd ?? 0).toFixed(4)}`} />
            </div>
            <TraceSummaryChips title="Prompt observability" value={traceDetail?.prompt_observability ?? []} />
            <TraceSummaryChips title="Stage executions" value={traceDetail?.stage_executions ?? []} />
            <TraceSummaryChips title="Pipeline executions" value={traceDetail?.pipeline_executions ?? []} />
            <TraceSummaryChips title="Prompt versions" value={traceDetail?.prompt_versions ?? []} />
            <TraceSummaryChips title="Linked prompt versions" value={traceDetail?.linked_prompt_versions ?? []} />
            <TraceSummaryChips title="Linked stage executions" value={traceDetail?.linked_stage_executions ?? []} />
            <TraceSummaryChips title="Linked pipeline execution" value={traceDetail?.linked_pipeline_execution ? [traceDetail.linked_pipeline_execution] : []} />
            <TraceSummaryChips title="Linked job" value={traceDetail?.linked_job ? [traceDetail.linked_job] : []} />
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}

function Metric({ label, value, icon: Icon }: { label: string; value: string; icon: ComponentType<{ className?: string }> }) {
  return (
    <div className="rounded-md border border-border bg-card p-3">
      <div className="flex items-center gap-2 text-[11px] uppercase tracking-wider text-muted-foreground">
        <Icon className="h-3.5 w-3.5" />
        {label}
      </div>
      <div className="mt-1 text-lg font-semibold text-foreground">{value}</div>
    </div>
  );
}

function Detail({ label, value, href }: { label: string; value: string; href?: string }) {
  const shell = (
    <div className="rounded-xl border border-border bg-gradient-to-br from-card to-muted/20 p-4 shadow-sm transition-colors hover:border-primary/40 hover:bg-primary/5">
      <div className="text-[11px] uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="mt-1 truncate text-sm font-medium text-foreground">{value}</div>
    </div>
  );

  if (!href) return shell;
  return (
    <a href={href} className="block">
      {shell}
    </a>
  );
}

function TraceSummary({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-md border border-border bg-muted/20 px-3 py-2">
      <span className="text-[11px] uppercase tracking-wider text-muted-foreground">{label}</span>
      <span className="text-sm text-foreground">{value}</span>
    </div>
  );
}

function TraceSummaryChips({ title, value }: { title: string; value: Array<Record<string, unknown>> }) {
  return (
    <div className="space-y-2">
      <div className="text-xs uppercase tracking-wider text-muted-foreground">{title}</div>
      <div className="flex flex-wrap gap-2">
        {value.length ? value.slice(0, 8).map((item, index) => (
          <Badge key={`${title}-${index}`} variant="outline" className="text-[10px] uppercase">
            {String(item.trace_id ?? item.status ?? item.version ?? item.model_name ?? item.stage_name ?? "item")}
          </Badge>
        )) : <div className="text-xs text-muted-foreground">No records available.</div>}
      </div>
    </div>
  );
}

function DetailPill({ label, value, href }: { label: string; value: string; href?: string }) {
  const inner = (
    <div className="flex items-center justify-between gap-3 rounded-lg border border-border bg-background/80 px-3 py-2 text-xs shadow-sm transition-colors hover:border-primary/40 hover:bg-primary/5">
      <span className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</span>
      <span className="truncate font-medium text-foreground">{value}</span>
    </div>
  );

  if (!href) return inner;
  return (
    <a href={href} className="block">
      {inner}
    </a>
  );
}

function downloadJson(filename: string, payload: unknown) {
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}
