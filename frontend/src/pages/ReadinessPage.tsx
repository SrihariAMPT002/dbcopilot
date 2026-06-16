import { Gauge, ShieldCheck, BookOpenText, Network, TrendingUp, Boxes, Sparkles, Bot, Lightbulb, History } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { useDatabaseContext } from "@/context/database-context";
import { useReadiness } from "@/hooks/useReadiness";
import { useReadinessHistory } from "@/hooks/useReadinessHistory";
import { useRemediation } from "@/hooks/useRemediation";
import { ReadinessOverview } from "@/components/readiness/ReadinessOverview";
import { DimensionScoreCard } from "@/components/readiness/DimensionScoreCard";
import { RemediationPanel } from "@/components/readiness/RemediationPanel";
import { EmptyState } from "@/components/empty-state";

export function ReadinessPage() {
  const { selectedDatabaseId } = useDatabaseContext();
  const dbId = selectedDatabaseId ?? 1;
  const { data } = useReadiness(dbId);
  const { data: history } = useReadinessHistory(dbId);
  const { data: remediation } = useRemediation(dbId);

  const dimensions = [
    { label: "Governance", score: data?.category_scores.governance_readiness_score ?? 0, icon: ShieldCheck },
    { label: "Semantic", score: data?.category_scores.semantic_readiness_score ?? 0, icon: BookOpenText },
    { label: "Relationship", score: data?.category_scores.relationship_readiness_score ?? 0, icon: Network },
    { label: "Retrieval", score: data?.category_scores.ai_context_readiness_score ?? 0, icon: Boxes },
    { label: "Prompt", score: data?.scores.prompt_score ?? 0, icon: Sparkles },
    { label: "Agent", score: data?.scores.overall_score ?? 0, icon: Bot },
    { label: "RAG", score: data?.category_scores.ai_context_readiness_score ?? 0, icon: Gauge },
    { label: "Text-to-SQL", score: data?.category_scores.semantic_readiness_score ?? 0, icon: TrendingUp },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="AI Surface"
        title="AI readiness"
        description="Persisted readiness snapshots, remediation actions, and maturity insights from packages."
      />
      <ReadinessOverview
        overallScore={data?.scores.overall_score ?? 0}
        maturityLevel={data?.readiness_status ?? "pending"}
        confidence={data?.ai_confidence ?? 0}
        traceId={data?.prompt_id ?? null}
      />
      <Tabs defaultValue="overview">
        <TabsList className="flex-wrap">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="dimensions">Dimensions</TabsTrigger>
          <TabsTrigger value="retrieval">Retrieval</TabsTrigger>
          <TabsTrigger value="agents">Agents</TabsTrigger>
          <TabsTrigger value="text-to-sql">Text-to-SQL</TabsTrigger>
          <TabsTrigger value="rag">RAG</TabsTrigger>
          <TabsTrigger value="remediation">Remediation</TabsTrigger>
          <TabsTrigger value="history">History</TabsTrigger>
        </TabsList>
        <TabsContent value="overview" className="pt-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Readiness snapshot</CardTitle>
              <CardDescription>Latest persisted snapshot from the readiness engine.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-sm text-muted-foreground">
              <div>Database: {data?.database_name ?? "n/a"}</div>
              <div>Generated at: {data?.generated_at ?? "n/a"}</div>
              <div>Top risks: {(data?.missing_stages ?? []).join(", ") || "none"}</div>
              <div>Recommendations: {(data?.remediation_hints ?? []).length ?? 0}</div>
            </CardContent>
          </Card>
        </TabsContent>
        <TabsContent value="dimensions" className="pt-4">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            {dimensions.map((dimension) => (
              <DimensionScoreCard key={dimension.label} label={dimension.label} score={dimension.score} confidence={data?.ai_confidence} />
            ))}
          </div>
        </TabsContent>
        <TabsContent value="retrieval" className="pt-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Retrieval readiness</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="text-sm text-muted-foreground">Coverage and retrieval quality are consumed from persisted metrics and snapshots.</div>
              <div className="text-sm">Current score: {data?.category_scores.ai_context_readiness_score ?? 0}</div>
            </CardContent>
          </Card>
        </TabsContent>
        <TabsContent value="agents" className="pt-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Agent readiness</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              Agent readiness is derived from governance, semantic, retrieval, prompt, and memory signals.
            </CardContent>
          </Card>
        </TabsContent>
        <TabsContent value="text-to-sql" className="pt-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Text-to-SQL readiness</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              Text-to-SQL readiness is based on schema, relationships, glossary, and prompt quality.
            </CardContent>
          </Card>
        </TabsContent>
        <TabsContent value="rag" className="pt-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">RAG readiness</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              RAG readiness is derived from retrieval quality, cache behavior, and graph coverage.
            </CardContent>
          </Card>
        </TabsContent>
        <TabsContent value="remediation" className="pt-4">
          <RemediationPanel remediations={remediation?.remediations ?? []} />
        </TabsContent>
        <TabsContent value="history" className="pt-4">
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
                  </div>
                ))
              ) : (
                <EmptyState icon={History} title="No readiness history yet" description="Run recalculation to persist snapshots." />
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
