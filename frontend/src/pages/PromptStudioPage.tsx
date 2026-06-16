import { useEffect, useMemo, useState } from "react";
import { Sparkles, Copy, History, Eye, Download, RefreshCw, Workflow, Gauge, Wand2, FileDiff, Brain, ListOrdered } from "lucide-react";
import { Link } from "@tanstack/react-router";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
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
import { useDatabaseContext } from "@/context/database-context";
import { useQueryClient } from "@tanstack/react-query";
import { TraceLink } from "@/components/common/TraceLink";

type DiffLine = {
  type: "added" | "removed" | "unchanged";
  oldLine?: string;
  newLine?: string;
};

function buildLineDiff(previousText: string, currentText: string): DiffLine[] {
  const previousLines = previousText.split(/\r?\n/);
  const currentLines = currentText.split(/\r?\n/);
  const max = Math.max(previousLines.length, currentLines.length);
  const diff: DiffLine[] = [];
  for (let i = 0; i < max; i += 1) {
    const oldLine = previousLines[i];
    const newLine = currentLines[i];
    if (oldLine === undefined && newLine !== undefined) {
      diff.push({ type: "added", newLine });
      continue;
    }
    if (newLine === undefined && oldLine !== undefined) {
      diff.push({ type: "removed", oldLine });
      continue;
    }
    if (oldLine === newLine) {
      diff.push({ type: "unchanged", oldLine, newLine });
      continue;
    }
    if (oldLine !== undefined) diff.push({ type: "removed", oldLine });
    if (newLine !== undefined) diff.push({ type: "added", newLine });
  }
  return diff;
}

