import type { HealthResponse } from "@/types/backend";

export const healthApi = {
  health: async (): Promise<HealthResponse> => {
    const base = import.meta.env.VITE_API_BASE_URL ?? "";
    const root = base.replace(/\/api\/v1\/?$/, "");
    const response = await fetch(`${root}/health`, {
      headers: { "Content-Type": "application/json" },
    });
    if (!response.ok) {
      const text = await response.text().catch(() => "");
      throw new Error(text || `Request failed: ${response.status}`);
    }
    return response.json() as Promise<HealthResponse>;
  },
};
