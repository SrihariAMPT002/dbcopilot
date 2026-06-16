export type BusinessInsight = {
  id?: number;
  insight_text: string;
  confidence_score: number;
  impact_level?: string | null;
  evidence: Array<Record<string, unknown>>;
  trace_id?: string | null;
  created_at?: string | null;
};

export type BusinessInsightsResponse = {
  database_id: number;
  insights: BusinessInsight[];
};
