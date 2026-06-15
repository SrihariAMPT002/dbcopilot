import { useQuery } from "@tanstack/react-query";
import { JobService } from "@/services/jobsService";

export function useJobs(limit = 20) {
  return useQuery({
    queryKey: ["jobs", limit],
    queryFn: () => JobService.list(limit),
  });
}
