import { Network, Workflow, Layers, BarChart3, BadgeInfo, GitBranch } from "lucide-react";
import { useMemo } from "react";
import { useDatabaseContext } from "@/context/database-context";
import { useRelationships } from "@/hooks/useRelationships";
import { PageHeader } from "@/components/page-header";
import { MetricCard } from "@/components/metric-card";
import { TraceLink } from "@/components/common/TraceLink";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { CoverageBar } from "@/components/coverage-bar";
import { Skeleton } from "@/components/ui/skeleton";

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-md border border-border bg-muted/20 p-3">
      <div className="text-[11px] uppercase tracking-wide text-muted-foreground">{label}</div>
      <div className="mt-1 text-sm font-medium text-foreground">{value}</div>
    </div>
  );
}

export function RelationshipsPage() {
  const { selectedDatabase } = useDatabaseContext();
  const dbId = selectedDatabase?.database_id ?? null;
  const { data, isLoading, isError, error, refetch } = useRelationships(dbId);
  const clusters = data?.packages ?? [];
  const selectedCluster = clusters[0];
  const evidence = selectedCluster?.evidence ?? [];
  const graphMetrics = selectedCluster?.graph_metrics ?? {};
  const confidenceDetails = selectedCluster?.confidence_details ?? {};
  const selectedConfidence = selectedCluster?.confidence_score ?? selectedCluster?.cluster_confidence ?? 0;
  const evidenceChips = useMemo(
    () => evidence.flatMap((item: any) => [item.metric, item.type, item.source]).filter(Boolean).slice(0, 12),
    [evidence],
  );
  const graph = useMemo(() => buildRelationshipGraph(clusters), [clusters]);

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Intelligence" title="Relationships" description="Cluster summaries, graph metrics, evidence, and lifecycle flows from persisted relationship packages." />

      {isLoading ? (
        <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <Skeleton className="h-28 rounded-xl" />
          <Skeleton className="h-28 rounded-xl" />
          <Skeleton className="h-28 rounded-xl" />
          <Skeleton className="h-28 rounded-xl" />
        </section>
      ) : isError ? (
        <Card className="border-destructive/30 bg-destructive/5">
          <CardHeader>
            <CardTitle className="text-base text-destructive">Relationship data unavailable</CardTitle>
            <CardDescription>{error instanceof Error ? error.message : "Failed to load relationship intelligence for the selected database."}</CardDescription>
          </CardHeader>
          <CardContent>
            <button type="button" onClick={() => void refetch()} className="rounded-md border border-border bg-background px-3 py-2 text-sm font-medium text-foreground transition hover:border-primary/40">
              Retry load
            </button>
          </CardContent>
        </Card>
      ) : null}

      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Clusters" value={String(clusters.length)} icon={Network} tone="info" />
        <MetricCard label="Graph nodes" value={String((graphMetrics as any).node_count ?? 0)} icon={Layers} tone="success" />
        <MetricCard label="Graph edges" value={String((graphMetrics as any).edge_count ?? 0)} icon={GitBranch} tone="default" />
        <MetricCard label="Cluster confidence" value={`${Math.round(selectedConfidence * 100)}%`} icon={BarChart3} tone="warning" />
      </section>

      <section className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader>
            <CardTitle className="text-base">Relationship packages</CardTitle>
            <CardDescription>Hidden relationships, process flows, lifecycle flows, and cluster scoring.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <section className="space-y-2">
              <div className="text-sm font-semibold text-foreground">Relationship graph</div>
              {graph.nodes.length ? (
                <RelationshipGraphCanvas nodes={graph.nodes} edges={graph.edges} />
              ) : (
                <div className="rounded-md border border-dashed border-border p-3 text-sm text-muted-foreground">
                  No graph nodes available yet.
                </div>
              )}
            </section>
            <section className="space-y-2">
              <div className="text-sm font-semibold text-foreground">Cluster dependencies</div>
              {clusters.length ? (
                <div className="space-y-2">
                  {clusters.slice(0, 5).map((c) => {
                    const clusterConfidence = c.confidence_score ?? c.cluster_confidence ?? 0;
                    return (
                      <div key={c.cluster_id} className="rounded-md border border-border bg-card p-3">
                        <div className="text-sm font-medium text-foreground">{c.cluster_summary ?? c.domain_name ?? c.cluster_id ?? "cluster"}</div>
                        <div className="mt-1 text-xs text-muted-foreground">
                          {c.source_table_name ?? "source"} → {c.target_table_name ?? "target"}
                        </div>
                        <CoverageBar value={Math.round(clusterConfidence * 100)} className="mt-2" />
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="rounded-md border border-dashed border-border p-3 text-sm text-muted-foreground">
                  No relationship packages found yet for this database.
                </div>
              )}
            </section>
            <section className="space-y-2">
              <div className="text-sm font-semibold text-foreground">Hidden relationships</div>
              {clusters.length ? clusters.flatMap((c) => (c.hidden_relationships ?? []).map((r) => ({ cluster_id: c.cluster_id, relationship: r }))).slice(0, 8).map((item: any, i: number) => (
                <div key={`${item.cluster_id}-${i}`} className="flex flex-wrap items-center gap-3 rounded-md border border-border bg-card p-3">
                  <Network className="h-4 w-4 text-primary" />
                  <code className="text-xs text-foreground">{item.relationship.left ?? item.relationship.source ?? item.relationship.from ?? "unknown"}</code>
                  <span className="text-xs text-muted-foreground">-&gt;</span>
                  <code className="text-xs text-foreground">{item.relationship.right ?? item.relationship.target ?? item.relationship.to ?? "unknown"}</code>
                  <span className="ml-auto text-[11px] text-muted-foreground">{item.relationship.note ?? item.relationship.summary ?? item.relationship.description ?? "persisted hidden relationship"}</span>
                </div>
              )) : <div className="rounded-md border border-dashed border-border p-3 text-sm text-muted-foreground">No hidden relationships persisted yet.</div>}
            </section>
            <section className="space-y-2">
              <div className="text-sm font-semibold text-foreground">Lifecycle flows</div>
              <div className="flex flex-wrap gap-2">
                {selectedCluster?.lifecycle_flows?.length ? selectedCluster.lifecycle_flows.slice(0, 8).map((flow: any, index: number) => (
                  <Badge key={`${flow.name ?? index}`} variant="outline" className="text-[10px] uppercase">
                    {flow.summary ?? flow.name ?? "lifecycle flow"}
                  </Badge>
                )) : <div className="rounded-md border border-dashed border-border p-3 text-sm text-muted-foreground">No lifecycle flows available.</div>}
              </div>
            </section>
            {evidence?.length ? (
              <section className="space-y-2">
                <div className="text-sm font-semibold text-foreground">Evidence summary</div>
                <div className="text-sm text-muted-foreground">
                  {evidence.slice(0, 3).map((item: any) => item.summary ?? item.description ?? item.note ?? String(item.source ?? "evidence")).join(" · ")}
                </div>
              </section>
            ) : null}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Relationship evidence</CardTitle>
            <CardDescription>Graph metrics, evidence chips, and confidence details.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-1">
              <Stat label="Cluster size" value={selectedCluster?.cluster_label ?? selectedCluster?.cluster_id ?? "n/a"} />
              <Stat label="Execution status" value={selectedCluster?.analysis_status ?? "unknown"} />
              <Stat label="Confidence source" value={String((confidenceDetails as { ai_confidence?: number } | undefined)?.ai_confidence ?? selectedConfidence)} />
              <Stat label="Communities" value={String((graphMetrics as { community_count?: number } | undefined)?.community_count ?? 0)} />
            </div>
            <div>
              <div className="mb-2 text-xs uppercase tracking-wider text-muted-foreground">Evidence chips</div>
              <div className="flex flex-wrap gap-2">
                {evidenceChips.length ? evidenceChips.map((chip) => (
                  <Badge key={chip} variant="outline" className="text-[10px] uppercase">
                    {chip}
                  </Badge>
                )) : <div className="text-sm text-muted-foreground">No persisted relationship evidence yet.</div>}
              </div>
            </div>
            <div className="rounded-md border border-border bg-muted/20 p-3">
              <div className="text-xs uppercase tracking-wider text-muted-foreground">Trace</div>
              <TraceLink traceId={(confidenceDetails as any)?.trace_id ?? selectedCluster?.trace_id} label="Open trace" className="mt-2 text-xs" />
            </div>
          </CardContent>
        </Card>
      </section>
    </div>
  );
}

type GraphNode = {
  id: string;
  label: string;
  clusterId: string;
  x: number;
  y: number;
};

type GraphEdge = {
  from: string;
  to: string;
};

function buildRelationshipGraph(
  clusters: Array<{
    cluster_id: string;
    cluster_summary?: string | null;
    domain_name?: string | null;
    hidden_relationships?: Array<Record<string, unknown>>;
    entity_graph?: Array<Record<string, unknown>>;
  }>,
): { nodes: GraphNode[]; edges: GraphEdge[] } {
  const nodesByName = new Map<string, GraphNode>();
  const edges: GraphEdge[] = [];

  const addNode = (name: string) => {
    if (!name) return;
    if (!nodesByName.has(name)) {
      nodesByName.set(name, {
        id: name,
        label: name,
        clusterId: "",
        x: 0,
        y: 0,
      });
    }
  };

  clusters.forEach((cluster) => {
    const relationships = [...(cluster.hidden_relationships ?? []), ...(cluster.entity_graph ?? [])];
    relationships.forEach((relationship) => {
      const source = String(relationship.source ?? relationship.from ?? relationship.left ?? relationship.source_table_name ?? relationship.table_name ?? "").trim();
      const target = String(relationship.target ?? relationship.to ?? relationship.right ?? relationship.target_table_name ?? relationship.referenced_table_name ?? "").trim();
      if (source && target) {
        addNode(source);
        addNode(target);
        edges.push({ from: source, to: target });
      }
    });
  });

  if (!nodesByName.size) {
    clusters.slice(0, 8).forEach((cluster) => {
      const label = cluster.cluster_summary ?? cluster.domain_name ?? cluster.cluster_id;
      if (label) addNode(label);
    });
  }

  const nodes = Array.from(nodesByName.values()).slice(0, 12).map((node, index) => ({
    ...node,
    x: 120 + (index % 4) * 180,
    y: 70 + Math.floor(index / 4) * 120,
  }));

  const valid = new Set(nodes.map((node) => node.id));
  return {
    nodes,
    edges: edges.filter((edge) => valid.has(edge.from) && valid.has(edge.to)).slice(0, 20),
  };
}

function RelationshipGraphCanvas({ nodes, edges }: { nodes: GraphNode[]; edges: GraphEdge[] }) {
  return (
    <div className="overflow-hidden rounded-xl border border-border bg-gradient-to-br from-background via-background to-muted/30 p-4">
      <svg viewBox="0 0 900 360" className="h-[320px] w-full">
        <defs>
          <linearGradient id="relationship-node" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="hsl(var(--primary))" stopOpacity="0.95" />
            <stop offset="100%" stopColor="hsl(var(--accent))" stopOpacity="0.75" />
          </linearGradient>
        </defs>
        {edges.map((edge, index) => {
          const source = nodes.find((node) => node.id === edge.from);
          const target = nodes.find((node) => node.id === edge.to);
          if (!source || !target) return null;
          return (
            <line
              key={`${edge.from}-${edge.to}-${index}`}
              x1={source.x}
              y1={source.y}
              x2={target.x}
              y2={target.y}
              stroke="hsl(var(--border))"
              strokeWidth="2"
              strokeDasharray="6 4"
            />
          );
        })}
        {nodes.map((node) => (
          <g key={node.id} transform={`translate(${node.x}, ${node.y})`}>
            <circle r="34" fill="url(#relationship-node)" opacity="0.95" />
            <circle r="38" fill="none" stroke="hsl(var(--border))" strokeWidth="1" opacity="0.9" />
            <text textAnchor="middle" y="-2" className="fill-background text-[10px] font-semibold">
              {node.label.slice(0, 12)}
            </text>
            <text textAnchor="middle" y="12" className="fill-background/80 text-[9px]">
              {node.clusterId.slice(0, 8)}
            </text>
          </g>
        ))}
      </svg>
      <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-muted-foreground">
        {nodes.slice(0, 8).map((node) => (
          <Badge key={node.id} variant="outline" className="text-[10px] uppercase">
            {node.label}
          </Badge>
        ))}
      </div>
    </div>
  );
}
