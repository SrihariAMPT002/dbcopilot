import { TrendingUp, Ruler, Layers3, GitBranch } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { MetricCard } from "@/components/metric-card";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { CoverageBar } from "@/components/coverage-bar";
import { useKPIs } from "@/hooks/useKpis";
import { useDatabaseContext } from "@/context/database-context";

export function KPIPage() {
  const { selectedDatabaseId } = useDatabaseContext();
  const dbId = selectedDatabaseId ?? 1;
  const { data } = useKPIs(dbId);
  const latest = data?.latest ? (Object.entries(data.latest) as Array<[string, unknown]>) : [];

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Intelligence"
        title="KPI catalog"
        description="Measures, dimensions, business rules, and lineage from persisted KPI artifacts."
      />
      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard label="Artifacts" value={String(data?.artifact_count ?? 0)} icon={TrendingUp} tone="info" />
        <MetricCard label="Measures" value={String((data?.latest?.kpi_definitions as any[] | undefined)?.length ?? 0)} icon={Ruler} />
        <MetricCard label="Dimensions" value={String((data?.latest?.kpi_catalog as any[] | undefined)?.length ?? 0)} icon={Layers3} tone="success" />
        <MetricCard label="Lineage items" value={String((data?.latest?.kpi_lineage as any[] | undefined)?.length ?? 0)} icon={GitBranch} progress={Math.min(100, (data?.artifact_count ?? 0) * 10)} tone="success" />
      </section>
      <Card>
        <CardHeader className="flex flex-row items-end justify-between gap-3 space-y-0">
          <div className="space-y-1">
            <CardTitle className="text-base">KPI catalog</CardTitle>
            <CardDescription>All KPI artifacts detected and modeled across the active source.</CardDescription>
          </div>
          <Input placeholder="Search KPIs…" className="h-9 max-w-xs" />
        </CardHeader>
        <CardContent>
          <Tabs defaultValue="catalog">
            <TabsList>
              <TabsTrigger value="catalog">Catalog</TabsTrigger>
              <TabsTrigger value="lineage">Lineage</TabsTrigger>
              <TabsTrigger value="rules">Business rules</TabsTrigger>
            </TabsList>
            <TabsContent value="catalog" className="pt-4">
              {latest.length ? (
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow className="bg-muted/40 hover:bg-muted/40">
                        <TableHead>Artifact</TableHead>
                        <TableHead>Type</TableHead>
                        <TableHead className="text-right">Count</TableHead>
                        <TableHead className="min-w-[180px]">Coverage</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {latest.map(([name, value]) => (
                        <TableRow key={name}>
                          <TableCell className="font-medium text-foreground">{name}</TableCell>
                          <TableCell className="text-sm text-muted-foreground">
                            {Array.isArray(value) ? "array" : typeof value}
                          </TableCell>
                          <TableCell className="text-right tabular-nums">
                            {Array.isArray(value) ? value.length : 1}
                          </TableCell>
                          <TableCell>
                            <CoverageBar value={Array.isArray(value) ? Math.min(100, value.length * 10) : 100} />
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              ) : (
                <div className="text-sm text-muted-foreground">No KPI artifacts available yet.</div>
              )}
            </TabsContent>
            <TabsContent value="lineage" className="pt-4">
              <div className="text-sm text-muted-foreground">
                Lineage is served from persisted KPI artifacts and the relationship package.
              </div>
            </TabsContent>
            <TabsContent value="rules" className="pt-4 text-sm text-muted-foreground">
              Business rules are generated from the persisted KPI package.
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
    </div>
  );
}
