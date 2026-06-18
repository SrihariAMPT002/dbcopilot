import { useQuery } from "@tanstack/react-query";
import { ServerCog, Cpu, Boxes, KeyRound, Globe, CheckCircle2, ArrowRight, Sparkles } from "lucide-react";
import { Link } from "@tanstack/react-router";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/empty-state";
import { queryKeys } from "@/lib/query-keys";
import { useConnections } from "@/hooks/useConnections";
import { useEmbeddings } from "@/hooks/useEmbeddings";
import { healthApi } from "@/api/health";

export function SettingsPage() {
  const { data: connections = [] } = useConnections();
  const active = connections.find((c) => c.status === "active") ?? connections[0] ?? null;
  const { data: embeddingStatus } = useEmbeddings(active?.id ?? null);
  const { data: health } = useQuery({ queryKey: queryKeys.health(), queryFn: healthApi.health });
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "";
  const runtimeMode = import.meta.env.MODE;

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Platform"
        title="Settings"
        description="Runtime settings, backend status, AI configuration, and platform context."
        actions={
          <Button asChild variant="outline" size="sm" className="gap-1.5">
            <Link to="/prompt-budgets">
              <Sparkles className="h-3.5 w-3.5" />
              Prompt budgets
            </Link>
          </Button>
        }
      />

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatusTile icon={ServerCog} label="Backend health" value={health?.status ?? "unknown"} hint={health?.version ?? "n/a"} />
        <StatusTile icon={Boxes} label="Qdrant health" value={embeddingStatus?.qdrant_health ? "healthy" : "unavailable"} hint={embeddingStatus?.message ?? "n/a"} />
        <StatusTile icon={Cpu} label="API base URL" value={apiBaseUrl ? "configured" : "unset"} hint={apiBaseUrl || "n/a"} />
        <StatusTile icon={Globe} label="Runtime mode" value={runtimeMode} hint={active?.name ?? "No active source"} />
      </div>

      <section className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardContent className="space-y-4 p-6">
            <Section title="Runtime" desc="Where DBCopilot's backend is hosted and how the platform runs.">
              <Field label="API base URL" defaultValue={apiBaseUrl} mono />
              <Field label="Default workspace" defaultValue="production" />
              <Field label="Concurrency" defaultValue="16" />
            </Section>
            <Section title="Telemetry" desc="Tracing and audit settings for the platform.">
              <ToggleRow title="OpenTelemetry tracing" defaultChecked />
              <ToggleRow title="Persist job logs (30d)" defaultChecked />
              <ToggleRow title="Audit prompt mutations" defaultChecked />
            </Section>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="space-y-4 p-6">
            <Section title="AI configuration" desc="Default models and retrieval infrastructure.">
              <Field label="Governance" defaultValue="gpt-5-nano" />
              <Field label="Semantics" defaultValue="gpt-5-nano" />
              <Field label="Relationships" defaultValue="gpt-5-nano" />
              <Field label="KPI" defaultValue="gpt-5-nano" />
              <Field label="Embeddings" defaultValue="text-embedding-3-large" />
            </Section>
            <Section title="Embeddings" desc="Vector store configuration and security posture.">
              <Field label="Endpoint" defaultValue="qdrant.internal:6333" mono />
              <Field label="Default similarity" defaultValue="cosine" />
              <Field label="HNSW M / ef_construct" defaultValue="32 / 256" />
              <ToggleRow title="Encrypt collections at rest" defaultChecked />
            </Section>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="space-y-4 p-6">
            <Section title="Platform context" desc="Workspace metadata and connected sources visible to the platform.">
              <Field label="Tenant ID" defaultValue="ten_acme_001" mono />
              <Field label="Environment" defaultValue={runtimeMode} />
              <Field label="Region" defaultValue="us-east-1" />
            </Section>
            <Section title="Connected sources" desc="Current database inventory visible to the platform.">
              {connections.length ? (
                connections.slice(0, 5).map((conn) => (
                  <div key={conn.id} className="rounded-md border border-border bg-card p-3 text-sm">
                    <div className="font-medium text-foreground">{conn.name}</div>
                    <div className="text-xs text-muted-foreground">
                      {conn.db_type} · {conn.host}:{conn.port}
                    </div>
                  </div>
                ))
              ) : (
                <EmptyState icon={Globe} title="No connected databases yet" description="Connect and sync a database to view platform context." />
              )}
            </Section>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="space-y-4 p-6">
            <Section title="API tokens" desc="Create scoped tokens for programmatic access. Tokens are write-once; copy them at creation time.">
              <div className="flex items-start gap-3 rounded-md border border-border bg-card p-4">
                <KeyRound className="mt-0.5 h-4 w-4 text-primary" />
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-medium text-foreground">Platform tokens</div>
                  <p className="mt-1 text-xs text-muted-foreground">Tokens are write-once and should be copied at creation time.</p>
                </div>
                <Button size="sm" className="shrink-0">
                  Generate token
                </Button>
              </div>
            </Section>

            <Section title="Prompt budgets" desc="Inspect completion budgets, truncation risk, and prompt quality scores for GPT-5 Nano workloads.">
              <div className="flex items-start justify-between gap-3 rounded-md border border-border bg-card p-4">
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-medium text-foreground">Prompt budget audit</div>
                  <p className="mt-1 text-xs text-muted-foreground">Review prompt budgets and truncation risk for production workloads.</p>
                </div>
                <Button asChild size="sm" className="shrink-0">
                  <Link to="/prompt-budgets">
                    Open audit <ArrowRight className="ml-1 h-3.5 w-3.5" />
                  </Link>
                </Button>
              </div>
            </Section>
          </CardContent>
        </Card>
      </section>
    </div>
  );
}

function StatusTile({ icon: Icon, label, value, hint }: { icon: typeof ServerCog; label: string; value: string; hint: string }) {
  return (
    <Card className="p-4">
      <div className="flex items-center gap-3">
        <div className="grid h-9 w-9 shrink-0 place-items-center rounded-md bg-gradient-to-br from-primary/15 to-primary/0 text-primary">
          <Icon className="h-4 w-4" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-[11px] uppercase tracking-wider text-muted-foreground">{label}</div>
          <div className="flex items-center gap-1.5 text-sm font-medium text-foreground">
            <CheckCircle2 className="h-3.5 w-3.5 text-[var(--success)]" />
            {value}
          </div>
          <div className="truncate text-[11px] text-muted-foreground">{hint}</div>
        </div>
        <Badge variant="outline" className="text-[10px]">
          live
        </Badge>
      </div>
    </Card>
  );
}

function Section({ title, desc, children }: { title: string; desc: string; children: React.ReactNode }) {
  return (
    <section className="space-y-3">
      <div>
        <h3 className="text-sm font-semibold text-foreground">{title}</h3>
        <p className="text-xs text-muted-foreground">{desc}</p>
      </div>
      <div className="space-y-3">{children}</div>
    </section>
  );
}

function Field({ label, defaultValue, mono }: { label: string; defaultValue: string; mono?: boolean }) {
  return (
    <div className="space-y-1.5">
      <Label className="text-xs font-medium text-muted-foreground">{label}</Label>
      <Input defaultValue={defaultValue} className={`h-9 ${mono ? "font-mono text-xs" : ""}`} />
    </div>
  );
}

function ToggleRow({ title, defaultChecked }: { title: string; defaultChecked?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-md border border-border bg-card px-3 py-2.5">
      <span className="text-sm text-foreground">{title}</span>
      <Switch defaultChecked={defaultChecked} />
    </div>
  );
}
