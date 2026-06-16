import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { databasesApi } from "@/api/databases";
import type { DatabaseSummary } from "@/types/backend";

const STORAGE_KEY = "dbcopilot.selectedDatabaseId";

type DatabaseContextValue = {
  selectedDatabaseId: number | null;
  setSelectedDatabaseId: (databaseId: number | null) => void;
  selectedDatabase: DatabaseSummary | null;
  databases: DatabaseSummary[];
  isHydrated: boolean;
};

const DatabaseContext = createContext<DatabaseContextValue | null>(null);

export function DatabaseProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const { data: databases = [] } = useQuery({ queryKey: ["databases"], queryFn: databasesApi.list });
  const [selectedDatabaseId, setSelectedDatabaseIdState] = useState<number | null>(null);
  const [hydrated, setHydrated] = useState(false);

  const selectedDatabaseExists = useMemo(
    () => selectedDatabaseId == null || databases.some((db) => db.database_id === selectedDatabaseId),
    [databases, selectedDatabaseId],
  );

  const defaultDatabaseQuery = useQuery({
    queryKey: ["databases", "default", selectedDatabaseId],
    queryFn: () => databasesApi.default(selectedDatabaseId),
    enabled: hydrated,
  });

  useEffect(() => {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored) {
      const parsed = Number(stored);
      setSelectedDatabaseIdState(Number.isFinite(parsed) ? parsed : null);
    }
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    if (selectedDatabaseId != null && !selectedDatabaseExists) {
      const fallback = defaultDatabaseQuery.data?.database_id ?? databases[0]?.database_id ?? null;
      setSelectedDatabaseIdState(fallback);
      return;
    }

    if (selectedDatabaseId == null) {
      const fallback = defaultDatabaseQuery.data?.database_id ?? databases[0]?.database_id ?? null;
      if (fallback != null) {
        setSelectedDatabaseIdState(fallback);
      }
    }
  }, [databases, defaultDatabaseQuery.data, hydrated, selectedDatabaseExists, selectedDatabaseId]);

  useEffect(() => {
    if (selectedDatabaseId == null) {
      window.localStorage.removeItem(STORAGE_KEY);
    } else {
      window.localStorage.setItem(STORAGE_KEY, String(selectedDatabaseId));
    }
    if (hydrated) {
      void queryClient.invalidateQueries({
        predicate: (query) => {
          const key = query.queryKey;
          return Array.isArray(key) && typeof key[0] === "string" && ["governance", "semantics", "relationships", "kpi", "embeddings", "prompt-packages", "prompt-bundle", "readiness", "jobs", "agent-memory", "retrieval-metrics", "retrieval-evaluation", "semantic-cache", "business-events", "business-insights", "business-intelligence", "dashboard", "pipeline", "readiness-history"].includes(key[0]);
        },
      });
    }
  }, [hydrated, queryClient, selectedDatabaseId]);

  const selectedDatabase = useMemo(
    () => databases.find((db) => db.database_id === selectedDatabaseId) ?? null,
    [databases, selectedDatabaseId],
  );

  const value = useMemo(
    () => ({
      selectedDatabaseId,
      setSelectedDatabaseId: setSelectedDatabaseIdState,
      selectedDatabase,
      databases,
      isHydrated: hydrated,
    }),
    [databases, hydrated, selectedDatabase, selectedDatabaseId],
  );

  return <DatabaseContext.Provider value={value}>{children}</DatabaseContext.Provider>;
}

export function useDatabaseContext() {
  const ctx = useContext(DatabaseContext);
  if (!ctx) throw new Error("useDatabaseContext must be used within DatabaseProvider");
  return ctx;
}
