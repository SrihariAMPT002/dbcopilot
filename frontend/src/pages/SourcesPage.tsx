import { useMemo, useState } from "react";
import { useMutation, useQueries, useQueryClient } from "@tanstack/react-query";
import { useNavigate, Link } from "@tanstack/react-router";
import { Database, Plus, RefreshCw, MoreHorizontal, Search, ExternalLink, Trash2, Sparkles, Power, RotateCcw, Archive } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { StatusBadge, type StatusKind } from "@/components/status-badge";
import { CoverageBar } from "@/components/coverage-bar";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { metadataApi } from "@/api/metadata";
import { useConnections } from "@/hooks/useConnections";
import { connectionsApi } from "@/api/connections";
import { useDatabaseContext } from "@/context/database-context";
import { toast } from "sonner";
import { DisconnectDatabaseModal } from "@/components/common/DisconnectDatabaseModal";
import { ArchiveDatabaseModal } from "@/components/common/ArchiveDatabaseModal";
import { DeleteDatabaseModal } from "@/components/common/DeleteDatabaseModal";
import { TraceLink } from "@/components/common/TraceLink";
import { queryKeys } from "@/lib/query-keys";

export function SourcesPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const { data = [] } = useConnections();
  const { setSelectedDatabaseId } = useDatabaseContext();
  const [search, setSearch] = useState("");
  const [message, setMessage] = useState<string>("");
  const [pendingAction, setPendingAction] = useState<{
    type: "disconnect" | "archive" | "delete";
    id: number;
    name: string;
  } | null>(null);

  const sources = useMemo(
      () =>
        data.map((s) => ({
          id: s.id,
          name: s.name,
          engine: s.db_type,
          env: "production",
          host: s.host,
          schemas: s.schema_count ?? 0,
          tables: s.table_count ?? 0,
          coverage: Math.min(100, s.table_count ? 80 : 0),
          status:
            (s.status === "active"
              ? "success"
              : s.status === "inactive"
                ? "neutral"
                : s.status === "testing"
                  ? "running"
                  : s.status) as StatusKind,
          lifecycleStatus: (s.lifecycle_status ?? "ACTIVE").toLowerCase() as StatusKind,
          lastSync: s.last_sync_at ? new Date(s.last_sync_at).toLocaleString() : "unknown",
        })),
    [data],
  );

  const visibleSources = sources.filter((source) => {
    const q = search.trim().toLowerCase();
    if (!q) return true;
    return [source.name, source.engine, source.host].some((field) => field.toLowerCase().includes(q));
  });

  const syncLogQueries = useQueries({
    queries: visibleSources.map((source) => ({
      queryKey: queryKeys.syncLogs(source.id, 1),
      queryFn: () => metadataApi.syncLogs(source.id, 1),
      enabled: !!source.id,
    })),
  });

  const lastSyncById = useMemo(() => {
    const map = new Map<number, string>();
    syncLogQueries.forEach((query, index) => {
      const source = visibleSources[index];
      const latest = query.data?.[0];
      const raw = source?.lastSync !== "unknown" ? source?.lastSync : latest?.completed_at ?? latest?.started_at;
      if (source && raw) {
        map.set(source.id, typeof raw === "string" ? raw : new Date(raw).toLocaleString());
      }
    });
    return map;
  }, [syncLogQueries, visibleSources]);

  const latestTraceById = useMemo(() => {
    const map = new Map<number, string>();
    syncLogQueries.forEach((query, index) => {
      const source = visibleSources[index];
      const latest = query.data?.[0] as { trace_id?: string | null } | undefined;
      if (source && latest?.trace_id) {
        map.set(source.id, latest.trace_id);
      }
    });
    return map;
  }, [syncLogQueries, visibleSources]);

  const syncMutation = useMutation({
    mutationFn: async (dbId: number) => connectionsApi.sync(dbId),
    onSuccess: async () => {
      setMessage("Sync queued successfully.");
      toast.success("Sync queued successfully.");
      await queryClient.invalidateQueries({ queryKey: queryKeys.connections() });
      await queryClient.invalidateQueries({ queryKey: queryKeys.dashboard("default") });
      await queryClient.invalidateQueries({ queryKey: queryKeys.pipeline() });
      await queryClient.invalidateQueries({ queryKey: queryKeys.syncLogsAll() });
    },
    onError: (error) => {
      const text = error instanceof Error ? error.message : "Sync failed";
      setMessage(text);
      toast.error(text);
    },
  });

  const syncAllMutation = useMutation({
    mutationFn: async () => Promise.all(data.map((source) => connectionsApi.sync(source.id))),
    onSuccess: async () => {
      setMessage("Sync queued for all connected sources.");
      toast.success("Sync queued for all connected sources.");
      await queryClient.invalidateQueries({ queryKey: queryKeys.connections() });
      await queryClient.invalidateQueries({ queryKey: queryKeys.dashboard("default") });
      await queryClient.invalidateQueries({ queryKey: queryKeys.pipeline() });
      await queryClient.invalidateQueries({ queryKey: queryKeys.syncLogsAll() });
    },
    onError: (error) => {
      const text = error instanceof Error ? error.message : "Sync all failed";
      setMessage(text);
      toast.error(text);
    },
  });

  const disconnectMutation = useMutation({
    mutationFn: async ({ dbId, confirmationText }: { dbId: number; confirmationText: string }) =>
      connectionsApi.disconnect(dbId, { confirmation_text: confirmationText }),
    onSuccess: async () => {
      setMessage("Connection disconnected.");
      toast.success("Connection disconnected.");
      await queryClient.invalidateQueries({ queryKey: queryKeys.connections() });
      await queryClient.invalidateQueries({ queryKey: queryKeys.databases() });
      await queryClient.invalidateQueries({ queryKey: queryKeys.dashboard("default") });
      await queryClient.invalidateQueries({ queryKey: queryKeys.pipeline() });
      await queryClient.invalidateQueries({ queryKey: queryKeys.observability() });
      await queryClient.invalidateQueries({ queryKey: queryKeys.syncLogsAll() });
    },
    onError: (error) => {
      const text = error instanceof Error ? error.message : "Disconnect failed";
      setMessage(text);
      toast.error(text);
    },
  });

  const archiveMutation = useMutation({
    mutationFn: async ({ dbId, confirmationText }: { dbId: number; confirmationText: string }) =>
      connectionsApi.archive(dbId, { confirmation_text: confirmationText }),
    onSuccess: async () => {
      setMessage("Connection archived.");
      toast.success("Connection archived.");
      await queryClient.invalidateQueries({ queryKey: queryKeys.connections() });
      await queryClient.invalidateQueries({ queryKey: queryKeys.databases() });
      await queryClient.invalidateQueries({ queryKey: queryKeys.dashboard("default") });
      await queryClient.invalidateQueries({ queryKey: queryKeys.syncLogsAll() });
    },
    onError: (error) => {
      const text = error instanceof Error ? error.message : "Archive failed";
      setMessage(text);
      toast.error(text);
    },
  });

  const reconnectMutation = useMutation({
    mutationFn: async ({ dbId, confirmationText }: { dbId: number; confirmationText: string }) =>
      connectionsApi.reconnect(dbId, { confirmation_text: confirmationText }),
    onSuccess: async () => {
      setMessage("Connection reconnected.");
      toast.success("Connection reconnected.");
      await queryClient.invalidateQueries({ queryKey: queryKeys.connections() });
      await queryClient.invalidateQueries({ queryKey: queryKeys.databases() });
      await queryClient.invalidateQueries({ queryKey: queryKeys.dashboard("default") });
      await queryClient.invalidateQueries({ queryKey: queryKeys.pipeline() });
    },
    onError: (error) => {
      const text = error instanceof Error ? error.message : "Reconnect failed";
      setMessage(text);
      toast.error(text);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async ({ dbId, confirmationText }: { dbId: number; confirmationText: string }) => connectionsApi.delete(dbId, {
      confirmation_text: confirmationText,
      delete_metadata: true,
      delete_packages: true,
      delete_embeddings: true,
      delete_observability: true,
    }),
    onSuccess: async () => {
      setMessage("Connection deleted.");
      toast.success("Connection deleted.");
      await queryClient.invalidateQueries({ queryKey: queryKeys.connections() });
      await queryClient.invalidateQueries({ queryKey: queryKeys.databases() });
      await queryClient.invalidateQueries({ queryKey: queryKeys.dashboard("default") });
      await queryClient.invalidateQueries({ queryKey: queryKeys.pipeline() });
      await queryClient.invalidateQueries({ queryKey: queryKeys.observability() });
      await queryClient.invalidateQueries({ queryKey: queryKeys.syncLogsAll() });
    },
    onError: (error) => {
      const text = error instanceof Error ? error.message : "Delete failed";
      setMessage(text);
      toast.error(text);
    },
  });

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Sources"
        title="Connected sources"
        description="All registered database connections backed by the live backend."
        actions={
          <>
            <Button variant="outline" size="sm" className="gap-1.5" onClick={() => syncAllMutation.mutate()} disabled={syncAllMutation.isPending}>
              <RefreshCw className="h-3.5 w-3.5" /> Sync all
            </Button>
            <Button asChild size="sm" className="gap-1.5 bg-gradient-to-br from-primary to-primary-glow text-primary-foreground">
              <Link to="/connect">
                <Plus className="h-3.5 w-3.5" /> Add source
              </Link>
            </Button>
          </>
        }
      />
      <Card>
        <CardContent className="p-4">
          <div className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 sm:flex sm:flex-wrap sm:justify-between">
            <div className="relative min-w-0 flex-1 sm:max-w-sm">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
              <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search sources…" className="h-9 pl-9" />
            </div>
            <div className="flex shrink-0 items-center gap-2">
              <Badge variant="outline" className="text-[11px]">
                All engines
              </Badge>
              <Badge variant="outline" className="text-[11px]">
                All environments
              </Badge>
            </div>
          </div>
          {message ? <div className="mt-3 text-xs text-muted-foreground">{message}</div> : null}
          <div className="mt-4 overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow className="bg-muted/40 hover:bg-muted/40">
                  <TableHead className="min-w-[200px]">Source</TableHead>
                  <TableHead>Engine</TableHead>
                  <TableHead>Env</TableHead>
                  <TableHead className="text-right">Schemas</TableHead>
                  <TableHead className="text-right">Tables</TableHead>
                  <TableHead className="min-w-[160px]">AI coverage</TableHead>
                  <TableHead>Sync</TableHead>
                  <TableHead>Lifecycle</TableHead>
                  <TableHead>Last sync</TableHead>
                  <TableHead className="w-10"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {visibleSources.map((s) => (
                  <TableRow key={s.id} className="hover:bg-muted/30">
                    <TableCell className="font-medium">
                      <div className="flex min-w-0 items-center gap-2">
                        <div className="grid h-7 w-7 shrink-0 place-items-center rounded-md bg-gradient-to-br from-primary/15 to-primary/0 text-primary">
                          <Database className="h-3.5 w-3.5" />
                        </div>
                        <div className="min-w-0">
                          <div className="truncate text-sm text-foreground">{s.name}</div>
                          <div className="truncate text-[11px] text-muted-foreground">{s.host}</div>
                        </div>
                      </div>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">{s.engine}</TableCell>
                    <TableCell>
                      <Badge variant="outline" className="text-[10px] uppercase tracking-wider">
                        {s.env}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right tabular-nums">{s.schemas}</TableCell>
                    <TableCell className="text-right tabular-nums">{s.tables}</TableCell>
                    <TableCell className="min-w-[160px]">
                      <CoverageBar value={s.coverage} />
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={s.status} />
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={s.lifecycleStatus} />
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      <div className="space-y-1">
                        <div>{lastSyncById.get(s.id) ?? s.lastSync}</div>
                        <TraceLink traceId={latestTraceById.get(s.id)} label="Open trace" className="text-[11px]" />
                      </div>
                    </TableCell>
                    <TableCell className="text-right">
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon" className="h-7 w-7">
                            <MoreHorizontal className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem
                            onSelect={(event) => {
                              event.preventDefault();
                              setSelectedDatabaseId(s.id);
                              void navigate({ to: "/explorer" });
                            }}
                          >
                            <ExternalLink className="mr-2 h-4 w-4" /> Open explorer
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            disabled={syncMutation.isPending}
                            onSelect={(event) => {
                              event.preventDefault();
                              syncMutation.mutate(s.id);
                            }}
                          >
                            <RefreshCw className="mr-2 h-4 w-4" /> Run sync
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            disabled={syncMutation.isPending}
                            onSelect={(event) => {
                              event.preventDefault();
                              syncMutation.mutate(s.id);
                            }}
                          >
                            <Sparkles className="mr-2 h-4 w-4" /> Sync and regenerate packages
                          </DropdownMenuItem>
                          {s.lifecycleStatus === "active" ? (
                            <DropdownMenuItem
                              disabled={disconnectMutation.isPending}
                              onSelect={(event) => {
                              event.preventDefault();
                              setPendingAction({ type: "disconnect", id: s.id, name: s.name });
                            }}
                          >
                              <Power className="mr-2 h-4 w-4" /> Disconnect
                            </DropdownMenuItem>
                          ) : null}
                          {s.lifecycleStatus === "disconnected" ? (
                            <DropdownMenuItem
                              disabled={reconnectMutation.isPending}
                              onSelect={(event) => {
                              event.preventDefault();
                                reconnectMutation.mutate({ dbId: s.id, confirmationText: s.name });
                              }}
                            >
                              <RotateCcw className="mr-2 h-4 w-4" /> Reconnect
                            </DropdownMenuItem>
                          ) : null}
                          {s.lifecycleStatus !== "archived" ? (
                            <DropdownMenuItem
                              disabled={archiveMutation.isPending}
                              onSelect={(event) => {
                                event.preventDefault();
                                setPendingAction({ type: "archive", id: s.id, name: s.name });
                              }}
                            >
                              <Archive className="mr-2 h-4 w-4" /> Archive
                            </DropdownMenuItem>
                          ) : null}
                          <DropdownMenuItem
                            className="text-destructive"
                            disabled={deleteMutation.isPending}
                            onSelect={(event) => {
                              event.preventDefault();
                              setPendingAction({ type: "delete", id: s.id, name: s.name });
                            }}
                          >
                            <Trash2 className="mr-2 h-4 w-4" /> Delete
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
      <DisconnectDatabaseModal
        open={pendingAction?.type === "disconnect"}
        onOpenChange={(open) => !open && setPendingAction(null)}
        connectionName={pendingAction?.name ?? ""}
      busy={disconnectMutation.isPending}
        onConfirm={async (confirmationText) => {
          if (pendingAction?.type !== "disconnect") return;
          await disconnectMutation.mutateAsync({ dbId: pendingAction.id, confirmationText });
          setPendingAction(null);
        }}
      />
      <ArchiveDatabaseModal
        open={pendingAction?.type === "archive"}
        onOpenChange={(open) => !open && setPendingAction(null)}
        connectionName={pendingAction?.name ?? ""}
      busy={archiveMutation.isPending}
        onConfirm={async (confirmationText) => {
          if (pendingAction?.type !== "archive") return;
          await archiveMutation.mutateAsync({ dbId: pendingAction.id, confirmationText });
          setPendingAction(null);
        }}
      />
      <DeleteDatabaseModal
        open={pendingAction?.type === "delete"}
        onOpenChange={(open) => !open && setPendingAction(null)}
        connectionName={pendingAction?.name ?? ""}
      busy={deleteMutation.isPending}
        onConfirm={async (confirmationText) => {
          if (pendingAction?.type !== "delete") return;
          await deleteMutation.mutateAsync({ dbId: pendingAction.id, confirmationText });
          setPendingAction(null);
        }}
      />
    </div>
  );
}
