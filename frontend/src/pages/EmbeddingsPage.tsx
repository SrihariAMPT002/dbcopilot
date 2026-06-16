import { Database } from "lucide-react";
import { Link } from "@tanstack/react-router";
import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/empty-state";
import { useDatabaseContext } from "@/context/database-context";
import { useEmbeddings } from "@/hooks/useEmbeddings";
import { useAgentMemoryHistory } from "@/hooks/useAgentMemory";
import { useRetrievalMetrics } from "@/hooks/useRetrievalMetrics";
import { useSemanticCache } from "@/hooks/useSemanticCache";
import { useRetrievalEvaluation } from "@/hooks/useRetrievalEvaluation";
import { EmbeddingStats } from "@/components/embeddings/EmbeddingStats";
import { VectorCollections } from "@/components/embeddings/VectorCollections";
import { RetrievalMetrics } from "@/components/embeddings/RetrievalMetrics";
import { AgentMemoryPanel } from "@/components/embeddings/AgentMemoryPanel";
import { CrossDatabaseSearch } from "@/components/embeddings/CrossDatabaseSearch";
import { RetrievalPlayground } from "@/components/embeddings/RetrievalPlayground";
import { RerankingPanel } from "@/components/embeddings/RerankingPanel";
import { GraphExplorer } from "@/components/embeddings/GraphExplorer";

export function EmbeddingsPage() {
  const { selectedDatabaseId } = useDatabaseContext();
  const dbId = selectedDatabaseId ?? 1;
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
        description="Documents, collections, search, reranking, memory, cache, and evaluation across persisted intelligence packages."
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

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Knowledge layer overview</CardTitle>
          <CardDescription>Package-driven retrieval assets for RAG, prompt studio, agents, readiness, and text-to-SQL.</CardDescription>
        </CardHeader>
        <CardContent>
          <Tabs defaultValue="documents">
            <TabsList className="flex-wrap">
              <TabsTrigger value="documents">Documents</TabsTrigger>
              <TabsTrigger value="collections">Collections</TabsTrigger>
              <TabsTrigger value="search">Search</TabsTrigger>
              <TabsTrigger value="rerank">Reranking</TabsTrigger>
              <TabsTrigger value="graph">Graph</TabsTrigger>
              <TabsTrigger value="memory">Agent Memory</TabsTrigger>
              <TabsTrigger value="cache">Cache</TabsTrigger>
              <TabsTrigger value="evaluation">Evaluation</TabsTrigger>
              <TabsTrigger value="cross-db">Cross DB</TabsTrigger>
            </TabsList>
            <div className="mt-3 flex flex-wrap gap-2">
              <Button asChild variant="outline" size="sm">
                <Link to="/embeddings">Open knowledge layer</Link>
              </Button>
              <Button asChild variant="outline" size="sm">
                <Link to="/jobs">Open jobs</Link>
              </Button>
            </div>

            <TabsContent value="documents" className="pt-4">
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Knowledge documents</CardTitle>
                  <CardDescription>Normalized embedding documents built from persisted intelligence packages.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-2 text-sm text-muted-foreground">
                  <div>Database: {data?.database_name ?? "n/a"}</div>
                  <div>Documents indexed: {data?.indexed_tables ?? 0}</div>
                  <div>Vector collections: {collections.length}</div>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="collections" className="pt-4">
              <VectorCollections collections={collections} healthy={!!data?.qdrant_health} />
            </TabsContent>

            <TabsContent value="search" className="pt-4">
              <RetrievalPlayground databaseId={dbId} />
            </TabsContent>

            <TabsContent value="rerank" className="pt-4">
              <RerankingPanel databaseId={dbId} />
            </TabsContent>

            <TabsContent value="graph" className="pt-4">
              <GraphExplorer databaseId={dbId} />
            </TabsContent>

            <TabsContent value="memory" className="pt-4">
              <AgentMemoryPanel memories={memoryItems} />
            </TabsContent>

            <TabsContent value="cache" className="pt-4">
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
                      </div>
                    ))
                  ) : (
                    <EmptyState icon={Database} title="No semantic cache yet" description="Cached retrieval responses will appear here after reuse." />
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="evaluation" className="pt-4">
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Retrieval evaluation</CardTitle>
                  <CardDescription>Quality, coverage, and hallucination-risk signals.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  <RetrievalMetrics
                    totalDocuments={metrics?.total_documents ?? 0}
                    logs={metrics?.retrieval_logs ?? 0}
                    evaluations={metrics?.retrieval_evaluations ?? 0}
                  />
                  {(evalItems.length ? evalItems : []).slice(0, 3).map((item) => (
                    <div key={item.id} className="rounded-md border border-border bg-card p-3">
                      <div className="text-sm font-medium text-foreground">{item.query_text}</div>
                      <div className="mt-1 text-xs text-muted-foreground">
                        Precision {Math.round(item.precision_score * 100)}% · Recall {Math.round(item.recall_score * 100)}% · Risk {Math.round(item.hallucination_risk * 100)}%
                      </div>
                    </div>
                  ))}
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="cross-db" className="pt-4">
              <CrossDatabaseSearch />
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Embedding collections</CardTitle>
          <CardDescription>All vector collections registered for retrieval.</CardDescription>
        </CardHeader>
        <CardContent>
          <VectorCollections collections={collections} healthy={!!data?.qdrant_health} />
        </CardContent>
      </Card>
    </div>
  );
}
