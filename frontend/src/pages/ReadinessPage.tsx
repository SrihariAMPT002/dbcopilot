import { Gauge, ShieldCheck, BookOpenText, Network, TrendingUp, Boxes, Sparkles, Bot, History, Lightbulb, ArrowRight } from "lucide-react";
import { Link } from "@tanstack/react-router";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useDatabaseContext } from "@/context/database-context";
import { useReadiness } from "@/hooks/useReadiness";
import { useReadinessHistory } from "@/hooks/useReadinessHistory";
import { useRemediation } from "@/hooks/useRemediation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ReadinessService } from "@/services/readinessService";
import { ReadinessOverview } from "@/components/readiness/ReadinessOverview";
import { DimensionScoreCard } from "@/components/readiness/DimensionScoreCard";
import { RemediationPanel } from "@/components/readiness/RemediationPanel";
import { EmptyState } from "@/components/empty-state";
import { TraceLink } from "@/components/common/TraceLink";

export function ReadinessPage() {
  const queryClient = useQueryClient();
  const { selectedDatabaseId } = useDatabaseContext();
  const dbId = selectedDatabaseId ?? 1;
  const { data } = useReadiness(dbId);
  const { data: history } = useReadinessHistory(dbId);
  const { data: remediation } = useRemediation(dbId);
  const recalcMutation = useMutation({
    mutationFn: () => ReadinessService.recalculate(dbId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["readiness", dbId] });
      await queryClient.invalidateQueries({ queryKey: ["readiness-history", dbId] });
      await queryClient.invalidateQueries({ queryKey: ["remediation", dbId] });
      await queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });

  const categoryScores = data?.category_scores;
  const scores = data?.scores;
  const dimensions = [
    { label: "Governance", score: categoryScores?.governance_readiness_score ?? 0, icon: ShieldCheck },
    { label: "Semantic", score: categoryScores?.semantic_readiness_score ?? 0, icon: BookOpenText },
    { label: "Relationship", score: categoryScores?.relationship_readiness_score ?? 0, icon: Network },
    { label: "Retrieval", score: categoryScores?.ai_context_readiness_score ?? 0, icon: Boxes },
    { label: "Prompt", score: scores?.prompt_score ?? 0, icon: Sparkles },
    { label: "Agent", score: scores?.overall_score ?? 0, icon: Bot },
    { label: "RAG", score: categoryScores?.ai_context_readiness_score ?? 0, icon: Gauge },
    { label: "Text-to-SQL", score: categoryScores?.semantic_readiness_score ?? 0, icon: TrendingUp },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="AI Surface"
        title="AI readiness"
        description="Persisted readiness snapshots, remediation actions, and maturity insights from packages."
        actions={
          <>
            <Button variant="outline" size="sm" onClick={() => recalcMutation.mutate()} disabled={recalcMutation.isPending}>
              <Gauge className={`mr-1 h-3.5 w-3.5 ${recalcMutation.isPending ? "animate-spin" : ""}`} />
              Recalculate
            </Button>
            <Button asChild variant="outline" size="sm">
              <Link to="/jobs">
                <ArrowRight className="mr-1 h-3.5 w-3.5" /> View jobs
              </Link>
            </Button>
          </>
        }
      />

      <ReadinessOverview
        overallScore={scores?.overall_score ?? 0}
        maturityLevel={data?.readiness_status ?? "pending"}
        confidence={data?.ai_confidence ?? 0}
        traceId={history?.snapshots?.[0]?.trace_id ?? null}
      />

      <section className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Readiness snapshot</CardTitle>
            <CardDescription>Latest persisted snapshot from the readiness engine.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm text-muted-foreground">
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-md border border-border bg-card p-3">
                <div className="text-[11px] uppercase tracking-wider text-muted-foreground">Database</div>
                <div className="mt-1 text-sm font-medium text-foreground">{data?.database_name ?? "n/a"}</div>
              </div>
              <div className="rounded-md border border-border bg-card p-3">
                <div className="text-[11px] uppercase tracking-wider text-muted-foreground">Generated at</div>
                <div className="mt-1 text-sm font-medium text-foreground">{data?.generated_at ?? "n/a"}</div>
              </div>
            </div>
            <div className="rounded-md border border-border bg-card p-3">
              <div className="text-[11px] uppercase tracking-wider text-muted-foreground">Top risks</div>
              <div className="mt-1 text-sm text-foreground">{(data?.missing_stages ?? []).join(", ") || "none"}</div>
            </div>
            <div className="rounded-md border border-border bg-card p-3">
              <div className="text-[11px] uppercase tracking-wider text-muted-foreground">Recommendations</div>
              <div className="mt-1 text-sm text-foreground">{(data?.remediation_hints ?? []).length ?? 0}</div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Readiness history</CardTitle>
            <CardDescription>Persisted snapshots over time.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {(history?.snapshots ?? []).length ? (
              history!.snapshots.slice(0, 5).map((item) => (
                <div key={item.id} className="rounded-md border border-border bg-card p-3 text-sm">
                  <div className="flex items-center justify-between gap-2">
                    <div className="font-medium text-foreground">{item.maturity_level}</div>
                    <Badge variant="outline">{item.overall_score}</Badge>
                  </div>
                  <div className="mt-1 text-xs text-muted-foreground">{item.generated_at}</div>
                  <div className="mt-2 text-xs text-muted-foreground">{item.summary ?? "No summary persisted."}</div>
                  <TraceLink traceId={item.trace_id} label="Open trace" className="mt-2 text-[11px]" />
                </div>
              ))
            ) : (
              <EmptyState icon={History} title="No readiness history yet" description="Run recalculation to persist snapshots." />
            )}
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader>
            <CardTitle className="text-base">Readiness dimensions</CardTitle>
            <CardDescription>Scores across governance, semantics, retrieval, prompting, agent context, RAG, and text-to-SQL.</CardDescription>
          </CardHeader>
          <CardContent className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            {dimensions.map((dimension) => (
              <DimensionScoreCard key={dimension.label} label={dimension.label} score={dimension.score} confidence={data?.ai_confidence} />
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Readiness summary</CardTitle>
            <CardDescription>High-level package and system state.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm text-muted-foreground">
            <div className="rounded-md border border-border bg-card p-3">
              <div className="text-[11px] uppercase tracking-wider text-muted-foreground">Overall score</div>
              <div className="mt-1 text-2xl font-semibold text-foreground">{scores?.overall_score ?? 0}</div>
            </div>
            <div className="rounded-md border border-border bg-card p-3">
              <div className="text-[11px] uppercase tracking-wider text-muted-foreground">Confidence</div>
              <div className="mt-1 text-sm font-medium text-foreground">{Math.round((data?.ai_confidence ?? 0) * 100)}%</div>
            </div>
            <div className="rounded-md border border-border bg-card p-3">
              <div className="text-[11px] uppercase tracking-wider text-muted-foreground">Trace</div>
              <div className="mt-1 text-sm font-medium text-foreground">{data?.prompt_id ?? "n/a"}</div>
            </div>
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Readiness focus areas</CardTitle>
            <CardDescription>Current readiness signals broken down into the most visible surfaces.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="rounded-md border border-border bg-card p-3">
              <div className="text-sm font-medium text-foreground">Retrieval readiness</div>
              <div className="mt-1 text-sm text-muted-foreground">Coverage and retrieval quality are consumed from persisted metrics and snapshots.</div>
              <div className="mt-2 text-sm">Current score: {categoryScores?.ai_context_readiness_score ?? 0}</div>
            </div>
            <div className="rounded-md border border-border bg-card p-3">
              <div className="text-sm font-medium text-foreground">Agent readiness</div>
              <div className="mt-1 text-sm text-muted-foreground">Agent readiness is derived from governance, semantic, retrieval, prompt, and memory signals.</div>
            </div>
            <div className="rounded-md border border-border bg-card p-3">
              <div className="text-sm font-medium text-foreground">Text-to-SQL readiness</div>
              <div className="mt-1 text-sm text-muted-foreground">Text-to-SQL readiness is based on schema, relationships, glossary, and prompt quality.</div>
            </div>
            <div className="rounded-md border border-border bg-card p-3">
              <div className="text-sm font-medium text-foreground">RAG readiness</div>
              <div className="mt-1 text-sm text-muted-foreground">RAG readiness is derived from retrieval quality, cache behavior, and graph coverage.</div>
            </div>
          </CardContent>
        </Card>

        <RemediationPanel remediations={remediation?.remediations ?? []} />
      </section>
    </div>
  );
}
