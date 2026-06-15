import { useState } from "react";
import {
  Search,
  Database,
  ChevronRight,
  ChevronDown,
  KeyRound,
  Link2,
  Type,
  Calendar,
  CircleDot,
  Filter,
} from "lucide-react";

import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { cn } from "@/lib/utils";

const schemas = [
  {
    name: "public",
    tables: [
      { name: "customers", rows: 184_215, columns: 24 },
      { name: "orders", rows: 1_204_881, columns: 18 },
    ],
  },
];

const columns = [
  { name: "id", type: "uuid", pk: true, nullable: false, icon: KeyRound, tag: "PK" },
  { name: "email", type: "varchar(320)", pk: false, nullable: false, icon: Type, tag: "PII" },
];

export function ExplorerPage() {
  const [openSchema, setOpenSchema] = useState<string>("public");
  const [selectedTable, setSelectedTable] = useState<string>("customers");

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Explorer"
        title="Database explorer"
        description="Browse schemas, tables, columns, keys, indexes, and relationships."
        actions={
          <Badge variant="outline" className="gap-1.5 border-border text-[11px]">
            <Database className="h-3 w-3" /> warehouse_prod
          </Badge>
        }
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[320px_minmax(0,1fr)]">
        <Card className="self-start">
          <CardHeader className="pb-3">
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
              <Input placeholder="Search schemas, tables…" className="h-9 pl-9" />
            </div>
          </CardHeader>
          <CardContent className="max-h-[640px] overflow-y-auto pt-0">
            <ul className="space-y-0.5 text-sm">
              {schemas.map((s) => {
                const open = openSchema === s.name;
                return (
                  <li key={s.name}>
                    <button
                      type="button"
                      onClick={() => setOpenSchema(open ? "" : s.name)}
                      className="flex w-full items-center gap-1.5 rounded-md px-2 py-1.5 text-left hover:bg-muted/60"
                    >
                      {open ? (
                        <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
                      ) : (
                        <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
                      )}
                      <span className="font-medium text-foreground">{s.name}</span>
                      <Badge variant="outline" className="ml-auto text-[10px] tabular-nums">
                        {s.tables.length}
                      </Badge>
                    </button>
                    {open && (
                      <ul className="ml-3 mt-0.5 border-l border-border pl-2">
                        {s.tables.map((t) => (
                          <li key={t.name}>
                            <button
                              type="button"
                              onClick={() => setSelectedTable(t.name)}
                              className={cn(
                                "flex w-full items-center justify-between gap-2 rounded-md px-2 py-1 text-left text-xs hover:bg-muted/60",
                                selectedTable === t.name && "bg-primary/10 text-primary",
                              )}
                            >
                              <span className="truncate">{t.name}</span>
                              <span className="shrink-0 tabular-nums text-muted-foreground">
                                {formatNum(t.rows)}
                              </span>
                            </button>
                          </li>
                        ))}
                      </ul>
                    )}
                  </li>
                );
              })}
            </ul>
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader className="flex flex-row items-start justify-between gap-3 space-y-0">
              <div className="min-w-0 space-y-1">
                <CardTitle className="flex items-center gap-2 text-base">
                  <span className="text-muted-foreground">public.</span>
                  {selectedTable}
                </CardTitle>
                <CardDescription>
                  184,215 rows · 24 columns · primary key on{" "}
                  <code className="rounded bg-muted px-1 py-0.5 text-[11px]">id</code>
                </CardDescription>
              </div>
              <Button variant="outline" size="sm" className="gap-1.5">
                <Filter className="h-3.5 w-3.5" /> Filter
              </Button>
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
                        {columns.map((c) => (
                          <TableRow key={c.name}>
                            <TableCell>
                              <div className="flex items-center gap-2">
                                <c.icon className="h-3.5 w-3.5 text-muted-foreground" />
                                <span className="font-mono text-sm">{c.name}</span>
                              </div>
                            </TableCell>
                            <TableCell className="font-mono text-xs text-muted-foreground">
                              {c.type}
                            </TableCell>
                            <TableCell className="text-xs text-muted-foreground">
                              {c.pk && (
                                <Badge
                                  variant="outline"
                                  className="mr-1 border-primary/40 bg-primary/10 text-primary"
                                >
                                  PK
                                </Badge>
                              )}
                              {c.nullable ? "nullable" : "not null"}
                            </TableCell>
                            <TableCell>
                              {c.tag && (
                                <Badge
                                  variant="outline"
                                  className={cn(
                                    "text-[10px]",
                                    c.tag === "PII" &&
                                      "border-[var(--warning)]/40 bg-[var(--warning)]/10 text-[var(--warning)]",
                                    c.tag === "FK" &&
                                      "border-[var(--info)]/40 bg-[var(--info)]/10 text-[var(--info)]",
                                    c.tag === "Measure" &&
                                      "border-[var(--success)]/40 bg-[var(--success)]/10 text-[var(--success)]",
                                    c.tag === "PK" && "border-primary/40 bg-primary/10 text-primary",
                                  )}
                                >
                                  {c.tag}
                                </Badge>
                              )}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                </TabsContent>

                <TabsContent value="indexes" className="pt-4">
                  <Table>
                    <TableHeader>
                      <TableRow className="bg-muted/40 hover:bg-muted/40">
                        <TableHead>Name</TableHead>
                        <TableHead>Columns</TableHead>
                        <TableHead>Type</TableHead>
                        <TableHead>Unique</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {[
                        { name: "customers_pkey", cols: "id", type: "btree", unique: true },
                      ].map((i) => (
                        <TableRow key={i.name}>
                          <TableCell className="font-mono text-sm">{i.name}</TableCell>
                          <TableCell className="font-mono text-xs text-muted-foreground">{i.cols}</TableCell>
                          <TableCell className="text-xs text-muted-foreground">{i.type}</TableCell>
                          <TableCell className="text-xs">{i.unique ? "yes" : "no"}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TabsContent>

                <TabsContent value="relationships" className="space-y-2 pt-4">
                  {[
                    { from: "customers.default_address_id", to: "addresses.id", kind: "FK → 1:1" },
                  ].map((r) => (
                    <div
                      key={r.from}
                      className="flex items-center gap-3 rounded-md border border-border bg-card p-3"
                    >
                      <Link2 className="h-4 w-4 text-[var(--info)]" />
                      <code className="text-xs text-foreground">{r.from}</code>
                      <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
                      <code className="text-xs text-foreground">{r.to}</code>
                      <Badge variant="outline" className="ml-auto text-[10px]">
                        {r.kind}
                      </Badge>
                    </div>
                  ))}
                </TabsContent>

                <TabsContent value="metadata" className="pt-4">
                  <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                    {[
                      ["Owner", "platform-data@acme"],
                      ["Storage", "Snowflake STANDARD"],
                    ].map(([k, v]) => (
                      <div key={k} className="rounded-md border border-border bg-card p-3">
                        <dt className="text-[11px] uppercase tracking-wider text-muted-foreground">
                          {k}
                        </dt>
                        <dd className="mt-1 text-sm text-foreground">{v}</dd>
                      </div>
                    ))}
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

function formatNum(n: number) {
  if (n > 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n > 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
}
