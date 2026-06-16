import { useState } from "react";
import { Wand2, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { EmptyState } from "@/components/empty-state";
import { useReranking } from "@/hooks/useReranking";

export function RerankingPanel({ databaseId }: { databaseId: number }) {
  const [query, setQuery] = useState("");
  const { data, isFetching } = useReranking(databaseId, query, 5);
  const results = data?.results ?? [];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Reranking</CardTitle>
        <CardDescription>LLM reranking with traceable scoring and reasoning.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto]">
          <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Query for reranking..." />
          <Button size="sm" disabled={isFetching || !query.trim()} className="gap-1.5">
            {isFetching ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Wand2 className="h-3.5 w-3.5" />}
            Rerank
          </Button>
        </div>
        {results.length ? (
          <div className="space-y-2">
            {results.map((item, index) => (
              <div key={`${item.original.collection}-${index}`} className="rounded-md border border-border bg-card p-3">
                <div className="flex items-center justify-between gap-3">
                  <div className="text-sm font-medium text-foreground">{item.original.table_name || item.original.collection}</div>
                  <div className="text-xs text-muted-foreground">{Math.round(item.final_score * 100)}%</div>
                </div>
                <div className="mt-1 text-xs text-muted-foreground">
                  Original {Math.round(item.original.score * 100)}% · Rerank {Math.round(item.rerank_score * 100)}%
                </div>
                <div className="mt-2 text-sm text-muted-foreground">{item.reasoning}</div>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState icon={Wand2} title="No reranking yet" description="Search a query to compare rerank scores." />
        )}
      </CardContent>
    </Card>
  );
}
