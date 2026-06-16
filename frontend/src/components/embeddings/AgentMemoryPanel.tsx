import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/empty-state";
import { History } from "lucide-react";

export function AgentMemoryPanel({
  memories,
}: {
  memories: Array<{ id: number; query_text: string; response_text?: string | null; trace_id?: string | null }>;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Agent memory</CardTitle>
        <CardDescription>Recent stored interactions used for semantic recall.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {memories.length ? (
          memories.map((item) => (
            <div key={item.id} className="rounded-md border border-border bg-card p-3">
              <div className="text-sm font-medium text-foreground">{item.query_text}</div>
              <div className="mt-1 text-xs text-muted-foreground">{item.response_text ?? "No response stored."}</div>
            </div>
          ))
        ) : (
          <EmptyState icon={History} title="No agent memory yet" description="Record agent interactions to build reusable memory." />
        )}
      </CardContent>
    </Card>
  );
}
