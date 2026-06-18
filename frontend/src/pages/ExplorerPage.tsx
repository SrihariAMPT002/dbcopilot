import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search, Database, Filter, ChevronRight, ChevronDown, Link2, KeyRound, Type, Columns3 } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { EmptyState } from "@/components/empty-state";
import { metadataApi } from "@/api/metadata";
import { useConnections } from "@/hooks/useConnections";
import { useDatabaseContext } from "@/context/database-context";
import { queryKeys } from "@/lib/query-keys";

export function ExplorerPage() {
  const { data: connections = [] } = useConnections();
  const { selectedDatabaseId: selectedDb, setSelectedDatabaseId } = useDatabaseContext();
  const [schemaFilter, setSchemaFilter] = useState("");
  const [tableFilter, setTableFilter] = useState("");
  const [columnFilter, setColumnFilter] = useState("");
  const [selectedSchemaId, setSelectedSchemaId] = useState<number | null>(null);
  const [selectedTableId, setSelectedTableId] = useState<number | null>(null);

  const { data: schemas = [] } = useQuery({
    queryKey: queryKeys.schemas(selectedDb ?? "default"),
    queryFn: () => metadataApi.schemas(Number(selectedDb)),
    enabled: !!selectedDb,
  });
  const { data: tables = [] } = useQuery({
    queryKey: queryKeys.tables(selectedSchemaId ?? "default"),
    queryFn: () => metadataApi.tables(Number(selectedSchemaId)),
    enabled: !!selectedSchemaId,
  });
  const { data: columns = [] } = useQuery({
    queryKey: queryKeys.columns(selectedTableId ?? "default"),
    queryFn: () => metadataApi.columns(Number(selectedTableId)),
    enabled: !!selectedTableId,
  });
  const { data: relationships = [] } = useQuery({
    queryKey: queryKeys.relationshipsByTable(selectedTableId ?? "default"),
    queryFn: () => metadataApi.relationships(Number(selectedTableId)),
    enabled: !!selectedTableId,
  });
  const { data: diag } = useQuery({
    queryKey: queryKeys.diagnose(selectedDb ?? "default"),
    queryFn: () => metadataApi.diagnose(Number(selectedDb)),
    enabled: !!selectedDb,
  });

  const filteredSchemas = useMemo(
    () => schemas.filter((schema) => !schemaFilter || schema.name.toLowerCase().includes(schemaFilter.toLowerCase())),
    [schemaFilter, schemas],
  );
  const filteredTables = useMemo(
    () => tables.filter((table) => !tableFilter || table.name.toLowerCase().includes(tableFilter.toLowerCase())),
    [tableFilter, tables],
  );
  const filteredColumns = useMemo(
    () => columns.filter((column) => !columnFilter || column.name.toLowerCase().includes(columnFilter.toLowerCase())),
    [columnFilter, columns],
  );
  const indexedColumns = useMemo(() => filteredColumns.filter((column) => column.is_indexed), [filteredColumns]);
  const selectedSchema = useMemo(() => schemas.find((schema) => schema.id === selectedSchemaId) ?? null, [schemas, selectedSchemaId]);
  const selectedTable = useMemo(() => tables.find((table) => table.id === selectedTableId) ?? null, [tables, selectedTableId]);

  useEffect(() => {
    if (!selectedDb || !schemas.length) {
      setSelectedSchemaId(null);
      setSelectedTableId(null);
      return;
    }
    if (!selectedSchemaId || !schemas.some((schema) => schema.id === selectedSchemaId)) {
      setSelectedSchemaId(schemas[0].id);
    }
  }, [schemas, selectedDb, selectedSchemaId]);

  useEffect(() => {
    if (!selectedSchemaId || !tables.length) {
      setSelectedTableId(null);
      return;
    }
    if (!selectedTableId || !tables.some((table) => table.id === selectedTableId)) {
      setSelectedTableId(tables[0].id);
    }
  }, [selectedSchemaId, selectedTableId, tables]);

  const selectedDbName = connections.find((connection) => connection.id === selectedDb)?.name ?? "n/a";
  const totalColumns = diag ? `${diag.schemas_count ?? 0} schemas · ${diag.tables_count ?? 0} tables · ${diag.columns_count ?? 0} columns` : "Loading metadata from backend...";

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Explorer"
        title="Database explorer"
        description="Browse schemas, tables, columns, indexes, and relationships with fewer clicks and more inline context."
        actions={<Badge variant="outline" className="gap-1.5 border-border text-[11px]"><Database className="h-3 w-3" /> backend-driven</Badge>}
      />

      <section className="grid gap-4 xl:grid-cols-[340px_minmax(0,1fr)]">
        <Card className="self-start">
          <CardHeader className="space-y-3 pb-3">
            <div className="grid gap-2 sm:grid-cols-3">
              <div className="rounded-md border border-border bg-card p-3">
                <div className="text-[11px] uppercase tracking-wider text-muted-foreground">Schemas</div>
                <div className="mt-1 text-lg font-semibold text-foreground">{schemas.length}</div>
              </div>
              <div className="rounded-md border border-border bg-card p-3">
                <div className="text-[11px] uppercase tracking-wider text-muted-foreground">Tables</div>
                <div className="mt-1 text-lg font-semibold text-foreground">{tables.length}</div>
              </div>
              <div className="rounded-md border border-border bg-card p-3">
                <div className="text-[11px] uppercase tracking-wider text-muted-foreground">Columns</div>
                <div className="mt-1 text-lg font-semibold text-foreground">{columns.length}</div>
              </div>
            </div>
            <div className="space-y-2">
              <div className="relative">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                <Input value={schemaFilter} onChange={(e) => setSchemaFilter(e.target.value)} placeholder="Search schemas..." className="h-9 pl-9" />
              </div>
              <div className="relative">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                <Input value={tableFilter} onChange={(e) => setTableFilter(e.target.value)} placeholder="Search tables..." className="h-9 pl-9" />
              </div>
            </div>
            <div className="flex gap-2 overflow-x-auto pb-1">
              {connections.map((connection) => (
                <Button
                  key={connection.id}
                  variant={selectedDb === connection.id ? "default" : "outline"}
                  size="sm"
                  onClick={() => {
                    setSelectedDatabaseId(connection.id);
                    setSelectedSchemaId(null);
                    setSelectedTableId(null);
                  }}
                >
                  {connection.name}
                </Button>
              ))}
            </div>
          </CardHeader>
          <CardContent className="max-h-[720px] overflow-y-auto pt-0">
            {filteredSchemas.length ? (
              <ul className="space-y-1 text-sm">
                {filteredSchemas.map((schema) => {
                  const open = selectedSchemaId === schema.id;
                  return (
                    <li key={schema.id}>
                      <button
                        type="button"
                        onClick={() => setSelectedSchemaId(open ? null : schema.id)}
                        className="flex w-full items-center gap-1.5 rounded-md px-2 py-1.5 text-left transition hover:bg-muted/60"
                      >
                        {open ? <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" /> : <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />}
                        <span className="font-medium text-foreground">{schema.name}</span>
                        <Badge variant="outline" className="ml-auto text-[10px] tabular-nums">{schema.table_count}</Badge>
                      </button>
                      {open ? (
                        <ul className="ml-3 mt-0.5 border-l border-border pl-2">
                          {(filteredTables.length ? filteredTables : tables).length ? (
                            (filteredTables.length ? filteredTables : tables).map((table) => {
                              const active = selectedTableId === table.id;
                              return (
                                <li key={table.id}>
                                  <button
                                    type="button"
                                    onClick={() => setSelectedTableId(table.id)}
                                    className={`flex w-full items-center justify-between gap-2 rounded-md px-2 py-1 text-left text-xs transition hover:bg-muted/60 ${active ? "bg-muted/60" : ""}`}
                                  >
                                    <span className="truncate">{table.name}</span>
                                    <span className="shrink-0 tabular-nums text-muted-foreground">{table.column_count}</span>
                                  </button>
                                </li>
                              );
                            })
                          ) : (
                            <li className="px-2 py-1 text-xs text-muted-foreground">No tables loaded.</li>
                          )}
                        </ul>
                      ) : null}
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
                <CardTitle className="flex items-center gap-2 text-base">
                  <span className="text-muted-foreground">database.</span> explorer
                </CardTitle>
                <CardDescription>{totalColumns}</CardDescription>
              </div>
              <Button variant="outline" size="sm" className="gap-1.5">
                <Filter className="h-3.5 w-3.5" /> Filter
              </Button>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-3 md:grid-cols-3">
                <div className="rounded-md border border-border bg-muted/20 p-3">
                  <div className="text-[11px] uppercase tracking-wider text-muted-foreground">Selected DB</div>
                  <div className="mt-1 text-sm font-medium text-foreground">{selectedDbName}</div>
                </div>
                <div className="rounded-md border border-border bg-muted/20 p-3">
                  <div className="text-[11px] uppercase tracking-wider text-muted-foreground">Selected Schema</div>
                  <div className="mt-1 text-sm font-medium text-foreground">{selectedSchema?.name ?? "n/a"}</div>
                </div>
                <div className="rounded-md border border-border bg-muted/20 p-3">
                  <div className="text-[11px] uppercase tracking-wider text-muted-foreground">Selected Table</div>
                  <div className="mt-1 text-sm font-medium text-foreground">{selectedTable?.name ?? "n/a"}</div>
                </div>
              </div>

              <section className="space-y-3">
                <div className="flex items-center justify-between gap-2">
                  <div>
                    <div className="text-sm font-semibold text-foreground">Columns</div>
                    <div className="text-xs text-muted-foreground">Filter and inspect PK/FK, nullability, and types.</div>
                  </div>
                  <Badge variant="outline" className="text-[10px]">
                    <Columns3 className="mr-1 h-3 w-3" /> {filteredColumns.length}
                  </Badge>
                </div>
                <div className="space-y-3">
                  <Input value={columnFilter} onChange={(e) => setColumnFilter(e.target.value)} placeholder="Filter columns..." className="h-9 max-w-xs" />
                  <div className="overflow-x-auto">
                    <Table>
                      <TableHeader>
                        <TableRow className="bg-muted/40 hover:bg-muted/40">
                          <TableHead>Column</TableHead>
                          <TableHead>Type</TableHead>
                          <TableHead>Constraints</TableHead>
                          <TableHead>Tag</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {filteredColumns.length ? (
                          filteredColumns.map((column) => (
                            <TableRow key={column.id}>
                              <TableCell>
                                <div className="flex items-center gap-2">
                                  <Type className="h-3.5 w-3.5 text-muted-foreground" />
                                  <span className="font-mono text-sm">{column.name}</span>
                                </div>
                              </TableCell>
                              <TableCell className="font-mono text-xs text-muted-foreground">{column.data_type}</TableCell>
                              <TableCell className="text-xs text-muted-foreground">
                                {column.is_primary_key ? <Badge variant="outline">PK</Badge> : null} {column.is_nullable ? "nullable" : "not null"}
                              </TableCell>
                              <TableCell>
                                {column.is_foreign_key ? <Badge variant="outline">FK</Badge> : column.is_primary_key ? <Badge variant="outline">PK</Badge> : column.is_unique ? <Badge variant="outline">UQ</Badge> : "—"}
                              </TableCell>
                            </TableRow>
                          ))
                        ) : (
                          <TableRow>
                            <TableCell colSpan={4} className="text-sm text-muted-foreground">No columns loaded.</TableCell>
                          </TableRow>
                        )}
                      </TableBody>
                    </Table>
                  </div>
                </div>
              </section>

              <section className="grid gap-4 lg:grid-cols-2">
                <Card className="border-border/70">
                  <CardHeader className="pb-3">
                    <CardTitle className="text-sm">Indexes</CardTitle>
                    <CardDescription>Indexed columns on the selected table.</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    {indexedColumns.length ? (
                      indexedColumns.map((column) => (
                        <div key={column.id} className="flex items-center justify-between rounded-md border border-border bg-card p-3">
                          <div>
                            <div className="text-sm font-medium text-foreground">{column.name}</div>
                            <div className="text-xs text-muted-foreground">{column.data_type}</div>
                          </div>
                          <Badge variant="outline" className="text-[10px]">Indexed</Badge>
                        </div>
                      ))
                    ) : (
                      <EmptyState icon={KeyRound} title="No indexed columns loaded" description="Index information is rendered from the live metadata for the selected table." />
                    )}
                  </CardContent>
                </Card>

                <Card className="border-border/70">
                  <CardHeader className="pb-3">
                    <CardTitle className="text-sm">Relationships</CardTitle>
                    <CardDescription>Foreign key links surfaced directly from metadata.</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    {relationships.length ? (
                      relationships.map((relationship) => (
                        <div key={relationship.id} className="flex items-center gap-3 rounded-md border border-border bg-card p-3">
                          <Link2 className="h-4 w-4 text-[var(--info)]" />
                          <code className="text-xs text-foreground">{relationship.column_name}</code>
                          <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
                          <code className="text-xs text-foreground">{`${relationship.referenced_schema ? `${relationship.referenced_schema}.` : ""}${relationship.referenced_table_name}.${relationship.referenced_column_name}`}</code>
                        </div>
                      ))
                    ) : (
                      <EmptyState icon={Link2} title="No relationships loaded" description="Relationships are rendered from persisted relationship packages." />
                    )}
                  </CardContent>
                </Card>
              </section>
            </CardContent>
          </Card>
        </div>
      </section>
    </div>
  );
}
