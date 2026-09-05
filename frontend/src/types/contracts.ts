export interface KPI {
  key: string;
  label: string;
  value: number | string;
  unit: string | null;
  delta: number | null;
}

export interface ChartSpec {
  type: "line" | "bar" | "area" | "pie" | "table" | "none";
  title: string;
  x_key: string | null;
  y_keys: string[];
  rows: Record<string, unknown>[];
}

export interface SourceRef {
  source_id: string;
  title: string;
  location: string | null;
  snippet: string | null;
}

export interface ToolCall {
  tool_name: string;
  arguments: Record<string, unknown>;
  status: "proposed" | "approved" | "executed" | "failed";
}

export interface ChatRequest {
  conversation_id?: string | null;
  query_text: string;
  attachment_ids: string[];
  voice_mode: boolean;
}

export interface ChatResponse {
  request_id: string;
  conversation_id: string;
  message_id: string;
  answer: string;
  intent: string;
  kpis: KPI[];
  chart_spec: ChartSpec;
  insights: string[];
  recommendations: string[];
  forecast: Record<string, unknown> | null;
  sources: SourceRef[];
  tool_calls: ToolCall[];
  requires_approval: boolean;
  suggested_questions: string[];
  error: Record<string, unknown> | null;
}
