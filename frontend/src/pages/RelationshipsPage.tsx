import { Network, GitBranch, Workflow, Search, Layers, BarChart3, BadgeInfo } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { CoverageBar } from "@/components/coverage-bar";
import { useRelationships } from "@/hooks/useRelationships";
import { useDatabaseContext } from "@/context/database-context";
import { TraceLink } from "@/components/common/TraceLink";

function MetricItem({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-md border border-border bg-muted/20 p-3">
      <div className="text-[11px] uppercase tracking-wide text-muted-foreground">{label}</div>
      <div className="mt-1 text-sm font-medium text-foreground">{value}</div>
    </div>
  );
}

export function RelationshipsPage() {
  const { selectedDatabaseId } = useDatabaseContext();
  const dbId = selectedDatabaseId ?? 1;
  const { data } = useRelationships(dbId);
  const clusters = data?.packages ?? [];
  const selectedCluster = clusters[0];
  const evidence = selectedCluster?.evidence ?? [];
  const graphMetrics = selectedCluster?.graph_metrics ?? {};
  const confidenceDetails = selectedCluster?.confidence_details ?? {};

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Intelligence"
        title="Relationships"
        description="Cluster summaries, graph metrics, evidence, and lifecycle flows from persisted relationship packages."
      />

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-1">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Relationship packages</CardTitle>
            <CardDescription>Hidden relationships, process flows, lifecycle flows, and cluster scoring.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <section className="space-y-2">
              <div className="text-sm font-semibold text-foreground">Hidden relationships</div>
              {clusters.length ? clusters.flatMap((c) => (c.hidden_relationships ?? []).map((r) => ({ cluster_id: c.cluster_id, relationship: r }))).slice(0, 8).map((item: any, i: number) => (
                <div key={`${item.cluster_id}-${i}`} className="flex flex-wrap items-center gap-3 rounded-md border border-border bg-card p-3">
                  <Network className="h-4 w-4 text-primary" />
                  <code className="text-xs text-foreground">{item.relationship.left ?? item.relationship.source ?? "unknown"}</code>
                  <span className="text-xs text-muted-foreground">-&gt;</span>
                  <code className="text-xs text-foreground">{item.relationship.right ?? item.relationship.target ?? "unknown"}</code>
                  <span className="ml-auto text-[11px] text-muted-foreground">{item.relationship.note ?? item.relationship.summary ?? "persisted hidden relationship"}</span>
                </div>
              )) : <div className="text-sm text-muted-foreground">No relationship packages found yet.</div>}
            </section>
            <section className="space-y-2">
              <div className="text-sm font-semibold text-foreground">Process flows</div>
              <div className="text-sm text-muted-foreground">{clusters.length ? (clusters[0].business_process_flows?.map((p: any) => p.summary ?? JSON.stringify(p)) ?? []).join(" | ") : "No process flows available."}</div>
            </section>
            <section className="space-y-2">
              <div className="text-sm font-semibold text-foreground">Lifecycle flows</div>
              <div className="text-sm text-muted-foreground">{clusters.length ? (clusters[0].lifecycle_flows?.map((p: any) => p.summary ?? JSON.stringify(p)) ?? []).join(" | ") : "No lifecycle flows available."}</div>
            </section>
            <section className="space-y-2">
              <div className="text-sm font-semibold text-foreground">Cluster dependencies</div>
              {clusters.length ? <div className="space-y-2">{clusters.slice(0, 5).map((c) => (<div key={c.cluster_id} className="rounded-md border border-border bg-card p-3"><div className="text-sm font-medium text-foreground">{c.cluster_summary ?? c.domain_name ?? c.cluster_id}</div><CoverageBar value={Math.round((c.cluster_confidence ?? 0) * 100)} className="mt-2" /></div>))}</div> : <div className="text-sm text-muted-foreground">No dependencies available.</div>}
            </section>
            <section className="space-y-2">
              <div className="text-sm font-semibold text-foreground">Cluster metrics</div>
              {selectedCluster ? <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4"><MetricItem label="Cluster confidence" value={`${Math.round((selectedCluster.cluster_confidence ?? 0) * 100)}%`} /><MetricItem label="Cluster size" value={selectedCluster.cluster_label ?? selectedCluster.cluster_id} /><MetricItem label="Graph nodes" value={String((graphMetrics as any).node_count ?? 0)} /><MetricItem label="Graph edges" value={String((graphMetrics as any).edge_count ?? 0)} /><MetricItem label="Density" value={String((graphMetrics as any).density ?? 0)} /><MetricItem label="Communities" value={String((graphMetrics as any).community_count ?? 0)} /><MetricItem label="Execution status" value={selectedCluster.analysis_status ?? "unknown"} /><MetricItem label="Confidence source" value={String((confidenceDetails as any).ai_confidence ?? selectedCluster.cluster_confidence ?? 0)} /></div> : <div className="text-sm text-muted-foreground">No cluster metrics available yet.</div>}
            </section>
            <section className="space-y-2">
              <div className="text-sm font-semibold text-foreground">Evidence</div>
              {evidence.length ? evidence.slice(0, 12).map((item: any, index: number) => (<div key={`${item.source ?? "evidence"}-${index}`} className="rounded-md border border-border bg-card p-3"><div className="flex flex-wrap items-center gap-2"><div className="text-sm font-medium text-foreground">{item.source ?? "graph"}</div><Badge variant="outline">{item.metric ?? item.type ?? "evidence"}</Badge></div><pre className="mt-2 overflow-x-auto text-xs text-muted-foreground">{JSON.stringify(item, null, 2)}</pre></div>)) : <div className="text-sm text-muted-foreground">No persisted relationship evidence yet.</div>}
            </section>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Relationship traceability</CardTitle>
          <CardDescription>Cluster confidence, graph metrics, evidence, and confidence details for the selected database.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 lg:grid-cols-2">
          <div className="space-y-3">
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              <MetricItem label="Cluster confidence" value={`${Math.round((selectedCluster?.cluster_confidence ?? 0) * 100)}%`} />
              <MetricItem label="Graph nodes" value={String((graphMetrics as any).node_count ?? 0)} />
              <MetricItem label="Graph edges" value={String((graphMetrics as any).edge_count ?? 0)} />
            </div>
            <div className="space-y-2">
              <div className="text-xs uppercase tracking-wider text-muted-foreground">Evidence payload</div>
              <pre className="max-h-64 overflow-auto rounded-md border border-border bg-muted/20 p-3 text-[11px] leading-5 text-muted-foreground">
                {JSON.stringify(evidence ?? [], null, 2)}
              </pre>
              <div className="mt-2">
                <TraceLink traceId={(confidenceDetails as any)?.trace_id} label="Open trace" className="text-xs" />
              </div>
            </div>
          </div>
          <div className="space-y-3">
            <div className="text-xs uppercase tracking-wider text-muted-foreground">Confidence details</div>
            <pre className="max-h-64 overflow-auto rounded-md border border-border bg-muted/20 p-3 text-[11px] leading-5 text-muted-foreground">
              {JSON.stringify(confidenceDetails ?? {}, null, 2)}
            </pre>
            <div className="text-xs uppercase tracking-wider text-muted-foreground">Lifecycle flows</div>
            <pre className="max-h-48 overflow-auto rounded-md border border-border bg-muted/20 p-3 text-[11px] leading-5 text-muted-foreground">
              {JSON.stringify(selectedCluster?.lifecycle_flows ?? [], null, 2)}
            </pre>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
