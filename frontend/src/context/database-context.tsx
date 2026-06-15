import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { databasesApi } from "@/api/databases";
import type { DatabaseSummary, DefaultDatabaseResponse } from "@/types/backend";

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
  const { data: databases = [] } = useQuery({ queryKey: ["databases"], queryFn: databasesApi.list });
  const { data: defaultDatabase } = useQuery({ queryKey: ["databases", "default"], queryFn: () => databasesApi.default() });
  const [selectedDatabaseId, setSelectedDatabaseIdState] = useState<number | null>(null);
  const [hydrated, setHydrated] = useState(false);

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
    if (selectedDatabaseId != null) return;

    if (defaultDatabase?.database_id) {
      setSelectedDatabaseIdState(defaultDatabase.database_id);
      return;
    }

    if (databases.length) {
      setSelectedDatabaseIdState(databases[0].database_id);
    }
  }, [databases, defaultDatabase, hydrated, selectedDatabaseId]);

  useEffect(() => {
    if (selectedDatabaseId == null) {
      window.localStorage.removeItem(STORAGE_KEY);
    } else {
      window.localStorage.setItem(STORAGE_KEY, String(selectedDatabaseId));
    }
  }, [selectedDatabaseId]);

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
