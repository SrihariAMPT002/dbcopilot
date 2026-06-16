import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { CoverageBar } from "@/components/coverage-bar";
import { StatusBadge, type StatusKind } from "@/components/status-badge";

export function VectorCollections({
  collections,
  healthy,
}: {
  collections: Array<{
    collection_name: string;
    vectors: number;
    indexed_tables?: number;
    last_indexed_at?: string | null;
  }>;
  healthy: boolean;
}) {
  return (
    <div className="overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow className="bg-muted/40 hover:bg-muted/40">
            <TableHead>Collection</TableHead>
            <TableHead className="text-right">Vectors</TableHead>
            <TableHead className="text-right">Indexed tables</TableHead>
            <TableHead className="min-w-[160px]">Coverage</TableHead>
            <TableHead>Status</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {collections.length ? (
            collections.map((c) => (
              <TableRow key={c.collection_name}>
                <TableCell className="font-mono text-sm">{c.collection_name}</TableCell>
                <TableCell className="text-right tabular-nums">{c.vectors.toLocaleString()}</TableCell>
                <TableCell className="text-right tabular-nums">{c.indexed_tables ?? 0}</TableCell>
                <TableCell>
                  <CoverageBar value={Math.min(100, c.vectors ? 100 : 0)} />
                </TableCell>
                <TableCell>
                  <StatusBadge status={(healthy ? "success" : "warning") as StatusKind} />
                </TableCell>
              </TableRow>
            ))
          ) : (
            <TableRow>
              <TableCell colSpan={5} className="text-sm text-muted-foreground">
                No embedding collections available yet.
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  );
}
