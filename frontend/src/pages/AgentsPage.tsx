import { useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { Bot, History, Search, Sparkles, ArrowRight, Plus } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { ActiveDatabaseBadge } from "@/components/common/ActiveDatabaseBadge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { EmptyState } from "@/components/empty-state";
import { LoadingShell, ErrorShell } from "@/components/state-shells";
import { useDatabaseContext } from "@/context/database-context";
import { useAgentMemoryHistory, useAgentMemorySearch, useAgentMemoryHealth } from "@/hooks/useAgentMemory";
import { AgentMemoryService } from "@/services/agentMemoryService";
import { TraceLink } from "@/components/common/TraceLink";

export function AgentsPage() {
  const { selectedDatabase } = useDatabaseContext();
  const queryClient = useQueryClient();
  const [query, setQuery] = useState("");
  const [selectedHitId, setSelectedHitId] = useState<number | null>(null);
  const [memoryQuery, setMemoryQuery] = useState("");
  const [memoryResponse, setMemoryResponse] = useState("");
  const dbId = selectedDatabase?.database_id ?? null;
  const historyQuery = useAgentMemoryHistory(dbId, 10);
  const searchQuery = useAgentMemorySearch(dbId, query, 5);
  const healthQuery = useAgentMemoryHealth(dbId);
  const { data: history, isLoading: historyLoading, isError: historyError, error: historyErrorValue } = historyQuery;
  const { data: search, isLoading: searchLoading, isError: searchError, error: searchErrorValue } = searchQuery;
  const { data: health } = healthQuery;

  const createMemory = useMutation({
    mutationFn: () =>
      AgentMemoryService.create({
        database_id: dbId ?? 0,
        query_text: memoryQuery,
        response_text: memoryResponse,
        memory_type: "query_history",
        context_json: { source: "agents_page" },
      }),
    onSuccess: async () => {
      setMemoryQuery("");
      setMemoryResponse("");
      await queryClient.invalidateQueries({ queryKey: ["agent-memory-history", dbId ?? "default", 10] });
    },
  });

  const searchResults = useMemo(() => search?.results ?? [], [search]);
  const selectedSearchHit = searchResults.find((item) => item.id === selectedHitId) ?? searchResults[0] ?? null;

  if (historyLoading || searchLoading || healthQuery.isLoading) {
    return (
      <div className="space-y-6">
        <PageHeader eyebrow="AI Surface" title="Agents" description="Query history and long-term memory surfaced from persisted agent interactions." actions={<ActiveDatabaseBadge />} />
        <LoadingShell title="Agent memory loading" description="Loading agent memory and health signals..." />
      </div>
    );
  }

  if (historyError || searchError || healthQuery.isError) {
    const message =
      (historyErrorValue instanceof Error && historyErrorValue.message) ||
      (searchErrorValue instanceof Error && searchErrorValue.message) ||
      (healthQuery.error instanceof Error && healthQuery.error.message) ||
      "Failed to load agent memory.";
    return (
      <div className="space-y-6">
        <PageHeader eyebrow="AI Surface" title="Agents" description="Query history and long-term memory surfaced from persisted agent interactions." actions={<ActiveDatabaseBadge />} />
        <ErrorShell title="Agent memory unavailable" description={message} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="AI Surface"
        title="Agents"
        description="Query history and long-term memory surfaced from persisted agent interactions."
        actions={<ActiveDatabaseBadge />}
      />

      <section className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Create memory</CardTitle>
            <CardDescription>Record a query and response into long-term memory and the memory vector store.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <Input value={memoryQuery} onChange={(e) => setMemoryQuery(e.target.value)} placeholder="Query or question" />
            <Textarea
              value={memoryResponse}
              onChange={(e) => setMemoryResponse(e.target.value)}
              placeholder="Stored answer or assistant response"
              className="min-h-28"
            />
            <Button onClick={() => createMemory.mutate()} disabled={!dbId || !memoryQuery.trim() || createMemory.isPending} className="gap-1.5">
              {createMemory.isPending ? <History className="h-3.5 w-3.5 animate-spin" /> : <Plus className="h-3.5 w-3.5" />}
              Save memory
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Agent memory history</CardTitle>
            <CardDescription>Recent stored interactions for the selected database.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {(history?.results?.length ?? 0) > 0 ? (
              history!.results.slice(0, 5).map((item) => (
                <div key={item.id} className="rounded-md border border-border bg-card p-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="truncate text-sm font-medium text-foreground">{item.query_text}</div>
                      <div className="mt-1 line-clamp-2 text-xs text-muted-foreground">{item.response_text ?? "No response stored."}</div>
                    </div>
                    <Badge variant="outline" className="text-[10px] uppercase">
                      {item.memory_type}
                    </Badge>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-2 text-[11px] text-muted-foreground">
                    <span>Trace: {item.trace_id ?? "n/a"}</span>
                    <span>Tags: {item.tags?.length ? item.tags.join(", ") : "none"}</span>
                    <TraceLink traceId={item.trace_id} label="Open trace" className="text-[11px]" />
                  </div>
                </div>
              ))
            ) : (
              <EmptyState icon={History} title="No agent memory yet" description="Record agent interactions to build reusable memory." />
            )}
          </CardContent>
        </Card>
      </section>

      <section className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Memory health</CardTitle>
            <CardDescription>Row, vector, and search health for long-term memory.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-md border border-border bg-card p-3">
              <div className="text-[11px] uppercase tracking-wider text-muted-foreground">Rows</div>
              <div className="mt-1 text-sm font-medium text-foreground">{health?.memory_rows ?? 0}</div>
            </div>
            <div className="rounded-md border border-border bg-card p-3">
              <div className="text-[11px] uppercase tracking-wider text-muted-foreground">Vectors</div>
              <div className="mt-1 text-sm font-medium text-foreground">{health?.vector_count ?? 0}</div>
            </div>
            <div className="rounded-md border border-border bg-card p-3">
              <div className="text-[11px] uppercase tracking-wider text-muted-foreground">Status</div>
              <div className="mt-1 text-sm font-medium text-foreground">{health?.status ?? "n/a"}</div>
            </div>
          </CardContent>
        </Card>
      </section>

      <section className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Memory search</CardTitle>
            <CardDescription>Search prior agent queries using the memory vector collection.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex gap-2">
              <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Ask a question or search memory..." />
              <Button variant="outline" className="gap-1.5">
                <Search className="h-3.5 w-3.5" /> Search
              </Button>
            </div>
            {searchResults.length ? (
              <div className="space-y-3">
                {searchResults.map((item) => (
                  <button
                    key={`${item.id}-${item.query_text}`}
                    type="button"
                    onClick={() => setSelectedHitId(item.id)}
                    className="w-full rounded-md border border-border bg-card p-3 text-left transition hover:border-primary/40"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="text-sm font-medium text-foreground">{item.query_text}</div>
                      <Badge variant="outline" className="text-[10px] tabular-nums">
                        {Math.round((item.score ?? 0) * 100)}%
                      </Badge>
                    </div>
                    <div className="mt-1 text-xs text-muted-foreground">{item.response_text ?? "No response stored."}</div>
                    <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
                      <Sparkles className="h-3.5 w-3.5" />
                      <span>{item.memory_type}</span>
                      <ArrowRight className="h-3 w-3" />
                      <span>Trace {item.trace_id ?? "n/a"}</span>
                      <TraceLink traceId={item.trace_id} label="Open trace" className="text-primary" />
                    </div>
                  </button>
                ))}
              </div>
            ) : (
              <EmptyState icon={Bot} title="No search results yet" description="Search memory to retrieve past agent interactions." />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Search result detail</CardTitle>
            <CardDescription>Inspect the currently selected memory hit in more detail.</CardDescription>
          </CardHeader>
          <CardContent>
            {selectedSearchHit ? (
              <div className="space-y-3 rounded-md border border-border bg-card p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="text-sm font-semibold text-foreground">{selectedSearchHit.query_text}</div>
                  <Badge variant="outline" className="text-[10px] tabular-nums">
                    {Math.round((selectedSearchHit.score ?? 0) * 100)}%
                  </Badge>
                </div>
                <div className="text-xs text-muted-foreground">{selectedSearchHit.response_text ?? "No response stored."}</div>
                <div className="grid gap-2 text-xs text-muted-foreground sm:grid-cols-2">
                  <div>Memory type: {selectedSearchHit.memory_type}</div>
                  <div>Trace: {selectedSearchHit.trace_id ?? "n/a"}</div>
                </div>
                <div className="flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
                  <span>Stored at: {selectedSearchHit.created_at ?? "n/a"}</span>
                  <TraceLink traceId={selectedSearchHit.trace_id} label="Open trace" />
                </div>
              </div>
            ) : (
              <EmptyState icon={History} title="No memory selected" description="Choose a search result to inspect its details." />
            )}
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
