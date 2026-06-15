import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Database, Lock, ServerCog, ShieldCheck, CheckCircle2, ChevronRight } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";

const engines = [
  { id: "postgres", name: "PostgreSQL", desc: "Including Aurora, Supabase, Neon", color: "from-[#336791]/30" },
  { id: "mysql", name: "MySQL", desc: "MySQL 5.7+, MariaDB, PlanetScale", color: "from-[#00758F]/30" },
  { id: "snowflake", name: "Snowflake", desc: "Account · warehouse · role", color: "from-[#29B5E8]/30" },
  { id: "bigquery", name: "BigQuery", desc: "Service account JSON", color: "from-[#669DF6]/30" },
  { id: "redshift", name: "Redshift", desc: "Provisioned and Serverless", color: "from-[#8C4FFF]/30" },
  { id: "databricks", name: "Databricks", desc: "Unity Catalog · SQL warehouse", color: "from-[#FF3621]/30" },
  { id: "sqlserver", name: "SQL Server", desc: "Azure SQL · on-prem", color: "from-[#A91D22]/30" },
  { id: "trino", name: "Trino / Presto", desc: "Catalog-aware", color: "from-[#DD00A1]/30" },
];

export function ConnectPage() {
  const [engine, setEngine] = useState("postgres");
  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Sources" title="Connect a database" description="Add a source to begin metadata sync, governance classification, and AI intelligence generation." />
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1fr_360px]">
        <Card>
          <CardHeader><CardTitle className="text-base">Choose engine</CardTitle><CardDescription>Select the database engine you want to connect.</CardDescription></CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">{engines.map((e) => (<button key={e.id} type="button" onClick={() => setEngine(e.id)} className={cn("relative flex flex-col items-start gap-2 rounded-lg border bg-card p-3 text-left transition hover:border-primary/40", engine === e.id ? "border-primary/60 shadow-[var(--shadow-md)]" : "border-border")}><div className={cn("absolute inset-0 -z-10 rounded-lg bg-gradient-to-br opacity-40 blur-2xl", e.color)} /><div className="grid h-8 w-8 place-items-center rounded-md bg-muted text-muted-foreground"><Database className="h-4 w-4" /></div><div><div className="text-sm font-medium text-foreground">{e.name}</div><div className="text-[11px] text-muted-foreground">{e.desc}</div></div>{engine === e.id && (<CheckCircle2 className="absolute right-2 top-2 h-3.5 w-3.5 text-primary" />)}</button>))}</div>
            <div className="mt-6 space-y-4">
              <Tabs defaultValue="connection"><TabsList><TabsTrigger value="connection">Connection</TabsTrigger><TabsTrigger value="security">Security</TabsTrigger><TabsTrigger value="sync">Sync schedule</TabsTrigger></TabsList>
                <TabsContent value="connection" className="space-y-4 pt-4"><div className="grid grid-cols-1 gap-4 sm:grid-cols-2"><Field label="Display name" placeholder="warehouse_prod" /><Field label="Environment" placeholder="production" /><Field label="Host" placeholder="db.internal.acme.io" /><Field label="Port" placeholder="5432" /><Field label="Database" placeholder="analytics" /><Field label="Username" placeholder="dbcopilot_reader" /><Field label="Password" type="password" placeholder="••••••••" /><Field label="Default schema" placeholder="public" /></div></TabsContent>
                <TabsContent value="security" className="space-y-4 pt-4"><ToggleRow icon={Lock} title="Require SSL/TLS" desc="Enforce encrypted connections to this source." defaultChecked /><ToggleRow icon={ShieldCheck} title="Mask sample values" desc="Redact preview rows for PII-classified columns." defaultChecked /><ToggleRow icon={ServerCog} title="Use private connector" desc="Route traffic through your VPC connector." /></TabsContent>
                <TabsContent value="sync" className="space-y-4 pt-4"><div className="grid grid-cols-1 gap-4 sm:grid-cols-2"><Field label="Sync cadence" placeholder="every 6 hours" /><Field label="Concurrency" placeholder="8" /></div><ToggleRow icon={Database} title="Auto-generate AI packages after sync" desc="Run Governance, Semantics, Relationships, KPI, and Embeddings." defaultChecked /></TabsContent>
              </Tabs>
              <div className="flex flex-wrap items-center justify-end gap-2 border-t border-border pt-4"><Button variant="outline" size="sm">Test connection</Button><Button size="sm" className="gap-1.5 bg-gradient-to-br from-primary to-primary-glow text-primary-foreground">Save and sync <ChevronRight className="h-3.5 w-3.5" /></Button></div>
            </div>
          </CardContent>
        </Card>
        <Card><CardHeader><CardTitle className="text-base">What gets generated</CardTitle><CardDescription>After a successful sync, DBCopilot produces:</CardDescription></CardHeader><CardContent className="space-y-3 text-sm">{["Metadata catalog (schemas, tables, columns, PK/FK, indexes)", "Governance package with PII risk and column semantics", "Semantic package with business domain and glossary", "Relationship clusters and entity graph", "KPI catalog with measures, dimensions, lineage", "Embeddings into Qdrant for retrieval", "Prompt Studio context bundles (RAG, Text-to-SQL, Agent)"].map((t) => (<div key={t} className="flex items-start gap-2 text-muted-foreground"><CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[var(--success)]" /><span>{t}</span></div>))}<div className="rounded-md border border-border bg-muted/30 p-3 text-xs text-muted-foreground"><div className="mb-1 flex items-center gap-1.5 font-medium text-foreground"><Badge variant="outline" className="border-[var(--info)]/40 bg-[var(--info)]/10 text-[var(--info)]">Read-only</Badge></div>DBCopilot only requires read access — no DDL or data modification is ever issued against your source.</div></CardContent></Card>
      </div>
    </div>
  );
}
function Field({ label, ...props }: { label: string } & React.ComponentProps<typeof Input>) { return (<div className="space-y-1.5"><Label className="text-xs font-medium text-muted-foreground">{label}</Label><Input {...props} className="h-9" /></div>); }
function ToggleRow({ icon: Icon, title, desc, defaultChecked }: { icon: typeof Lock; title: string; desc: string; defaultChecked?: boolean }) { return (<div className="flex items-start justify-between gap-4 rounded-lg border border-border bg-card p-3"><div className="flex min-w-0 items-start gap-3"><div className="grid h-8 w-8 shrink-0 place-items-center rounded-md bg-muted text-muted-foreground"><Icon className="h-4 w-4" /></div><div className="min-w-0"><div className="text-sm font-medium text-foreground">{title}</div><div className="text-xs text-muted-foreground">{desc}</div></div></div><Switch defaultChecked={defaultChecked} /></div>); }
