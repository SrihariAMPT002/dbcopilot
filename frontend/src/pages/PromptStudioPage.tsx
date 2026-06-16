import { useEffect, useMemo, useState } from "react";
import {
  Sparkles,
  Copy,
  History,
  Eye,
  Download,
  RefreshCw,
  Workflow,
  Gauge,
  Wand2,
  FileDiff,
  Brain,
  ListOrdered,
  ArrowRight,
  ExternalLink,
} from "lucide-react";
import { Link } from "@tanstack/react-router";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
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
    if (oldLine !== undefined) {
      diff.push({ type: "removed", oldLine });
    }
    if (newLine !== undefined) {
      diff.push({ type: "added", newLine });
    }
  }
  return diff;
}

export function PromptStudioPage() {
  const [tab, setTab] = useState("generated");
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
    generated:
      selectedPackage?.generated_prompt ||
      generatedPrompt ||
      bundle?.content?.slice(0, 1800) ||
      "No AI-generated prompt available yet.",
    database:
      inventory?.prompts?.map((p) => `${p.prompt}: ${p.consumer}`).join("\n") ||
      "No inventory available yet.",
    agent:
      bundle?.artifacts?.map((a) => `${a.artifact_type}: ${a.filename ?? "artifact"}`).join("\n") ||
      "No agent context available yet.",
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

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="AI Surface"
        title="Prompt Studio"
        description="AI-generated prompt artifacts and versioned prompt packages generated from persisted intelligence packages."
        actions={
          <>
            <Button variant="outline" size="sm" className="gap-1.5">
              <History className="h-3.5 w-3.5" /> Versions
            </Button>
            <Button
              size="sm"
              onClick={onGenerate}
              disabled={generate.isPending}
              className="gap-1.5 bg-gradient-to-br from-primary to-primary-glow text-primary-foreground"
            >
              {generate.isPending ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
              Regenerate
            </Button>
          </>
        }
      />

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1fr_340px]">
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
              {generate.data?.trace_id ? (
                <a
                  href={`/jobs?trace_id=${encodeURIComponent(generate.data.trace_id)}`}
                  className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-[11px] text-primary underline-offset-2 hover:underline"
                >
                  Trace drill-down <ExternalLink className="h-3 w-3" />
                </a>
              ) : null}
              <Badge variant="outline" className="text-[11px]">packages {promptPackageList.length}</Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <label className="space-y-1 text-sm">
                <div className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Artifact</div>
                <select
                  value={artifactType}
                  onChange={(e) => setArtifactType(e.target.value)}
                  className="h-10 w-full rounded-md border border-border bg-background px-3 text-sm"
                >
                  <option value="system_prompt">system_prompt</option>
                  <option value="database_context">database_context</option>
                  <option value="rag_context">rag_context</option>
                  <option value="agent_context">agent_context</option>
                  <option value="text_to_sql_context">text_to_sql_context</option>
                </select>
              </label>
              <label className="space-y-1 text-sm">
                <div className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Template</div>
                <select
                  value={templateId}
                  onChange={(e) => setTemplateId(e.target.value)}
                  className="h-10 w-full rounded-md border border-border bg-background px-3 text-sm"
                >
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

            <Tabs value={tab} onValueChange={setTab}>
              <TabsList className="flex-wrap">
                <TabsTrigger value="generated">Generated Prompt</TabsTrigger>
                <TabsTrigger value="versions">Versions</TabsTrigger>
                <TabsTrigger value="evaluation">Evaluation</TabsTrigger>
                <TabsTrigger value="observability">Observability</TabsTrigger>
                <TabsTrigger value="diff">Diff</TabsTrigger>
                <TabsTrigger value="optimization">Optimization</TabsTrigger>
              </TabsList>

              <TabsContent value="generated" className="pt-4">
                <div className="relative overflow-hidden rounded-md border border-border bg-[var(--muted)]/40">
                  <div className="flex items-center justify-between border-b border-border bg-card/60 px-3 py-2 text-[11px] text-muted-foreground">
                    <span className="font-mono">generated_prompt.md</span>
                    <div className="flex items-center gap-2">
                      <Button variant="ghost" size="sm" className="h-7 gap-1 px-2 text-[11px]">
                        <Copy className="h-3 w-3" /> Copy
                      </Button>
                      <Button variant="ghost" size="sm" className="h-7 gap-1 px-2 text-[11px]">
                        <Download className="h-3 w-3" /> Download
                      </Button>
                    </div>
                  </div>
                  <ScrollArea className="max-h-[360px]">
                    <pre className="whitespace-pre-wrap p-4 font-mono text-xs leading-relaxed text-foreground">
                      {contexts.generated}
                    </pre>
                  </ScrollArea>
                </div>
              </TabsContent>

              <TabsContent value="versions" className="pt-4 space-y-3">
                <div className="flex items-center gap-2">
                  <Badge variant="outline" className="text-[11px]">selected package {selectedPackage?.id ?? "none"}</Badge>
                  <Button variant="outline" size="sm" className="gap-1.5" onClick={onGenerate}>
                    <Workflow className="h-3.5 w-3.5" /> Generate
                  </Button>
                </div>
                <div className="space-y-2">
                  {(promptVersions?.versions ?? []).map((version) => (
                    <div key={version.id} className="rounded-md border border-border bg-card p-3">
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <div className="text-sm font-medium text-foreground">Version {version.version}</div>
                          <div className="text-xs text-muted-foreground">
                            Template {version.template_id ?? "n/a"} · {version.model_name ?? "unknown"}
                          </div>
                        </div>
                        <Badge variant="outline" className="text-[10px]">
                          trace {version.trace_id ?? "n/a"}
                        </Badge>
                        {version.trace_id ? (
                          <a
                            href={`/jobs?trace_id=${encodeURIComponent(version.trace_id)}`}
                            className="ml-2 inline-flex items-center gap-1 text-[11px] text-primary underline-offset-2 hover:underline"
                          >
                            Trace drill-down <ArrowRight className="h-3 w-3" />
                          </a>
                        ) : null}
                      </div>
                      <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap font-mono text-[11px] text-muted-foreground">
                        {version.generated_prompt}
                      </pre>
                    </div>
                  ))}
                  {!promptVersions?.versions?.length && (
                    <div className="text-sm text-muted-foreground">No versions available yet.</div>
                  )}
                </div>
              </TabsContent>

              <TabsContent value="evaluation" className="pt-4 space-y-3">
                <div className="flex items-center gap-2">
                  <Button variant="outline" size="sm" className="gap-1.5" onClick={onEvaluate} disabled={!selectedPackage}>
                    <Gauge className="h-3.5 w-3.5" /> Evaluate selected
                  </Button>
                </div>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                  <Card>
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm">Prompt quality</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="text-2xl font-semibold">{Math.round((selectedPackage?.confidence_score ?? 0) * 100)}%</div>
                    </CardContent>
                  </Card>
                  <Card>
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm">Safety</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="text-2xl font-semibold">100%</div>
                    </CardContent>
                  </Card>
                  <Card>
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm">Grounding</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="text-2xl font-semibold">100%</div>
                    </CardContent>
                  </Card>
                </div>
              </TabsContent>

              <TabsContent value="observability" className="pt-4 space-y-3">
                {(promptObservability?.observability_logs ?? []).map((entry) => (
                  <Card key={entry.id}>
                    <CardContent className="space-y-2 pt-4">
                      <div className="flex items-center justify-between">
                        <div className="text-sm font-medium">Trace {entry.trace_id ?? "n/a"}</div>
                        <Badge variant="outline" className="text-[10px]">
                          {entry.finish_reason ?? "unknown"}
                        </Badge>
                      </div>
                      {entry.trace_id ? (
                        <a
                          href={`/jobs?trace_id=${encodeURIComponent(entry.trace_id)}`}
                          className="inline-flex items-center gap-1 text-[11px] text-primary underline-offset-2 hover:underline"
                        >
                          Trace drill-down <ArrowRight className="h-3 w-3" />
                        </a>
                      ) : null}
                      <div className="grid grid-cols-2 gap-2 text-xs text-muted-foreground sm:grid-cols-4">
                        <div>Prompt {entry.prompt_tokens ?? 0}</div>
                        <div>Completion {entry.completion_tokens ?? 0}</div>
                        <div>Reasoning {entry.reasoning_tokens ?? 0}</div>
                        <div>Latency {Math.round(entry.latency_ms ?? 0)}ms</div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
                {!promptObservability?.observability_logs?.length && (
                  <div className="text-sm text-muted-foreground">No observability logs available yet.</div>
                )}
              </TabsContent>

              <TabsContent value="diff" className="pt-4">
                <div className="mb-3 flex items-center gap-2">
                  <Badge variant="outline" className="text-[11px]">current {selectedPackage?.prompt_version ?? "n/a"}</Badge>
                  <Badge variant="outline" className="text-[11px]">versions {promptVersions?.versions?.length ?? 0}</Badge>
                </div>
                <div className="grid gap-4 md:grid-cols-2">
                  <Card>
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2 text-sm">
                        <ListOrdered className="h-4 w-4" /> Previous version
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <ScrollArea className="max-h-80">
                        <div className="space-y-1 pr-3 font-mono text-[11px]">
                          {promptDiff.length ? (
                            promptDiff.map((line, index) => (
                              <div
                                key={`prev-${index}`}
                                className={cn(
                                  "whitespace-pre-wrap rounded px-2 py-1",
                                  line.type === "removed" ? "bg-red-500/10 text-red-700 dark:text-red-300" : "text-muted-foreground",
                                )}
                              >
                                {line.type === "removed" ? `- ${line.oldLine ?? ""}` : line.oldLine ?? line.newLine ?? ""}
                              </div>
                            ))
                          ) : (
                            <div className="text-sm text-muted-foreground">No previous version available.</div>
                          )}
                        </div>
                      </ScrollArea>
                    </CardContent>
                  </Card>
                  <Card>
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2 text-sm">
                        <FileDiff className="h-4 w-4" /> Generated prompt
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <ScrollArea className="max-h-80">
                        <div className="space-y-1 pr-3 font-mono text-[11px]">
                          {promptDiff.length ? (
                            promptDiff.map((line, index) => (
                              <div
                                key={`curr-${index}`}
                                className={cn(
                                  "whitespace-pre-wrap rounded px-2 py-1",
                                  line.type === "added" ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300" : "text-muted-foreground",
                                )}
                              >
                                {line.type === "added" ? `+ ${line.newLine ?? ""}` : line.newLine ?? line.oldLine ?? ""}
                              </div>
                            ))
                          ) : (
                            <div className="text-sm text-muted-foreground">No generated prompt yet.</div>
                          )}
                        </div>
                      </ScrollArea>
                    </CardContent>
                  </Card>
                </div>
              </TabsContent>

              <TabsContent value="optimization" className="pt-4 space-y-3">
                <div className="flex items-center gap-2">
                  <Button variant="outline" size="sm" className="gap-1.5" onClick={onOptimize} disabled={!selectedPackage}>
                    <Wand2 className="h-3.5 w-3.5" /> Optimize selected
                  </Button>
                </div>
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-sm">
                      <Brain className="h-4 w-4" /> Optimization summary
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="text-sm text-muted-foreground">
                    AI optimization refines the selected prompt for safety, grounding, token efficiency, and reuse.
                  </CardContent>
                </Card>
              </TabsContent>
            </Tabs>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="text-sm font-medium text-foreground">Generated prompt</div>
                <Badge variant="outline" className="text-[11px]">
                  AI generated
                </Badge>
              </div>
              <Textarea
                value={selectedPackage?.generated_prompt || generatedPrompt || ""}
                readOnly
                className="min-h-[280px] font-mono text-xs"
                placeholder="Generate a prompt to preview the AI output."
              />
            </div>
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
                          {index === 0 && (
                            <Badge variant="outline" className="border-primary/40 bg-primary/10 text-primary text-[10px]">
                              latest
                            </Badge>
                          )}
                        </div>
                        <div className="truncate text-[11px] text-muted-foreground">
                          {pkg.template_id ?? "template"} · v{pkg.prompt_version ?? "1"}
                        </div>
                      </div>
                      <Badge variant="outline" className="shrink-0 tabular-nums text-[10px]">
                        {Math.round((pkg.confidence_score ?? 0) * 100)}%
                      </Badge>
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
              <CardTitle className="text-base">Preview</CardTitle>
              <CardDescription>Dry-run the assembled prompt against the active source.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              <Button variant="outline" size="sm" className="w-full gap-1.5">
                <Eye className="h-3.5 w-3.5" /> Open preview
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
