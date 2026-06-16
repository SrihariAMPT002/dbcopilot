import { useQuery } from "@tanstack/react-query";
import { ConnectionService } from "@/services/connectionService";

export function useConnections() {
  return useQuery({
    queryKey: ["connections"],
    queryFn: ConnectionService.list,
    refetchInterval: 10000,
    refetchOnWindowFocus: true,
  });
}
