import { useQuery } from "@tanstack/react-query";
import { ConnectionService } from "@/services/connectionService";
import { queryKeys } from "@/lib/query-keys";

export function useConnections() {
  return useQuery({
    queryKey: queryKeys.connections(),
    queryFn: ConnectionService.list,
    refetchInterval: 10000,
    refetchOnWindowFocus: true,
  });
}
