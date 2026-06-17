import { Database, Search, GitBranch, Wand2, History, FileText, Layers3, ArrowRight } from "lucide-react";
import { Link } from "@tanstack/react-router";
import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/empty-state";
import { useDatabaseContext } from "@/context/database-context";
import { useEmbeddings } from "@/hooks/useEmbeddings";
import { useAgentMemoryHistory } from "@/hooks/useAgentMemory";
import { useRetrievalMetrics } from "@/hooks/useRetrievalMetrics";
import { useSemanticCache } from "@/hooks/useSemanticCache";
import { useRetrievalEvaluation } from "@/hooks/useRetrievalEvaluation";
import { TraceLink } from "@/components/common/TraceLink";
import { EmbeddingStats } from "@/components/embeddings/EmbeddingStats";
import { VectorCollections } from "@/components/embeddings/VectorCollections";
import { RetrievalMetrics } from "@/components/embeddings/RetrievalMetrics";
import { AgentMemoryPanel } from "@/components/embeddings/AgentMemoryPanel";
import { CrossDatabaseSearch } from "@/components/embeddings/CrossDatabaseSearch";
import { RetrievalPlayground } from "@/components/embeddings/RetrievalPlayground";
import { RerankingPanel } from "@/components/embeddings/RerankingPanel";
import { GraphExplorer } from "@/components/embeddings/GraphExplorer";

