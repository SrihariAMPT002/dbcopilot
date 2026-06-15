import { useRouterState } from "@tanstack/react-router";
import { Database } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { useDatabaseContext } from "@/context/database-context";

export function ActiveDatabaseBadge() {
  const { selectedDatabase } = useDatabaseContext();
  const pathname = useRouterState({ select: (r) => r.location.pathname });
  const isDashboard = pathname === "/";

  return (
    <Badge variant="outline" className="hidden gap-1.5 border-border bg-muted/40 px-2 py-1 text-[11px] font-medium text-muted-foreground sm:inline-flex">
      <Database className="h-3 w-3" />
      {isDashboard ? (
        <span className="truncate">DBCopilot Platform</span>
      ) : selectedDatabase ? (
        <span className="truncate">
          {selectedDatabase.database_name} (#{selectedDatabase.database_id}){selectedDatabase.db_type ? ` · ${selectedDatabase.db_type}` : ""}
        </span>
      ) : (
        <span>No database selected</span>
      )}
    </Badge>
  );
}
