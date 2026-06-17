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
  const { data } = useRelationships(dbId);
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

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Intelligence" title="Relationships" description="Cluster summaries, graph metrics, evidence, and lifecycle flows from persisted relationship packages." />
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
                <div className="text-sm text-muted-foreground">No dependencies available.</div>
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
              )) : <div className="text-sm text-muted-foreground">No relationship packages found yet.</div>}
            </section>
            <section className="space-y-2">
              <div className="text-sm font-semibold text-foreground">Lifecycle flows</div>
              <div className="flex flex-wrap gap-2">
                {selectedCluster?.lifecycle_flows?.length ? selectedCluster.lifecycle_flows.slice(0, 8).map((flow: any, index: number) => (
                  <Badge key={`${flow.name ?? index}`} variant="outline" className="text-[10px] uppercase">
                    {flow.summary ?? flow.name ?? "lifecycle flow"}
                  </Badge>
                )) : <div className="text-sm text-muted-foreground">No lifecycle flows available.</div>}
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
