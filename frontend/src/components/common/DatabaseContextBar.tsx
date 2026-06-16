import { Database, Clock3, HeartPulse, ChevronsUpDown } from "lucide-react";
import { useMemo, useState } from "react";
import { Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { StatusBadge } from "@/components/status-badge";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { useDatabaseContext } from "@/context/database-context";
import { useConnections } from "@/hooks/useConnections";

export function DatabaseContextBar() {
  const [open, setOpen] = useState(false);
  const { databases, selectedDatabaseId, selectedDatabase, setSelectedDatabaseId } = useDatabaseContext();
  const { data: connections = [] } = useConnections();
  const selectedConnection = connections.find((conn) => conn.id === selectedDatabaseId) ?? null;

  const label = useMemo(() => {
    if (!selectedDatabase) return "Select database";
    return `${selectedDatabase.database_name} (#${selectedDatabase.database_id})`;
  }, [selectedDatabase]);

  const syncTime = selectedConnection?.last_sync_at ?? selectedDatabase?.connected_at ?? "n/a";
  const health = selectedConnection?.status ?? selectedDatabase?.status ?? "unknown";

  return (
    <div className="sticky top-14 z-20 border-b border-border bg-background/95 px-4 py-2 backdrop-blur-md sm:px-5">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline" className="gap-1.5 border-border bg-muted/40 px-2 py-1 text-[11px] font-medium text-muted-foreground">
              <Database className="h-3 w-3" />
              {selectedDatabase ? selectedDatabase.database_name : "No database selected"}
            </Badge>
            <Badge variant="outline" className="px-2 py-1 text-[11px] font-medium text-muted-foreground">ID {selectedDatabase?.database_id ?? "n/a"}</Badge>
            <Badge variant="outline" className="px-2 py-1 text-[11px] font-medium text-muted-foreground">{selectedDatabase?.db_type ?? "unknown"}</Badge>
            <StatusBadge status={selectedDatabase?.lifecycle_status?.toLowerCase()} label={selectedDatabase?.lifecycle_status ?? "ACTIVE"} />
            <Badge variant="outline" className="px-2 py-1 text-[11px] font-medium text-muted-foreground">
              <HeartPulse className="mr-1 h-3 w-3" />
              {health}
            </Badge>
            <Badge variant="outline" className="px-2 py-1 text-[11px] font-medium text-muted-foreground">
              <Clock3 className="mr-1 h-3 w-3" />
              {syncTime}
            </Badge>
          </div>
        </div>

        <Popover open={open} onOpenChange={setOpen}>
          <PopoverTrigger asChild>
            <Button variant="outline" className="h-9 min-w-[240px] justify-between gap-2">
              <span className="truncate text-left">{label}</span>
              <ChevronsUpDown className="h-4 w-4 shrink-0 opacity-60" />
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-[340px] p-0" align="end">
            <Command>
              <CommandInput placeholder="Search databases" />
              <CommandList>
                <CommandEmpty>No databases found.</CommandEmpty>
                <CommandGroup heading="Databases">
                  {databases.map((db) => (
                    <CommandItem
                      key={db.database_id}
                      value={`${db.database_name} ${db.database_id} ${db.db_type}`}
                      onSelect={() => {
                        setSelectedDatabaseId(db.database_id);
                        setOpen(false);
                      }}
                    >
                      <div className="flex min-w-0 flex-1 items-center justify-between gap-2">
                        <div className="min-w-0">
                          <div className="truncate text-sm">{db.database_name}</div>
                          <div className="text-[11px] text-muted-foreground">
                            #{db.database_id}
                            {db.db_type ? ` · ${db.db_type}` : ""}
                          </div>
                        </div>
                        {selectedDatabaseId === db.database_id ? <Check className="h-4 w-4" /> : null}
                      </div>
                    </CommandItem>
                  ))}
                </CommandGroup>
              </CommandList>
            </Command>
          </PopoverContent>
        </Popover>
      </div>
    </div>
  );
}