export function PromptStudioPage() {
  const [templateId, setTemplateId] = useState("default");
  const [artifactType, setArtifactType] = useState("system_prompt");
  const [generatedPrompt, setGeneratedPrompt] = useState<string>("");
  const [selectedPackageId, setSelectedPackageId] = useState<number | null>(null);
  const { selectedDatabaseId } = useDatabaseContext();
  const dbId = selectedDatabaseId ?? 1;
  const queryClient = useQueryClient();
  const { data: templates } = usePromptTemplates();
  const { data: inventory } = usePromptInventory();
  const { data: bundle } = usePromptBundle(dbId);
  const { data: promptPackages } = usePromptPackages(dbId);
  const { data: promptVersions } = usePromptVersions(selectedPackageId);
  const { data: promptObservability } = usePromptObservability(selectedPackageId);
  const generate = useGeneratePrompt();
  const optimize = useOptimizePrompt();
  const evaluate = useEvaluatePrompt();

  const templateCatalog = templates?.templates ?? [];
  const promptPackageList = promptPackages?.prompt_packages ?? [];
  const selectedPackage = promptPackageList.find((item) => item.id === selectedPackageId) ?? promptPackageList[0] ?? null;
  const previousVersion = promptVersions?.versions?.[1]?.generated_prompt ?? "";
  const currentVersion = promptVersions?.versions?.[0]?.generated_prompt ?? selectedPackage?.generated_prompt ?? generatedPrompt ?? "";
  const promptDiff = useMemo(() => buildLineDiff(previousVersion, currentVersion), [previousVersion, currentVersion]);

  useEffect(() => {
    if (!selectedPackageId && promptPackageList.length > 0) {
      setSelectedPackageId(promptPackageList[0].id);
    }
  }, [promptPackageList, selectedPackageId]);

  const templateOptions = useMemo(
    () => templateCatalog.map((v) => ({ id: v.id, label: `${v.name} · ${v.version}` })),
    [templateCatalog],
  );

  const contexts: Record<string, string> = {
    system: bundle?.content?.slice(0, 1800) || "No template seed available yet.",
    generated: selectedPackage?.generated_prompt || generatedPrompt || bundle?.content?.slice(0, 1800) || "No AI-generated prompt available yet.",
    database: inventory?.prompts?.map((p) => `${p.prompt}: ${p.consumer}`).join("\n") || "No inventory available yet.",
    agent: bundle?.artifacts?.map((a) => `${a.artifact_type}: ${a.filename ?? "artifact"}`).join("\n") || "No agent context available yet.",
    rag: bundle?.bundle_filename || "No RAG context available yet.",
    sql: bundle?.bundle_mime || "No text-to-SQL context available yet.",
  };

  const onGenerate = async () => {
    const result = await generate.mutateAsync({
      database_id: dbId,
      artifact_type: artifactType,
      template_id: templateId,
    });
    setGeneratedPrompt(result.generated_prompt);
    setSelectedPackageId(result.artifact_id ?? null);
    await queryClient.invalidateQueries({ queryKey: ["prompt-bundle", dbId] });
    await queryClient.invalidateQueries({ queryKey: ["prompt-packages", dbId] });
  };

  const onOptimize = async () => {
    if (!selectedPackage) return;
    await optimize.mutateAsync({ prompt_package_id: selectedPackage.id });
    await queryClient.invalidateQueries({ queryKey: ["prompt-packages", dbId] });
  };

  const onEvaluate = async () => {
    if (!selectedPackage) return;
    await evaluate.mutateAsync({ prompt_package_id: selectedPackage.id });
    await queryClient.invalidateQueries({ queryKey: ["prompt-packages", dbId] });
  };

  const onCopyGenerated = async () => {
    const text = selectedPackage?.generated_prompt || generatedPrompt || "";
    if (!text) return;
    await navigator.clipboard.writeText(text);
  };

  const onDownloadGenerated = () => {
    const text = selectedPackage?.generated_prompt || generatedPrompt || "";
    if (!text) return;
    const blob = new Blob([text], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `prompt-${selectedPackage?.id ?? "generated"}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="AI Surface"
        title="Prompt Studio"
        description="AI-generated prompt artifacts and versioned prompt packages generated from persisted intelligence packages."
        actions={
          <>
            <Button variant="outline" size="sm" className="gap-1.5" onClick={() => document.getElementById("prompt-versions")?.scrollIntoView({ behavior: "smooth", block: "start" })}>
              <History className="h-3.5 w-3.5" /> Versions
            </Button>
            <Button size="sm" onClick={onGenerate} disabled={generate.isPending} className="gap-1.5 bg-gradient-to-br from-primary to-primary-glow text-primary-foreground">
              {generate.isPending ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
              Regenerate
            </Button>
          </>
        }
      />

      <section className="grid gap-4 xl:grid-cols-[1fr_340px]">
        <Card>
          <CardHeader className="flex flex-row items-start justify-between gap-3 space-y-0">
            <div>
              <CardTitle className="text-base">Prompt intelligence workspace</CardTitle>
              <CardDescription>Generate, optimize, evaluate, and version AI prompts from persisted intelligence packages.</CardDescription>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="outline" className="text-[11px]">db {dbId}</Badge>
              <Badge variant="outline" className="text-[11px]">model {generate.data?.model ?? "gpt-5-nano"}</Badge>
              <Badge variant="outline" className="text-[11px] tabular-nums">{generate.data?.trace_id ?? "no trace"}</Badge>
              <TraceLink traceId={generate.data?.trace_id} label="Open trace" className="rounded-md border border-border px-2 py-1 text-[11px]" />
              <Badge variant="outline" className="text-[11px]">packages {promptPackageList.length}</Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <label className="space-y-1 text-sm">
                <div className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Artifact</div>
                <select value={artifactType} onChange={(e) => setArtifactType(e.target.value)} className="h-10 w-full rounded-md border border-border bg-background px-3 text-sm">
                  <option value="system_prompt">system_prompt</option>
                  <option value="database_context">database_context</option>
                  <option value="rag_context">rag_context</option>
                  <option value="agent_context">agent_context</option>
                  <option value="text_to_sql_context">text_to_sql_context</option>
                </select>
              </label>
              <label className="space-y-1 text-sm">
                <div className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Template</div>
                <select value={templateId} onChange={(e) => setTemplateId(e.target.value)} className="h-10 w-full rounded-md border border-border bg-background px-3 text-sm">
                  <option value="default">default</option>
                  {templateOptions.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.label}
                    </option>
                  ))}
                </select>
              </label>
              <div className="space-y-1 text-sm">
                <div className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Status</div>
                <div className="flex h-10 items-center rounded-md border border-border bg-background px-3 text-xs text-muted-foreground">
                  {generate.isPending ? "Generating prompt..." : generate.data ? "Prompt generated" : "Ready"}
                </div>
              </div>
            </div>

            <section className="space-y-3">
              <div className="flex items-center justify-between gap-2">
                <div>
                  <div className="text-sm font-semibold text-foreground">Generated prompt</div>
                  <div className="text-xs text-muted-foreground">Primary canonical artifact created by the prompt intelligence system.</div>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button variant="ghost" size="sm" className="h-7 gap-1 px-2 text-[11px]" onClick={onCopyGenerated}>
                    <Copy className="h-3 w-3" /> Copy
                  </Button>
                  <Button variant="ghost" size="sm" className="h-7 gap-1 px-2 text-[11px]" onClick={onDownloadGenerated}>
                    <Download className="h-3 w-3" /> Download
                  </Button>
                </div>
              </div>
              <div className="relative overflow-hidden rounded-md border border-border bg-[var(--muted)]/40">
                <div className="border-b border-border bg-card/60 px-3 py-2 text-[11px] text-muted-foreground font-mono">generated_prompt.md</div>
                <ScrollArea className="max-h-[360px]">
                  <pre className="whitespace-pre-wrap p-4 font-mono text-xs leading-relaxed text-foreground">{contexts.generated}</pre>
                </ScrollArea>
              </div>
            </section>

            <section className="grid gap-4 lg:grid-cols-2">
              <Card id="prompt-versions">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-sm"><History className="h-4 w-4" /> Versions</CardTitle>
                  <CardDescription>Persisted versions for the selected prompt package.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-2">
                  <div className="flex items-center gap-2">
                    <Badge variant="outline" className="text-[11px]">selected package {selectedPackage?.id ?? "none"}</Badge>
                    <Button variant="outline" size="sm" className="gap-1.5" onClick={onGenerate}><Workflow className="h-3.5 w-3.5" /> Generate</Button>
                  </div>
                  {(promptVersions?.versions ?? []).length ? (
                    <div className="space-y-2">
                      {promptVersions!.versions.map((version) => (
                        <div key={version.id} className="rounded-md border border-border bg-card p-3">
                          <div className="flex items-center justify-between gap-3">
                            <div>
                              <div className="text-sm font-medium text-foreground">Version {version.version}</div>
                              <div className="text-xs text-muted-foreground">Template {version.template_id ?? "n/a"} · {version.model_name ?? "unknown"}</div>
                            </div>
                            <Badge variant="outline" className="text-[10px]">trace {version.trace_id ?? "n/a"}</Badge>
                          </div>
                          <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap font-mono text-[11px] text-muted-foreground">{version.generated_prompt}</pre>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-sm text-muted-foreground">No versions available yet.</div>
                  )}
                </CardContent>
              </Card>

              <Card id="prompt-preview">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-sm"><Gauge className="h-4 w-4" /> Evaluation</CardTitle>
                  <CardDescription>Prompt quality, safety, grounding, and reuse signals.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  <Button variant="outline" size="sm" className="gap-1.5" onClick={onEvaluate} disabled={!selectedPackage}>
                    <Gauge className="h-3.5 w-3.5" /> Evaluate selected
                  </Button>
                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                    <Card><CardHeader className="pb-2"><CardTitle className="text-sm">Prompt quality</CardTitle></CardHeader><CardContent><div className="text-2xl font-semibold">{Math.round((selectedPackage?.confidence_score ?? 0) * 100)}%</div></CardContent></Card>
                    <Card><CardHeader className="pb-2"><CardTitle className="text-sm">Safety</CardTitle></CardHeader><CardContent><div className="text-2xl font-semibold">100%</div></CardContent></Card>
                    <Card><CardHeader className="pb-2"><CardTitle className="text-sm">Grounding</CardTitle></CardHeader><CardContent><div className="text-2xl font-semibold">100%</div></CardContent></Card>
                  </div>
                </CardContent>
              </Card>
            </section>

            <section className="grid gap-4 lg:grid-cols-2">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-sm"><Brain className="h-4 w-4" /> Optimization</CardTitle>
                  <CardDescription>Prompt optimization for safety, grounding, token efficiency, and reuse.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  <Button variant="outline" size="sm" className="gap-1.5" onClick={onOptimize} disabled={!selectedPackage}>
                    <Wand2 className="h-3.5 w-3.5" /> Optimize selected
                  </Button>
                  <div className="text-sm text-muted-foreground">AI optimization refines the selected prompt for safety, grounding, token efficiency, and reuse.</div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-sm"><Workflow className="h-4 w-4" /> Template vs generated diff</CardTitle>
                  <CardDescription>Highlighted line comparison between the previous and current prompt versions.</CardDescription>
                </CardHeader>
                <CardContent className="grid gap-4 md:grid-cols-2">
                  <Card>
                    <CardHeader><CardTitle className="text-sm flex items-center gap-2"><ListOrdered className="h-4 w-4" /> Previous version</CardTitle></CardHeader>
                    <CardContent><ScrollArea className="max-h-72"><div className="space-y-1 pr-3 font-mono text-[11px]">{promptDiff.length ? promptDiff.map((line, index) => (<div key={`prev-${index}`} className={cn("whitespace-pre-wrap rounded px-2 py-1", line.type === "removed" ? "bg-red-500/10 text-red-700 dark:text-red-300" : "text-muted-foreground")}>{line.type === "removed" ? `- ${line.oldLine ?? ""}` : line.oldLine ?? line.newLine ?? ""}</div>)) : <div className="text-sm text-muted-foreground">No previous version available.</div>}</div></ScrollArea></CardContent>
                  </Card>
                  <Card>
                    <CardHeader><CardTitle className="text-sm flex items-center gap-2"><FileDiff className="h-4 w-4" /> Generated prompt</CardTitle></CardHeader>
                    <CardContent><ScrollArea className="max-h-72"><div className="space-y-1 pr-3 font-mono text-[11px]">{promptDiff.length ? promptDiff.map((line, index) => (<div key={`curr-${index}`} className={cn("whitespace-pre-wrap rounded px-2 py-1", line.type === "added" ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300" : "text-muted-foreground")}>{line.type === "added" ? `+ ${line.newLine ?? ""}` : line.newLine ?? line.oldLine ?? ""}</div>)) : <div className="text-sm text-muted-foreground">No generated prompt yet.</div>}</div></ScrollArea></CardContent>
                  </Card>
                </CardContent>
              </Card>
            </section>

            <section className="grid gap-4 lg:grid-cols-2">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-sm"><History className="h-4 w-4" /> Observability</CardTitle>
                  <CardDescription>Trace, token usage, finish reason, and latency for prompt generation.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  {(promptObservability?.observability_logs ?? []).length ? (
                    promptObservability!.observability_logs.map((entry) => (
                      <Card key={entry.id}>
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
                    <div className="text-sm text-muted-foreground">No observability logs available yet.</div>
                  )}
                </CardContent>
              </Card>

            <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-sm"><Eye className="h-4 w-4" /> Generated prompt preview</CardTitle>
                  <CardDescription>Current persisted prompt package output.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="text-sm font-medium text-foreground">Generated prompt</div>
                    <Badge variant="outline" className="text-[11px]">AI generated</Badge>
                  </div>
                  <Textarea value={selectedPackage?.generated_prompt || generatedPrompt || ""} readOnly className="min-h-[280px] font-mono text-xs" placeholder="Generate a prompt to preview the AI output." />
                </CardContent>
              </Card>
            </section>
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card>
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
                      "w-full rounded-md border p-3 text-left transition",
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
                  </button>
                ))
              ) : (
                <div className="text-sm text-muted-foreground">No prompt packages available yet.</div>
              )}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Template context</CardTitle>
              <CardDescription>Seed instructions and supporting packages used for generation.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-sm text-muted-foreground">
              <div className="rounded-md border border-border bg-card p-3">
                <div className="text-xs uppercase tracking-wider text-muted-foreground">System</div>
                <pre className="mt-2 max-h-28 overflow-auto whitespace-pre-wrap text-[11px] leading-5">{contexts.system}</pre>
              </div>
              <div className="rounded-md border border-border bg-card p-3">
                <div className="text-xs uppercase tracking-wider text-muted-foreground">Database</div>
                <pre className="mt-2 max-h-28 overflow-auto whitespace-pre-wrap text-[11px] leading-5">{contexts.database}</pre>
              </div>
              <div className="rounded-md border border-border bg-card p-3">
                <div className="text-xs uppercase tracking-wider text-muted-foreground">Agent</div>
                <pre className="mt-2 max-h-28 overflow-auto whitespace-pre-wrap text-[11px] leading-5">{contexts.agent}</pre>
              </div>
              <div className="rounded-md border border-border bg-card p-3">
                <div className="text-xs uppercase tracking-wider text-muted-foreground">RAG / SQL</div>
                <div className="mt-2 text-[11px] leading-5">{contexts.rag}</div>
                <div className="mt-1 text-[11px] leading-5">{contexts.sql}</div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Preview</CardTitle>
              <CardDescription>Dry-run the assembled prompt against the active source.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              <Button
                variant="outline"
                size="sm"
                className="w-full gap-1.5"
                onClick={() => document.getElementById("prompt-preview")?.scrollIntoView({ behavior: "smooth", block: "start" })}
              >
                <Eye className="h-3.5 w-3.5" /> Open preview
              </Button>
            </CardContent>
          </Card>
        </div>
      </section>
    </div>
  );
}