export function EmbeddingsPage() {
  const { selectedDatabase } = useDatabaseContext();
  const dbId = selectedDatabase?.database_id ?? null;
  const { data } = useEmbeddings(dbId);
  const { data: memory } = useAgentMemoryHistory(dbId, 5);
  const { data: metrics } = useRetrievalMetrics(dbId);
  const { data: evaluations } = useRetrievalEvaluation(dbId);
  const { data: cache } = useSemanticCache(dbId);
  const collections = data?.collections ?? [];
  const embeddingCoverage = Math.round(((data?.completed_tables ?? 0) / Math.max(1, data?.indexed_tables ?? 1)) * 100);
  const cacheItems = cache?.caches ?? [];
  const evalItems = evaluations?.evaluations ?? [];
  const memoryItems = memory?.results ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="AI Surface"
        title="Embeddings & retrieval"
        description="Package-driven retrieval assets for search, reranking, graph traversal, memory, cache, and evaluation."
        actions={
          <Badge variant="outline" className="gap-1.5 text-[11px]">
            <span className="h-1.5 w-1.5 rounded-full bg-[var(--success)] shadow-[0_0_6px_var(--success)]" />
            {data?.qdrant_health ? "Qdrant · healthy" : "Qdrant · unavailable"}
          </Badge>
        }
      />

      <EmbeddingStats
        collections={collections.length}
        indexedTables={data?.indexed_tables ?? 0}
        vectorsTotal={data?.vectors_total ?? 0}
        embeddingModel={data?.embedding_model}
        embeddingCoverage={embeddingCoverage}
      />

      <section className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Knowledge layer overview</CardTitle>
            <CardDescription>Embedded knowledge documents and collections built from persisted intelligence packages.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="rounded-md border border-border bg-card p-3">
                <div className="text-[11px] uppercase tracking-wider text-muted-foreground">Database</div>
                <div className="mt-1 text-sm font-medium text-foreground">{data?.database_name ?? "n/a"}</div>
              </div>
              <div className="rounded-md border border-border bg-card p-3">
                <div className="text-[11px] uppercase tracking-wider text-muted-foreground">Indexed docs</div>
                <div className="mt-1 text-sm font-medium text-foreground">{data?.indexed_tables ?? 0}</div>
              </div>
              <div className="rounded-md border border-border bg-card p-3">
                <div className="text-[11px] uppercase tracking-wider text-muted-foreground">Vector collections</div>
                <div className="mt-1 text-sm font-medium text-foreground">{collections.length}</div>
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button asChild variant="outline" size="sm">
                <Link to="/jobs">Open jobs</Link>
              </Button>
              <Button asChild variant="outline" size="sm">
                <Link to="/prompt-studio">Open prompt studio</Link>
              </Button>
            </div>
            <div className="flex flex-wrap gap-2">
              <TraceLink traceId={cacheItems[0]?.trace_id ?? evalItems[0]?.trace_id ?? memoryItems[0]?.trace_id} label="Open trace" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Semantic cache</CardTitle>
            <CardDescription>Cached retrieval responses and query reuse.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
              {cacheItems.length ? (
                cacheItems.slice(0, 5).map((item) => (
                  <div key={item.id} className="rounded-md border border-border bg-card p-3">
                    <div className="text-sm font-medium text-foreground">{item.query_text}</div>
                    <div className="mt-1 text-xs text-muted-foreground">Hits: {item.hit_count} · TTL: {item.ttl_seconds}s</div>
                    <TraceLink traceId={item.trace_id} label="Open trace" className="mt-2 text-[11px]" />
                  </div>
                ))
              ) : (
              <EmptyState icon={Database} title="No semantic cache yet" description="Cached retrieval responses will appear here after reuse." />
            )}
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Vector collections</CardTitle>
            <CardDescription>All vector collections registered for retrieval.</CardDescription>
          </CardHeader>
          <CardContent>
            <VectorCollections collections={collections} healthy={!!data?.qdrant_health} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Retrieval metrics</CardTitle>
            <CardDescription>Documents, logs, and evaluation summaries from the retrieval layer.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <RetrievalMetrics
              totalDocuments={metrics?.total_documents ?? 0}
              logs={metrics?.retrieval_logs ?? 0}
              evaluations={metrics?.retrieval_evaluations ?? 0}
            />
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="rounded-md border border-border bg-card p-3">
                <div className="text-[11px] uppercase tracking-wider text-muted-foreground">Collections</div>
                <div className="mt-1 text-sm font-medium text-foreground">{metrics?.collections?.length ?? 0}</div>
              </div>
              <div className="rounded-md border border-border bg-card p-3">
                <div className="text-[11px] uppercase tracking-wider text-muted-foreground">Logs</div>
                <div className="mt-1 text-sm font-medium text-foreground">{metrics?.retrieval_logs ?? 0}</div>
              </div>
              <div className="rounded-md border border-border bg-card p-3">
                <div className="text-[11px] uppercase tracking-wider text-muted-foreground">Evaluations</div>
                <div className="mt-1 text-sm font-medium text-foreground">{metrics?.retrieval_evaluations ?? 0}</div>
              </div>
            </div>
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <RetrievalPlayground databaseId={dbId} />
        <RerankingPanel databaseId={dbId} />
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <GraphExplorer databaseId={dbId} />
        <AgentMemoryPanel memories={memoryItems} />
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Retrieval evaluation</CardTitle>
            <CardDescription>Quality, coverage, and hallucination-risk signals.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {(evalItems.length ? evalItems : []).slice(0, 3).map((item) => (
              <div key={item.id} className="rounded-md border border-border bg-card p-3">
                <div className="text-sm font-medium text-foreground">{item.query_text}</div>
                <div className="mt-1 text-xs text-muted-foreground">
                  Precision {Math.round(item.precision_score * 100)}% · Recall {Math.round(item.recall_score * 100)}% · Risk {Math.round(item.hallucination_risk * 100)}%
                </div>
                <TraceLink traceId={item.trace_id} label="Open trace" className="mt-2 text-[11px]" />
              </div>
            ))}
            {!evalItems.length ? <EmptyState icon={Search} title="No retrieval evaluations yet" description="Run a search to inspect quality and risk signals." /> : null}
          </CardContent>
        </Card>
        <CrossDatabaseSearch />
      </section>

      <section className="grid gap-4">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Knowledge layer actions</CardTitle>
            <CardDescription>Direct entry points into the most-used retrieval surfaces.</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            <Button asChild variant="outline" size="sm"><Link to="/jobs"><ArrowRight className="mr-1 h-3.5 w-3.5" />Jobs</Link></Button>
            <Button asChild variant="outline" size="sm"><Link to="/readiness"><History className="mr-1 h-3.5 w-3.5" />Readiness</Link></Button>
            <Button asChild variant="outline" size="sm"><Link to="/prompt-studio"><FileText className="mr-1 h-3.5 w-3.5" />Prompt Studio</Link></Button>
            <Button asChild variant="outline" size="sm"><Link to="/semantics"><Layers3 className="mr-1 h-3.5 w-3.5" />Semantics</Link></Button>
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
