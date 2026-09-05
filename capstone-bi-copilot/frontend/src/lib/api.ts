import type { AlertItem, AnalyticsResult, Briefing, ChatRequest, ChatResponse, ToolCall } from "../types/contracts";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

export async function sendChat(request: ChatRequest): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error("The copilot could not complete that request.");
  }

  return response.json() as Promise<ChatResponse>;
}

export async function decideToolAction(messageId: string, decision: "approve" | "cancel"): Promise<ToolCall> {
  const response = await fetch(`${API_BASE}/api/chat/${encodeURIComponent(messageId)}/approval`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ decision }),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(typeof body?.detail === "string" ? body.detail : "The action could not be processed.");
  }
  return response.json() as Promise<ToolCall>;
}

export interface SavedConversation {
  id: string;
  title: string;
  updated_at: string;
  message_count: number;
}

export interface SavedConversationDetail {
  id: string;
  title: string;
  messages: { id: string; role: "user" | "assistant"; content: string; created_at: string }[];
}

async function historyRequest<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}/api/chat${path}`, { credentials: "include" });
  if (!response.ok) throw new Error(response.status === 401 ? "Sign in to view chat history." : "Chat history could not be loaded.");
  return response.json() as Promise<T>;
}

export const listConversations = () => historyRequest<SavedConversation[]>("/conversations");
export const loadConversation = (id: string) => historyRequest<SavedConversationDetail>(`/conversations/${encodeURIComponent(id)}`);

export async function transcribeVoice(audio: Blob): Promise<string> {
  const body=new FormData(); body.append("audio",audio,"recording.webm"); body.append("mime_type",audio.type || "audio/webm");
  const response=await fetch(`${API_BASE}/api/voice/transcribe`,{method:"POST",body,credentials:"include"});
  const result=await response.json().catch(()=>null);
  if(!response.ok) throw new Error(typeof result?.detail === "string" ? result.detail : "Speech could not be transcribed.");
  return result.text as string;
}

export async function synthesizeVoice(text: string): Promise<Blob> {
  const response=await fetch(`${API_BASE}/api/voice/synthesize`,{method:"POST",credentials:"include",headers:{"Content-Type":"application/json"},body:JSON.stringify({text})});
  if(!response.ok){const result=await response.json().catch(()=>null);throw new Error(typeof result?.detail === "string"?result.detail:"Voice playback failed.");}
  return response.blob();
}

async function analyticsRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}/api/analytics${path}`, { credentials: "include", ...init });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(typeof body?.detail === "string" ? body.detail : "Analytics data could not be loaded.");
  }
  return response.json() as Promise<T>;
}

export const fetchAnalyticsOverview = (signal?: AbortSignal) => analyticsRequest<AnalyticsResult>("/overview", { signal });

// NOTE: the backend binds `question` as a query parameter (not a JSON body) on this POST route -
// confirmed against api/analytics.py: query_analytics(question: str, db = Depends(get_db)).
export const queryAnalytics = (question: string, signal?: AbortSignal) =>
  analyticsRequest<AnalyticsResult>(`/query?question=${encodeURIComponent(question)}`, { method: "POST", signal });

export const fetchAlerts = (signal?: AbortSignal) => analyticsRequest<AlertItem[]>("/alerts", { signal });

export const fetchBriefing = (signal?: AbortSignal) => analyticsRequest<Briefing>("/briefing", { signal });
