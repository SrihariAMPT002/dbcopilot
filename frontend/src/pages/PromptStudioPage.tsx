import { useEffect, useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/empty-state";
import { LoadingShell, ErrorShell } from "@/components/state-shells";
import { PageHeader } from "@/components/page-header";
import { TraceLink } from "@/components/common/TraceLink";
import { cn } from "@/lib/utils";
import { useDatabaseContext } from "@/context/database-context";
import {
  usePromptBundle,
  usePromptInventory,
  usePromptTemplates,
  useGeneratePrompt,
  usePromptPackages,
  usePromptVersions,
  usePromptObservability,
  useOptimizePrompt,
  useEvaluatePrompt,
} from "@/hooks/usePromptStudio";
import { useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "@/lib/query-keys";
import { Copy, Download, Eye, FileDiff, Gauge, History, RefreshCw, Sparkles, Wand2, Workflow, BarChart3, ShieldAlert } from "lucide-react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, XAxis, YAxis } from "recharts";
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart";

type DiffLine = { type: "added" | "removed" | "unchanged"; oldLine?: string; newLine?: string };

const chartConfig: ChartConfig = {
  versions: { label: "Versions", color: "hsl(var(--primary))" },
  observability: { label: "Observability", color: "hsl(var(--success))" },
  quality: { label: "Quality", color: "hsl(var(--warning))" },
};

function buildLineDiff(previousText: string, currentText: string): DiffLine[] {
  const previousLines = previousText.split(/\r?\n/);
  const currentLines = currentText.split(/\r?\n/);
  const max = Math.max(previousLines.length, currentLines.length);
  const diff: DiffLine[] = [];
  for (let i = 0; i < max; i += 1) {
    const oldLine = previousLines[i];
    const newLine = currentLines[i];
    if (oldLine === undefined && newLine !== undefined) diff.push({ type: "added", newLine });
    else if (newLine === undefined && oldLine !== undefined) diff.push({ type: "removed", oldLine });
    else if (oldLine === newLine) diff.push({ type: "unchanged", oldLine, newLine });
    else {
      if (oldLine !== undefined) diff.push({ type: "removed", oldLine });
      if (newLine !== undefined) diff.push({ type: "added", newLine });
    }
  }
  return diff;
}

export function PromptStudioPage() {
  const { selectedDatabase } = useDatabaseContext();
  const dbId = selectedDatabase?.database_id ?? null;
  const queryClient = useQueryClient();
  const [templateId, setTemplateId] = useState("default");
  const [artifactType, setArtifactType] = useState("system_prompt");
  const [generatedPrompt, setGeneratedPrompt] = useState("");
  const [selectedPackageId, setSelectedPackageId] = useState<number | null>(null);
  const [selectedEvaluation, setSelectedEvaluation] = useState<{
    completeness_score: number;
    safety_score: number;
    grounding_score: number;
    hallucination_risk: number;
    sql_safety_score: number;
    rag_quality_score: number;
    agent_quality_score: number;
    prompt_quality_score: number;
    reasoning_summary?: string | null;
    trace_id?: string | null;
  } | null>(null);

  const templates = usePromptTemplates();
  const inventory = usePromptInventory();
  const bundle = usePromptBundle(dbId ?? 0);
  const promptPackages = usePromptPackages(dbId ?? 0);
  const promptVersions = usePromptVersions(selectedPackageId);
  const promptObservability = usePromptObservability(selectedPackageId);
  const generate = useGeneratePrompt();
  const optimize = useOptimizePrompt();
  const evaluate = useEvaluatePrompt();

  const isLoading =
    templates.isLoading ||
    inventory.isLoading ||
    bundle.isLoading ||
    promptPackages.isLoading;
  const isError =
    templates.isError ||
    inventory.isError ||
    bundle.isError ||
    promptPackages.isError;
  const error = templates.error ?? inventory.error ?? bundle.error ?? promptPackages.error ?? null;

  const templateCatalog = templates.data?.templates ?? [];
  const promptPackageList = promptPackages.data?.prompt_packages ?? [];
  const selectedPackage = promptPackageList.find((item) => item.id === selectedPackageId) ?? promptPackageList[0] ?? null;

  useEffect(() => {
    if (!selectedPackageId && promptPackageList.length > 0) {
      setSelectedPackageId(promptPackageList[0].id);
    }
  }, [promptPackageList, selectedPackageId]);

  const previousVersion = promptVersions.data?.versions?.[1]?.generated_prompt ?? "";
  const currentVersion = promptVersions.data?.versions?.[0]?.generated_prompt ?? selectedPackage?.generated_prompt ?? generatedPrompt ?? "";
  const promptDiff = useMemo(() => buildLineDiff(previousVersion, currentVersion), [previousVersion, currentVersion]);
  const templateOptions = useMemo(() => templateCatalog.map((v) => ({ id: v.id, label: `${v.name} · ${v.version}` })), [templateCatalog]);
  const latestVersion = promptVersions.data?.versions?.[0] ?? null;
  const priorVersion = promptVersions.data?.versions?.[1] ?? null;

  const generatedText = selectedPackage?.generated_prompt ?? generatedPrompt;
  const generatedPreview = generatedText || "";

  const trendData = useMemo(
    () => [
      {
        label: "Packages",
        versions: promptPackageList.length,
        observability: promptObservability.data?.observability_logs?.length ?? 0,
        quality: Math.round((selectedPackage?.confidence_score ?? 0) * 100),
      },
      {
        label: "Versions",
        versions: promptVersions.data?.versions?.length ?? 0,
        observability: promptObservability.data?.observability_logs?.length ?? 0,
        quality: Math.round((selectedEvaluation?.prompt_quality_score ?? selectedPackage?.confidence_score ?? 0) * 100),
      },
      {
        label: "Trace",
        versions: selectedPackage?.trace_id ? 1 : 0,
        observability: promptObservability.data?.observability_logs?.length ?? 0,
        quality: Math.round((selectedEvaluation?.safety_score ?? 0) * 100),
      },
    ],
    [promptPackageList.length, promptObservability.data?.observability_logs?.length, promptVersions.data?.versions?.length, selectedEvaluation?.prompt_quality_score, selectedEvaluation?.safety_score, selectedPackage?.confidence_score, selectedPackage?.trace_id],
  );

  const onGenerate = async () => {
    if (!dbId) return;
    const result = await generate.mutateAsync({ database_id: dbId, artifact_type: artifactType, template_id: templateId });
    setGeneratedPrompt(result.generated_prompt);
    setSelectedPackageId(result.artifact_id ?? null);
    await queryClient.invalidateQueries({ queryKey: queryKeys.promptBundle(dbId) });
    await queryClient.invalidateQueries({ queryKey: queryKeys.promptPackages(dbId) });
  };

  const onOptimize = async () => {
    if (!selectedPackage) return;
    await optimize.mutateAsync({ prompt_package_id: selectedPackage.id });
    await queryClient.invalidateQueries({ queryKey: queryKeys.promptPackages(dbId) });
    await queryClient.invalidateQueries({ queryKey: queryKeys.promptVersions(selectedPackage.id) });
  };

  const onEvaluate = async () => {
    if (!selectedPackage) return;
    const result = await evaluate.mutateAsync({ prompt_package_id: selectedPackage.id });
    setSelectedEvaluation(result);
    await queryClient.invalidateQueries({ queryKey: queryKeys.promptPackages(dbId) });
  };

  const onCopyGenerated = async () => {
    if (!generatedPreview) return;
    await navigator.clipboard.writeText(generatedPreview);
  };

  const onDownloadGenerated = () => {
    if (!generatedPreview) return;
    const blob = new Blob([generatedPreview], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `prompt-${selectedPackage?.id ?? "generated"}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <PageHeader eyebrow="AI Surface" title="Prompt Studio" description="AI-generated prompt artifacts and versioned prompt packages generated from persisted intelligence packages." />
        <LoadingShell title="Prompt Studio loading" description="Loading prompt templates, inventory, bundle, and package history..." />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="space-y-6">
        <PageHeader eyebrow="AI Surface" title="Prompt Studio" description="AI-generated prompt artifacts and versioned prompt packages generated from persisted intelligence packages." />
        <ErrorShell title="Prompt Studio unavailable" description={error instanceof Error ? error.message : "Failed to load prompt studio data for the selected database."} />
      </div>
    );
  }

  if (!promptPackageList.length && !generatedText) {
    return (
      <div className="space-y-6">
        <PageHeader eyebrow="AI Surface" title="Prompt Studio" description="AI-generated prompt artifacts and versioned prompt packages generated from persisted intelligence packages." />
        <EmptyState
          icon={Sparkles}
          title="No prompt packages yet"
          description="Generate your first prompt bundle after sync so the studio can show versions, traces, and evaluation data."
          action={
            <Button onClick={onGenerate} disabled={!dbId || generate.isPending} className="gap-1.5">
              <Sparkles className="h-3.5 w-3.5" />
              Generate prompt
            </Button>
          }
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="AI Surface"
        title="Prompt Studio"
        description="AI-generated prompt artifacts and versioned prompt packages generated from persisted intelligence packages."
        actions={
          <>
            <Badge variant="outline" className="text-[11px]">
              db {dbId}
            </Badge>
            <Badge variant="outline" className="text-[11px]">
              packages {promptPackageList.length}
            </Badge>
            <Button variant="outline" size="sm" className="gap-1.5" onClick={() => document.getElementById("prompt-versions")?.scrollIntoView({ behavior: "smooth", block: "start" })}>
              <History className="h-3.5 w-3.5" />
              Versions
            </Button>
            <Button size="sm" onClick={onGenerate} disabled={!dbId || generate.isPending} className="gap-1.5 bg-gradient-to-br from-primary to-primary-glow text-primary-foreground">
              {generate.isPending ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
              Regenerate
            </Button>
          </>
        }
      />

      <section className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Card className="border-border bg-card shadow-sm">
          <CardContent className="p-4">
            <div className="text-xs uppercase tracking-wider text-muted-foreground">Prompt quality</div>
            <div className="mt-2 text-2xl font-semibold text-foreground">{Math.round((selectedEvaluation?.prompt_quality_score ?? selectedPackage?.confidence_score ?? 0) * 100)}%</div>
            <div className="mt-1 text-xs text-muted-foreground">Quality is derived from persisted package confidence and latest evaluation.</div>
          </CardContent>
        </Card>
        <Card className="border-border bg-card shadow-sm">
          <CardContent className="p-4">
            <div className="text-xs uppercase tracking-wider text-muted-foreground">Trace</div>
            <div className="mt-2 text-2xl font-semibold text-foreground truncate">{selectedPackage?.trace_id ?? generate.data?.trace_id ?? "n/a"}</div>
            <div className="mt-1 text-xs text-muted-foreground">Open the trace to inspect prompt tokens, latency, and finish reason.</div>
          </CardContent>
        </Card>
        <Card className="border-border bg-card shadow-sm">
          <CardContent className="p-4">
            <div className="text-xs uppercase tracking-wider text-muted-foreground">Versions</div>
            <div className="mt-2 text-2xl font-semibold text-foreground">{promptVersions.data?.versions?.length ?? 0}</div>
            <div className="mt-1 text-xs text-muted-foreground">Versioned prompt snapshots for the selected package.</div>
          </CardContent>
        </Card>
        <Card className="border-border bg-card shadow-sm">
          <CardContent className="p-4">
            <div className="text-xs uppercase tracking-wider text-muted-foreground">Observability</div>
            <div className="mt-2 text-2xl font-semibold text-foreground">{promptObservability.data?.observability_logs?.length ?? 0}</div>
            <div className="mt-1 text-xs text-muted-foreground">Traceable logs with tokens, latency, and finish reason.</div>
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-4 xl:grid-cols-[1fr_360px]">
        <Card className="overflow-hidden border-border/70 bg-card/90 shadow-[0_18px_40px_-28px_rgba(15,23,42,0.45)]">
          <CardHeader className="border-b border-border/60 bg-gradient-to-r from-slate-950/5 via-background to-slate-900/5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <CardTitle className="text-base">Prompt workspace</CardTitle>
                <CardDescription>Generate, optimize, evaluate, and version prompts from persisted intelligence packages.</CardDescription>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="outline" className="text-[11px]">model {generate.data?.model ?? selectedPackage?.model_name ?? "gpt-5-nano"}</Badge>
                <Badge variant="outline" className="text-[11px] tabular-nums">{selectedPackage?.prompt_version ?? generate.data?.prompt_version ?? "1.0"}</Badge>
                <TraceLink traceId={selectedPackage?.trace_id ?? generate.data?.trace_id} label="Open trace" className="rounded-md border border-border px-2 py-1 text-[11px]" />
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-5 p-5">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <label className="space-y-1 text-sm">
                <div className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Artifact</div>
                <select value={artifactType} onChange={(e) => setArtifactType(e.target.value)} className="h-11 w-full rounded-lg border border-border bg-background px-3 text-sm">
                  <option value="system_prompt">system_prompt</option>
                  <option value="database_context">database_context</option>
                  <option value="rag_context">rag_context</option>
                  <option value="agent_context">agent_context</option>
                  <option value="text_to_sql_context">text_to_sql_context</option>
                </select>
              </label>
              <label className="space-y-1 text-sm">
                <div className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Template</div>
                <select value={templateId} onChange={(e) => setTemplateId(e.target.value)} className="h-11 w-full rounded-lg border border-border bg-background px-3 text-sm">
                  <option value="default">default</option>
                  {templateOptions.map((t) => (
                    <option key={t.id} value={t.id}>{t.label}</option>
                  ))}
                </select>
              </label>
              <div className="space-y-1 text-sm">
                <div className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Status</div>
                <div className="flex h-11 items-center rounded-lg border border-border bg-background px-3 text-xs text-muted-foreground">
                  {generate.isPending ? "Generating prompt..." : selectedPackage ? "Prompt ready" : "Ready to generate"}
                </div>
              </div>
            </div>

            <section className="grid gap-4 lg:grid-cols-2">
              <div className="space-y-3 rounded-2xl border border-border/70 bg-background/80 p-4 shadow-sm">
                <div className="flex items-center justify-between gap-2">
                  <div>
                    <div className="text-sm font-semibold text-foreground">Generated prompt</div>
                    <div className="text-xs text-muted-foreground">Primary canonical artifact created by the prompt intelligence system.</div>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button variant="ghost" size="sm" className="h-8 gap-1 px-2 text-[11px]" onClick={onCopyGenerated} disabled={!generatedPreview}>
                      <Copy className="h-3 w-3" /> Copy
                    </Button>
                    <Button variant="ghost" size="sm" className="h-8 gap-1 px-2 text-[11px]" onClick={onDownloadGenerated} disabled={!generatedPreview}>
                      <Download className="h-3 w-3" /> Download
                    </Button>
                  </div>
                </div>
                <div className="rounded-xl border border-border bg-[var(--muted)]/35">
                  <div className="border-b border-border/70 bg-card/70 px-3 py-2 text-[11px] font-mono text-muted-foreground">generated_prompt.md</div>
                  <ScrollArea className="max-h-[340px]">
                    <div className="whitespace-pre-wrap p-4 font-mono text-xs leading-6 text-foreground">{generatedPreview || "No prompt generated yet."}</div>
                  </ScrollArea>
                </div>
              </div>

              <div className="space-y-3 rounded-2xl border border-border/70 bg-background/80 p-4 shadow-sm">
                <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
                  <BarChart3 className="h-4 w-4" />
                  Prompt trends
                </div>
                <ChartContainer config={chartConfig} className="h-[280px] w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={trendData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="label" tickLine={false} axisLine={false} />
                      <YAxis tickLine={false} axisLine={false} />
                      <ChartTooltip content={<ChartTooltipContent />} />
                      <Bar dataKey="versions" fill="var(--color-versions)" radius={[8, 8, 0, 0]} />
                      <Bar dataKey="observability" fill="var(--color-observability)" radius={[8, 8, 0, 0]} />
                      <Bar dataKey="quality" fill="var(--color-quality)" radius={[8, 8, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </ChartContainer>
                <div className="grid grid-cols-3 gap-2 text-xs text-muted-foreground">
                  <div className="rounded-lg border border-border bg-card p-3">Safety {Math.round((selectedEvaluation?.safety_score ?? 0) * 100)}%</div>
                  <div className="rounded-lg border border-border bg-card p-3">Grounding {Math.round((selectedEvaluation?.grounding_score ?? 0) * 100)}%</div>
                  <div className="rounded-lg border border-border bg-card p-3">Traces {promptObservability.data?.observability_logs?.length ?? 0}</div>
                </div>
              </div>
            </section>

            <section className="grid gap-4 lg:grid-cols-2">
              <Card id="prompt-versions" className="border-border bg-background/70 shadow-sm">
                <CardHeader className="border-b border-border/60 bg-gradient-to-r from-background to-muted/30">
                  <CardTitle className="flex items-center gap-2 text-sm"><History className="h-4 w-4" /> Versions</CardTitle>
                  <CardDescription>Persisted versions for the selected prompt package.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3 p-5">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant="outline" className="text-[11px]">selected package {selectedPackage?.id ?? "none"}</Badge>
                    <Button variant="outline" size="sm" className="gap-1.5" onClick={onGenerate} disabled={!dbId || generate.isPending}>
                      <Workflow className="h-3.5 w-3.5" /> Generate
                    </Button>
                  </div>
                  {(promptVersions.data?.versions ?? []).length ? (
                    <div className="space-y-3">
                      {promptVersions.data!.versions.map((version) => (
                        <div key={version.id} className={cn("rounded-2xl border p-4 shadow-sm transition", version.id === latestVersion?.id ? "border-primary/30 bg-primary/5" : "border-border bg-card")}>
                          <div className="flex items-start justify-between gap-3">
                            <div>
                              <div className="flex flex-wrap items-center gap-2">
                                <div className="text-sm font-semibold text-foreground">Version {version.version}</div>
                                {version.id === latestVersion?.id ? <Badge className="border-primary/30 bg-primary/10 text-primary text-[10px]">latest</Badge> : null}
                              </div>
                              <div className="mt-1 text-xs text-muted-foreground">Template {version.template_id ?? "n/a"} | {version.model_name ?? "unknown"}</div>
                            </div>
                            <TraceLink traceId={version.trace_id} label="Trace" className="rounded-md border border-border px-2 py-1 text-[10px]" />
                          </div>
                          <div className="mt-3 overflow-hidden rounded-xl border border-dashed border-border bg-background">
                            <div className="border-b border-border/70 bg-card/70 px-3 py-2 text-[11px] font-mono text-muted-foreground">generated_prompt.md</div>
                            <div className="max-h-40 overflow-auto whitespace-pre-wrap p-3 font-mono text-[11px] leading-6 text-foreground">{version.generated_prompt}</div>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <EmptyState icon={FileDiff} title="No versions yet" description="Generate or optimize a prompt to create version history." />
                  )}
                </CardContent>
              </Card>

              <Card className="border-border bg-background/70 shadow-sm">
                <CardHeader className="border-b border-border/60 bg-gradient-to-r from-background to-muted/30">
                  <CardTitle className="flex items-center gap-2 text-sm"><Gauge className="h-4 w-4" /> Evaluation</CardTitle>
                  <CardDescription>Prompt quality, safety, grounding, and reuse signals.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3 p-4">
                  <Button variant="outline" size="sm" className="gap-1.5" onClick={onEvaluate} disabled={!selectedPackage || evaluate.isPending}>
                    <Gauge className={cn("h-3.5 w-3.5", evaluate.isPending && "animate-spin")} /> Evaluate selected
                  </Button>
                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                    <Metric value={selectedEvaluation ? formatPct(selectedEvaluation.prompt_quality_score) : formatPct(selectedPackage?.confidence_score)} label="Prompt quality" />
                    <Metric value={selectedEvaluation ? formatPct(selectedEvaluation.safety_score) : "N/A"} label="Safety" />
                    <Metric value={selectedEvaluation ? formatPct(selectedEvaluation.grounding_score) : "N/A"} label="Grounding" />
                  </div>
                  {selectedEvaluation ? (
                    <div className="rounded-2xl border border-border bg-gradient-to-br from-background to-muted/30 p-4 text-sm text-muted-foreground shadow-sm">
                      <div className="flex items-center justify-between gap-2">
                        <div className="font-semibold text-foreground">Latest evaluation</div>
                        <Badge variant="outline" className="text-[10px]">trace {selectedEvaluation.trace_id ?? "n/a"}</Badge>
                      </div>
                      <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
                        <StatPill label="completeness" value={formatPct(selectedEvaluation.completeness_score)} />
                        <StatPill label="sql safety" value={formatPct(selectedEvaluation.sql_safety_score)} />
                        <StatPill label="rag quality" value={formatPct(selectedEvaluation.rag_quality_score)} />
                        <StatPill label="agent quality" value={formatPct(selectedEvaluation.agent_quality_score)} />
                      </div>
                      {selectedEvaluation.reasoning_summary ? <div className="mt-3 rounded-xl border border-border bg-card p-3 text-xs leading-5 text-foreground">{selectedEvaluation.reasoning_summary}</div> : null}
                    </div>
                  ) : (
                    <EmptyState icon={ShieldAlert} title="No evaluation yet" description="Run evaluation to surface prompt safety and grounding signals." />
                  )}
                </CardContent>
              </Card>
            </section>

            <section className="grid gap-4 lg:grid-cols-[1fr_1fr]">
              <Card className="border-border/70 bg-background/80 shadow-sm">
                <CardHeader className="border-b border-border/60 bg-gradient-to-r from-slate-950/5 via-background to-slate-900/5">
                  <CardTitle className="flex items-center gap-2 text-sm"><FileDiff className="h-4 w-4" /> Diff view</CardTitle>
                  <CardDescription>Side-by-side comparison between the latest and previous prompt versions.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3 p-4">
                  <div className="flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
                    <Badge variant="outline" className="border-primary/30 bg-primary/10 text-primary text-[10px]">current {latestVersion?.version ?? "n/a"}</Badge>
                    <Badge variant="outline" className="text-[10px]">previous {priorVersion?.version ?? "n/a"}</Badge>
                  </div>
                  <div className="grid gap-3 lg:grid-cols-2">
                    <div className="overflow-hidden rounded-2xl border border-border/70 bg-background">
                      <div className="border-b border-border/70 bg-card/70 px-3 py-2 text-[11px] font-mono text-muted-foreground">Previous</div>
                      <ScrollArea className="h-[320px]">
                        <div className="space-y-0.5 p-3 font-mono text-[11px] leading-6">
                          {promptDiff.map((line, index) => (
                            <div key={`prev-${index}`} className={cn("whitespace-pre-wrap rounded px-2 py-0.5", line.type === "removed" ? "bg-rose-500/10 text-rose-700" : line.type === "added" ? "text-transparent" : "text-foreground")}>
                              {line.oldLine ?? " "}
                            </div>
                          ))}
                        </div>
                      </ScrollArea>
                    </div>
                    <div className="overflow-hidden rounded-2xl border border-border/70 bg-background">
                      <div className="border-b border-border/70 bg-card/70 px-3 py-2 text-[11px] font-mono text-muted-foreground">Current</div>
                      <ScrollArea className="h-[320px]">
                        <div className="space-y-0.5 p-3 font-mono text-[11px] leading-6">
                          {promptDiff.map((line, index) => (
                            <div key={`curr-${index}`} className={cn("whitespace-pre-wrap rounded px-2 py-0.5", line.type === "added" ? "bg-emerald-500/10 text-emerald-700" : line.type === "removed" ? "text-transparent" : "text-foreground")}>
                              {line.newLine ?? " "}
                            </div>
                          ))}
                        </div>
                      </ScrollArea>
                    </div>
                  </div>
                </CardContent>
              </Card>
              <Card className="border-border/70 bg-background/80 shadow-sm">
                <CardHeader className="border-b border-border/60 bg-gradient-to-r from-background to-muted/30">
                  <CardTitle className="flex items-center gap-2 text-sm"><History className="h-4 w-4" /> Observability</CardTitle>
                  <CardDescription>Trace, token usage, finish reason, and latency for prompt generation.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  {(promptObservability.data?.observability_logs ?? []).length ? (
                    promptObservability.data!.observability_logs.map((entry) => (
                      <Card key={entry.id} className="border-border/70 bg-card shadow-sm">
                        <CardContent className="space-y-2 pt-4">
                          <div className="flex items-center justify-between">
                            <div className="text-sm font-medium">Trace {entry.trace_id ?? "n/a"}</div>
                            <Badge variant="outline" className="text-[10px]">{entry.finish_reason ?? "unknown"}</Badge>
                          </div>
                          <TraceLink traceId={entry.trace_id} label="Open trace" className="text-[11px]" />
                          <div className="grid grid-cols-2 gap-2 text-xs text-muted-foreground sm:grid-cols-4">
                            <div>Prompt {entry.prompt_tokens ?? 0}</div>
                            <div>Completion {entry.completion_tokens ?? 0}</div>
                            <div>Reasoning {entry.reasoning_tokens ?? 0}</div>
                            <div>Latency {Math.round(entry.latency_ms ?? 0)}ms</div>
                          </div>
                        </CardContent>
                      </Card>
                    ))
                  ) : (
                    <EmptyState icon={History} title="No observability logs yet" description="Generate a prompt to create traceable observability records." />
                  )}
                </CardContent>
              </Card>

              <Card className="border-border bg-background/70 shadow-sm">
                <CardHeader className="border-b border-border/60 bg-gradient-to-r from-slate-950/5 via-background to-slate-900/5">
                  <CardTitle className="flex items-center gap-2 text-sm"><Eye className="h-4 w-4" /> Prompt preview</CardTitle>
                  <CardDescription>Current persisted prompt package output.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3 p-4">
                  <div className="flex flex-wrap gap-2">
                    <Button variant="outline" size="sm" className="gap-1.5" onClick={onOptimize} disabled={!selectedPackage || optimize.isPending}>
                      <Wand2 className={cn("h-3.5 w-3.5", optimize.isPending && "animate-spin")} /> Optimize selected
                    </Button>
                    <Button variant="outline" size="sm" className="gap-1.5" onClick={() => document.getElementById("prompt-versions")?.scrollIntoView({ behavior: "smooth", block: "start" })}>
                      <FileDiff className="h-3.5 w-3.5" /> Compare versions
                    </Button>
                  </div>
                  <div className="overflow-hidden rounded-2xl border border-border/70 bg-background shadow-sm">
                    <div className="flex items-center justify-between border-b border-border/70 bg-card/70 px-3 py-2">
                      <div className="text-[11px] font-mono text-muted-foreground">prompt-preview.md</div>
                      <Badge variant="outline" className="text-[10px]">AI generated</Badge>
                    </div>
                    <Textarea value={generatedPreview} readOnly className="min-h-[300px] resize-none border-0 bg-transparent font-mono text-xs shadow-none focus-visible:ring-0" placeholder="Generate a prompt to preview the AI output." />
                  </div>
                </CardContent>
              </Card>
            </section>
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card className="border-border bg-card shadow-sm">
            <CardHeader>
              <CardTitle className="text-base">Prompt packages</CardTitle>
              <CardDescription>Persisted canonical prompt artifacts.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              {promptPackageList.length ? (
                promptPackageList.map((pkg, index) => (
                  <button
                    key={pkg.id}
                    onClick={() => setSelectedPackageId(pkg.id)}
                    className={cn(
                      "w-full rounded-xl border p-3 text-left transition",
                      selectedPackage?.id === pkg.id ? "border-primary/40 bg-primary/5" : "border-border bg-card hover:bg-muted/40",
                    )}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex items-center gap-2 text-sm font-medium text-foreground">
                          {pkg.artifact_type}
                          {index === 0 ? <Badge variant="outline" className="border-primary/40 bg-primary/10 text-primary text-[10px]">latest</Badge> : null}
                        </div>
                        <div className="truncate text-[11px] text-muted-foreground">{pkg.template_id ?? "template"} · v{pkg.prompt_version ?? "1"}</div>
                      </div>
                      <Badge variant="outline" className="shrink-0 tabular-nums text-[10px]">{Math.round((pkg.confidence_score ?? 0) * 100)}%</Badge>
                    </div>
                    <div className="mt-2 text-[11px] text-muted-foreground truncate">{pkg.trace_id ?? "no trace"} · {pkg.execution_status ?? "unknown"}</div>
                  </button>
                ))
              ) : (
                <EmptyState
                  icon={Sparkles}
                  title="No prompt packages yet"
                  description="Generate your first prompt bundle to populate the studio."
                />
              )}
            </CardContent>
          </Card>

          <Card className="border-border bg-card shadow-sm">
            <CardHeader>
              <CardTitle className="text-base">Template context</CardTitle>
              <CardDescription>Seed instructions and supporting packages used for generation.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-sm text-muted-foreground">
              <ContextBlock title="System" value={bundle.data?.content?.slice(0, 1800) ?? "No template seed available yet."} />
              <ContextBlock title="Database" value={inventory.data?.prompts?.map((p) => `${p.prompt}: ${p.consumer}`).join("\n") ?? "No inventory available yet."} />
              <ContextBlock title="Agent" value={bundle.data?.artifacts?.map((a) => `${a.artifact_type}: ${a.filename ?? "artifact"}`).join("\n") ?? "No agent context available yet."} />
              <ContextBlock title="RAG / SQL" value={`${bundle.data?.bundle_filename ?? "No RAG context available yet."}\n${bundle.data?.bundle_mime ?? "No SQL context available yet."}`} />
            </CardContent>
          </Card>
        </div>
      </section>
    </div>
  );
}

function Metric({ value, label }: { value: string; label: string }) {
  return (
    <div className="rounded-xl border border-border bg-card p-3">
      <div className="text-[11px] uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="mt-1 text-xl font-semibold text-foreground">{value}</div>
    </div>
  );
}

function StatPill({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-full border border-border bg-card px-3 py-1.5 text-[11px] shadow-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className="ml-2 font-semibold text-foreground">{value}</span>
    </div>
  );
}

function ContextBlock({ title, value }: { title: string; value: string }) {
  return (
    <div className="rounded-xl border border-border bg-card p-3">
      <div className="text-xs uppercase tracking-wider text-muted-foreground">{title}</div>
      <div className="mt-2 max-h-28 overflow-auto whitespace-pre-wrap text-[11px] leading-5 text-foreground">{value}</div>
    </div>
  );
}

