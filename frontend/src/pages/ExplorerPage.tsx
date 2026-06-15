import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search, Database, Filter, ChevronRight, ChevronDown, Link2, KeyRound, Type } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { EmptyState } from "@/components/empty-state";
import { metadataApi } from "@/api/metadata";
import { useConnections } from "@/hooks/useConnections";
import { useDatabaseContext } from "@/context/database-context";

export function ExplorerPage() {
  const { data: connections = [] } = useConnections();
  const { selectedDatabaseId: selectedDb, setSelectedDatabaseId } = useDatabaseContext();
  const [schemaFilter, setSchemaFilter] = useState("");
  const [tableFilter, setTableFilter] = useState("");
  const [columnFilter, setColumnFilter] = useState("");
  const [selectedSchemaId, setSelectedSchemaId] = useState<number | null>(null);
  const [selectedTableId, setSelectedTableId] = useState<number | null>(null);

  const { data: schemas = [] } = useQuery({
    queryKey: ["schemas", selectedDb],
    queryFn: () => metadataApi.schemas(Number(selectedDb)),
    enabled: !!selectedDb,
  });
  const { data: tables = [] } = useQuery({
    queryKey: ["tables", selectedSchemaId],
    queryFn: () => metadataApi.tables(Number(selectedSchemaId)),
    enabled: !!selectedSchemaId,
  });
  const { data: columns = [] } = useQuery({
    queryKey: ["columns", selectedTableId],
    queryFn: () => metadataApi.columns(Number(selectedTableId)),
    enabled: !!selectedTableId,
  });
  const { data: relationships = [] } = useQuery({
    queryKey: ["relationships", selectedTableId],
    queryFn: () => metadataApi.relationships(Number(selectedTableId)),
    enabled: !!selectedTableId,
  });
  const { data: diag } = useQuery({
    queryKey: ["diagnose", selectedDb],
    queryFn: () => metadataApi.diagnose(Number(selectedDb)),
    enabled: !!selectedDb,
  });

  const filteredSchemas = useMemo(() => schemas.filter((s) => !schemaFilter || s.name.toLowerCase().includes(schemaFilter.toLowerCase())), [schemaFilter, schemas]);
  const filteredTables = useMemo(() => tables.filter((t) => !tableFilter || t.name.toLowerCase().includes(tableFilter.toLowerCase())), [tableFilter, tables]);
  const filteredColumns = useMemo(() => columns.filter((c) => !columnFilter || c.name.toLowerCase().includes(columnFilter.toLowerCase())), [columnFilter, columns]);

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Explorer" title="Database explorer" description="Browse schemas, tables, columns, keys, indexes, and relationships." actions={<Badge variant="outline" className="gap-1.5 border-border text-[11px]"><Database className="h-3 w-3" /> backend-driven</Badge>} />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[320px_minmax(0,1fr)]">
        <Card className="self-start">
          <CardHeader className="pb-3">
            <div className="space-y-2">
              <div className="relative">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                <Input value={schemaFilter} onChange={(e) => setSchemaFilter(e.target.value)} placeholder="Search schemas, tables…" className="h-9 pl-9" />
              </div>
              <div className="flex gap-2">
                {connections.map((c) => (
                  <Button key={c.id} variant={selectedDb === c.id ? "default" : "outline"} size="sm" onClick={() => { setSelectedDatabaseId(c.id); setSelectedSchemaId(null); setSelectedTableId(null); }}>
                    {c.name}
                  </Button>
                ))}
              </div>
            </div>
          </CardHeader>
          <CardContent className="max-h-[640px] overflow-y-auto pt-0">
            {filteredSchemas.length ? (
              <ul className="space-y-0.5 text-sm">
                {filteredSchemas.map((s) => {
                  const open = selectedSchemaId === s.id;
                  return (
                    <li key={s.id}>
                      <button type="button" onClick={() => setSelectedSchemaId(open ? null : s.id)} className="flex w-full items-center gap-1.5 rounded-md px-2 py-1.5 text-left hover:bg-muted/60">
                        {open ? <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" /> : <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />}
                        <span className="font-medium text-foreground">{s.name}</span>
                        <Badge variant="outline" className="ml-auto text-[10px] tabular-nums">{s.table_count}</Badge>
                      </button>
                      {open && (
                        <ul className="ml-3 mt-0.5 border-l border-border pl-2">
                          {filteredTables.length ? filteredTables.map((t) => (
                            <li key={t.id}>
                              <button type="button" onClick={() => setSelectedTableId(t.id)} className="flex w-full items-center justify-between gap-2 rounded-md px-2 py-1 text-left text-xs hover:bg-muted/60">
                                <span className="truncate">{t.name}</span>
                                <span className="shrink-0 tabular-nums text-muted-foreground">{t.column_count}</span>
                              </button>
                            </li>
                          )) : <li className="px-2 py-1 text-xs text-muted-foreground">No tables loaded.</li>}
                        </ul>
                      )}
                    </li>
                  );
                })}
              </ul>
            ) : (
              <EmptyState icon={Database} title="No metadata tree loaded" description="Schema, table, and column navigation will render from backend metadata responses." />
            )}
          </CardContent>
        </Card>
        <div className="space-y-4">
          <Card>
            <CardHeader className="flex flex-row items-start justify-between gap-3 space-y-0">
              <div className="min-w-0 space-y-1">
                <CardTitle className="flex items-center gap-2 text-base"><span className="text-muted-foreground">database.</span> explorer</CardTitle>
                <CardDescription>{diag ? `${diag.schemas_count ?? 0} schemas · ${diag.tables_count ?? 0} tables · ${diag.columns_count ?? 0} columns` : "Metadata details are shown once backend data is loaded."}</CardDescription>
              </div>
              <Button variant="outline" size="sm" className="gap-1.5"><Filter className="h-3.5 w-3.5" /> Filter</Button>
            </CardHeader>
            <CardContent>
              <Tabs defaultValue="columns">
                <TabsList>
                  <TabsTrigger value="columns">Columns</TabsTrigger>
                  <TabsTrigger value="indexes">Indexes</TabsTrigger>
                  <TabsTrigger value="relationships">Relationships</TabsTrigger>
                  <TabsTrigger value="metadata">Metadata</TabsTrigger>
                </TabsList>
                <TabsContent value="columns" className="pt-4">
                  <div className="space-y-3">
                    <Input value={columnFilter} onChange={(e) => setColumnFilter(e.target.value)} placeholder="Optional field filter..." className="h-9 max-w-xs" />
                    <Table>
                      <TableHeader><TableRow className="bg-muted/40 hover:bg-muted/40"><TableHead>Column</TableHead><TableHead>Type</TableHead><TableHead>Constraints</TableHead><TableHead>Tag</TableHead></TableRow></TableHeader>
                      <TableBody>
                        {filteredColumns.length ? filteredColumns.map((c) => (
                          <TableRow key={c.id}>
                            <TableCell><div className="flex items-center gap-2"><Type className="h-3.5 w-3.5 text-muted-foreground" /><span className="font-mono text-sm">{c.name}</span></div></TableCell>
                            <TableCell className="font-mono text-xs text-muted-foreground">{c.data_type}</TableCell>
                            <TableCell className="text-xs text-muted-foreground">{c.is_primary_key ? <Badge variant="outline">PK</Badge> : null} {c.is_nullable ? "nullable" : "not null"}</TableCell>
                            <TableCell>{c.is_foreign_key ? <Badge variant="outline">FK</Badge> : c.is_primary_key ? <Badge variant="outline">PK</Badge> : c.is_unique ? <Badge variant="outline">UQ</Badge> : "—"}</TableCell>
                          </TableRow>
                        )) : <TableRow><TableCell colSpan={4} className="text-sm text-muted-foreground">No columns loaded.</TableCell></TableRow>}
                      </TableBody>
                    </Table>
                  </div>
                </TabsContent>
                <TabsContent value="indexes" className="pt-4">
                  <EmptyState icon={KeyRound} title="Indexes shown from backend metadata" description="Index information is rendered from the live schema explorer data." />
                </TabsContent>
                <TabsContent value="relationships" className="pt-4 space-y-2">
                  {relationships.length ? relationships.map((r) => (
                    <div key={r.id} className="flex items-center gap-3 rounded-md border border-border bg-card p-3">
                      <Link2 className="h-4 w-4 text-[var(--info)]" />
                      <code className="text-xs text-foreground">{r.column_name}</code>
                      <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
                      <code className="text-xs text-foreground">{`${r.referenced_schema ? `${r.referenced_schema}.` : ""}${r.referenced_table_name}.${r.referenced_column_name}`}</code>
                    </div>
                  )) : <EmptyState icon={Link2} title="No relationships loaded" description="Relationships are rendered from persisted relationship packages." />}
                </TabsContent>
                <TabsContent value="metadata" className="pt-4">
                  <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                    <div className="rounded-md border border-border bg-card p-3"><dt className="text-[11px] uppercase tracking-wider text-muted-foreground">Selected DB</dt><dd className="mt-1 text-sm text-foreground">{connections.find((c) => c.id === selectedDb)?.name ?? "n/a"}</dd></div>
                    <div className="rounded-md border border-border bg-card p-3"><dt className="text-[11px] uppercase tracking-wider text-muted-foreground">Diagnostic</dt><dd className="mt-1 text-sm text-foreground">{String((diag as { recommendation?: unknown } | undefined)?.recommendation ?? "n/a")}</dd></div>
                  </dl>
                </TabsContent>
              </Tabs>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
