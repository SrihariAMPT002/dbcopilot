import { useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, ChevronRight, Database, Lock } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/empty-state";
import { connectionsApi } from "@/api/connections";
import type { ConnectionRequest, TestConnectionResponse } from "@/types/backend";
import { cn } from "@/lib/utils";

const dbDefaults = {
  PostgreSQL: { port: 5432, type: "postgresql", allowPortEdit: true },
  MySQL: { port: 3306, type: "mysql", allowPortEdit: true },
  "SQL Server": { port: 1433, type: "sqlserver", allowPortEdit: true },
  Oracle: { port: 1521, type: "oracle", allowPortEdit: true },
  MongoDB: { port: 27017, type: "mongodb", allowPortEdit: true },
  MariaDB: { port: 3306, type: "mariadb", allowPortEdit: true },
  SQLite: { port: 0, type: "sqlite", allowPortEdit: false },
} as const;

export function ConnectPage() {
  const queryClient = useQueryClient();
  const [dbLabel, setDbLabel] = useState<keyof typeof dbDefaults>("PostgreSQL");
  const [form, setForm] = useState<{
    name: string;
    host: string;
    database_name: string;
    username: string;
    password: string;
    ssl_enabled: boolean;
    port: number;
  }>({
    name: "",
    host: "",
    database_name: "",
    username: "",
    password: "",
    ssl_enabled: false,
    port: dbDefaults.PostgreSQL.port,
  });
  const [testResult, setTestResult] = useState<TestConnectionResponse | null>(null);
  const [message, setMessage] = useState<string>("");
  const dbMeta = dbDefaults[dbLabel];

  const payload: ConnectionRequest = useMemo(
    () => ({
      name: form.name,
      db_type: dbMeta.type,
      host: form.host,
      port: form.port,
      database_name: form.database_name,
      username: form.username,
      password: form.password,
      ssl_enabled: form.ssl_enabled,
    }),
    [dbMeta.type, form],
  );

  const testMutation = useMutation({
    mutationFn: () => connectionsApi.test(payload),
    onSuccess: (data) => setTestResult(data as TestConnectionResponse),
    onError: (error) => setMessage(error instanceof Error ? error.message : "Connection test failed"),
  });

  const connectMutation = useMutation({
    mutationFn: async () => {
      const created = await connectionsApi.create(payload);
      await connectionsApi.sync((created as { id: number }).id);
      return created;
    },
    onSuccess: async () => {
      setMessage("Connection registered and schema sync queued.");
      await queryClient.invalidateQueries({ queryKey: ["connections"] });
    },
    onError: (error) => setMessage(error instanceof Error ? error.message : "Connect & sync failed"),
  });

  const engines = [
    { id: "PostgreSQL", desc: "Including Aurora, Supabase, Neon" },
    { id: "MySQL", desc: "MySQL 5.7+, PlanetScale" },
    { id: "SQL Server", desc: "Azure SQL and on-prem" },
    { id: "Oracle", desc: "Oracle Database and compatible services" },
    { id: "MongoDB", desc: "NoSQL collections and inferred fields" },
    { id: "MariaDB", desc: "MariaDB and compatible services" },
    { id: "SQLite", desc: "Embedded local database files" },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Sources"
        title="Connect a database"
        description="Add a source to begin metadata sync, governance classification, and AI intelligence generation."
      />
      <section className="grid gap-4 xl:grid-cols-[1fr_360px]">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Choose engine</CardTitle>
            <CardDescription>Select the database engine you want to connect.</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
              {engines.map((e) => (
                <button
                  key={e.id}
                  type="button"
                  onClick={() => {
                    const next = e.id as keyof typeof dbDefaults;
                    setDbLabel(next);
                    setForm((p) => ({ ...p, port: dbDefaults[next].port }));
                  }}
                  className={cn(
                    "relative flex flex-col items-start gap-2 rounded-lg border bg-card p-3 text-left transition hover:border-primary/40",
                    dbLabel === e.id ? "border-primary/60 shadow-[var(--shadow-md)]" : "border-border",
                  )}
                >
                  <div className="grid h-8 w-8 place-items-center rounded-md bg-muted text-muted-foreground">
                    <Database className="h-4 w-4" />
                  </div>
                  <div>
                    <div className="text-sm font-medium text-foreground">{e.id}</div>
                    <div className="text-[11px] text-muted-foreground">{e.desc}</div>
                  </div>
                  {dbLabel === e.id ? <CheckCircle2 className="absolute right-2 top-2 h-3.5 w-3.5 text-primary" /> : null}
                </button>
              ))}
            </div>

            <div className="mt-6 space-y-4">
              <section className="space-y-3">
                <div className="text-sm font-semibold text-foreground">Connection</div>
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <Field label="Connection Name" value={form.name} onChange={(v) => setForm((p) => ({ ...p, name: v }))} placeholder="production-analytics" />
                  <Field label="Host" value={form.host} onChange={(v) => setForm((p) => ({ ...p, host: v }))} placeholder="localhost or IP" />
                  <Field label="Database Name" value={form.database_name} onChange={(v) => setForm((p) => ({ ...p, database_name: v }))} placeholder="my_database" />
                  <Field label="Username" value={form.username} onChange={(v) => setForm((p) => ({ ...p, username: v }))} placeholder="db_user" />
                  <Field label="Password" value={form.password} onChange={(v) => setForm((p) => ({ ...p, password: v }))} placeholder="••••••••" type="password" />
                  <div className="space-y-1.5">
                    <Label className="text-xs font-medium text-muted-foreground">Port</Label>
                    <Input value={form.port} onChange={(e) => setForm((p) => ({ ...p, port: Number(e.target.value) || 0 }))} disabled={!dbMeta.allowPortEdit} className="h-9" />
                  </div>
                </div>
              </section>

              <section className="space-y-3">
                <div className="text-sm font-semibold text-foreground">Security</div>
                <ToggleRow title="Enable SSL/TLS" desc="Use encrypted transport if the database supports it." checked={form.ssl_enabled} onCheckedChange={(checked) => setForm((p) => ({ ...p, ssl_enabled: checked }))} />
                <ToggleRow title="Mask sample values" desc="Redact preview rows for PII-classified columns." checked />
                <ToggleRow title="Use private connector" desc="Route traffic through your VPC connector." checked={false} />
              </section>

              <section className="space-y-3">
                <div className="text-sm font-semibold text-foreground">Sync schedule</div>
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <Field label="Sync cadence" value="" onChange={() => {}} placeholder="every 6 hours" />
                  <Field label="Concurrency" value="" onChange={() => {}} placeholder="8" />
                </div>
                <ToggleRow title="Auto-generate AI packages after sync" desc="Run Governance, Semantics, Relationships, KPI, and Embeddings." checked />
              </section>

              <div className="flex flex-wrap items-center justify-end gap-2 border-t border-border pt-4">
                <Button variant="outline" size="sm" onClick={() => testMutation.mutate()} disabled={testMutation.isPending}>
                  Test Connection
                </Button>
                <Button size="sm" className="gap-1.5 bg-gradient-to-br from-primary to-primary-glow text-primary-foreground" onClick={() => connectMutation.mutate()} disabled={connectMutation.isPending}>
                  Connect & Sync <ChevronRight className="h-3.5 w-3.5" />
                </Button>
              </div>
              {message ? <div className="text-sm text-muted-foreground">{message}</div> : null}
              {testResult ? (
                <Card className="border-[var(--success)]/30 bg-[var(--success)]/5">
                  <CardContent className="p-4 text-sm">
                    <div className="font-medium text-foreground">{testResult.success ? "Connection successful" : "Connection failed"}</div>
                    <div className="text-muted-foreground">{testResult.message}</div>
                    <div className="mt-2 grid grid-cols-3 gap-2 text-xs">
                      <span>Latency: {testResult.latency_ms ?? "n/a"} ms</span>
                      <span>Version: {testResult.server_version ?? "n/a"}</span>
                      <span>Accessible DBs: {testResult.databases_accessible ?? "n/a"}</span>
                    </div>
                  </CardContent>
                </Card>
              ) : null}
            </div>
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">What gets generated</CardTitle>
              <CardDescription>After a successful sync, DBCopilot produces:</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              {[
                "Metadata catalog (schemas, tables, columns, PK/FK, indexes)",
                "Governance package with PII risk and column semantics",
                "Semantic package with business domain and glossary",
                "Relationship clusters and entity graph",
                "KPI catalog with measures, dimensions, lineage",
                "Embeddings into Qdrant for retrieval",
                "Prompt Studio context bundles (RAG, Text-to-SQL, Agent)",
              ].map((t) => (
                <div key={t} className="flex items-start gap-2 text-muted-foreground">
                  <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[var(--success)]" />
                  <span>{t}</span>
                </div>
              ))}
              <div className="rounded-md border border-border bg-muted/30 p-3 text-xs text-muted-foreground">
                <div className="mb-1 flex items-center gap-1.5 font-medium text-foreground">
                  <Badge variant="outline" className="border-[var(--info)]/40 bg-[var(--info)]/10 text-[var(--info)]">
                    Read-only
                  </Badge>
                </div>
                DBCopilot only requires read access - no DDL or data modification is ever issued against your source.
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Why it matters</CardTitle>
              <CardDescription>Set up a source once, then let the package-first pipeline run automatically.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-sm text-muted-foreground">
              <div className="rounded-md border border-border bg-card p-3">
                <div className="text-sm font-medium text-foreground">Schema discovery</div>
                <div className="mt-1">The explorer, governance, semantics, and downstream intelligence modules all consume the same source.</div>
              </div>
              <div className="rounded-md border border-border bg-card p-3">
                <div className="text-sm font-medium text-foreground">AI package generation</div>
                <div className="mt-1">Governance, semantics, relationships, KPI, prompts, embeddings, and readiness are all triggered from sync.</div>
              </div>
            </CardContent>
          </Card>
        </div>
      </section>
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  placeholder,
  type = "text",
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  type?: React.ComponentProps<typeof Input>["type"];
}) {
  return (
    <div className="space-y-1.5">
      <Label className="text-xs font-medium text-muted-foreground">{label}</Label>
      <Input value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} type={type} className="h-9" />
    </div>
  );
}

function ToggleRow({
  title,
  desc,
  checked,
  onCheckedChange,
}: {
  title: string;
  desc: string;
  checked: boolean;
  onCheckedChange?: (checked: boolean) => void;
}) {
  return (
    <div className="flex items-start justify-between gap-4 rounded-lg border border-border bg-card p-3">
      <div className="flex min-w-0 items-start gap-3">
        <div className="grid h-8 w-8 shrink-0 place-items-center rounded-md bg-muted text-muted-foreground">
          <Lock className="h-4 w-4" />
        </div>
        <div className="min-w-0">
          <div className="text-sm font-medium text-foreground">{title}</div>
          <div className="text-xs text-muted-foreground">{desc}</div>
        </div>
      </div>
      <Switch checked={checked} onCheckedChange={onCheckedChange} />
    </div>
  );
}
