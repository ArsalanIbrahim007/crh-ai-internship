export type FileKind = "pdf" | "document" | "spreadsheet" | "slides" | "text";
export interface WorkspaceFile {
  id: string;
  filename: string;
  mime_type: string;
  folder_id: string | null;
  size: number | null;
  created_at: string;
  updated_at: string;
}
export interface WorkspaceFolder {
  folder_id: string;
  name: string;
  parent_folder_id: string | null;
  document_count: number;
  created_at: string;
  updated_at: string;
}
export interface CalendarEvent {
  id: string;
  title: string;
  start: string;
  end: string;
  location?: string;
  attendees: string[];
  reminder?: string;
  agenda?: string;
  color: "blue" | "peach" | "lavender";
}
export type ConnectionState =
  | "not_connected"
  | "connecting"
  | "connected"
  | "error"
  | "needs_reauthorization";
export interface Integration {
  provider: string;
  name: string;
  description: string;
  state: ConnectionState;
  configured: boolean;
  account: string | null;
  message?: string;
  has_required_scope?: boolean;
  missing_scopes?: string[];
}
const base = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";
export async function workspaceRequest<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch(`${base}/api${path}`, {
    ...options,
    credentials: "include",
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(
      response.status === 401
        ? "Sign in to your workspace to continue."
        : typeof body?.detail === "string"
          ? body.detail
          : "The request failed. Please try again.",
    );
  }
  return response.json() as Promise<T>;
}
const json = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});
export const listDocuments = (signal: AbortSignal) =>
  workspaceRequest<WorkspaceFile[]>("/documents", { signal });
export const listFolders = (signal: AbortSignal) =>
  workspaceRequest<WorkspaceFolder[]>("/documents/folders", { signal });
export const createFolder = (name: string) =>
  workspaceRequest<WorkspaceFolder>(
    "/documents/folders",
    json("POST", { name }),
  );
export const renameFolder = (id: string, name: string) =>
  workspaceRequest<WorkspaceFolder>(
    `/documents/folders/${encodeURIComponent(id)}`,
    json("PATCH", { name }),
  );
export const deleteFolder = (id: string) =>
  workspaceRequest(`/documents/folders/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
export const deleteDocument = (id: string) =>
  workspaceRequest(`/documents/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
export const moveDocument = (id: string, folder_id: string | null) =>
  workspaceRequest(
    `/documents/${encodeURIComponent(id)}`,
    json("PATCH", { folder_id }),
  );
export function uploadDocument(
  file: File,
  folderId: string | null,
  onStage: (stage: string) => void,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const path = folderId
      ? `/documents/folders/${encodeURIComponent(folderId)}/upload`
      : "/documents/upload";
    xhr.open("POST", `${base}/api${path}`);
    xhr.withCredentials = true;
    xhr.timeout = 180000;
    xhr.upload.onload = () => onStage("Processing…");
    xhr.onerror = () =>
      reject(new Error("Upload failed. Check your connection and try again."));
    xhr.ontimeout = () =>
      reject(
        new Error(
          "Processing timed out. Refresh the document list before retrying.",
        ),
      );
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve();
        return;
      }
      let message = "Could not upload this document.";
      try {
        const result = JSON.parse(xhr.responseText);
        if (typeof result.detail === "string") message = result.detail;
      } catch {
        /* Use a readable fallback. */
      }
      reject(new Error(message));
    };
    const data = new FormData();
    data.append("file", file);
    onStage("Uploading…");
    xhr.send(data);
  });
}
export function fileKind(name: string): FileKind {
  const extension = name.split(".").pop()?.toLowerCase();
  if (extension === "pdf") return "pdf";
  if (["csv", "xlsx", "xls", "xlsm"].includes(extension ?? ""))
    return "spreadsheet";
  if (["ppt", "pptx"].includes(extension ?? "")) return "slides";
  if (["txt", "md", "html"].includes(extension ?? "")) return "text";
  return "document";
}
export function fileSize(bytes: number | null): string {
  return bytes == null
    ? "Size unavailable"
    : bytes < 1024
      ? `${bytes} B`
      : bytes < 1048576
        ? `${(bytes / 1024).toFixed(1)} KB`
        : `${(bytes / 1048576).toFixed(1)} MB`;
}
interface RawEvent {
  id?: string;
  event_id?: string;
  title?: string;
  summary?: string;
  start: string | { dateTime?: string; date?: string };
  end: string | { dateTime?: string; date?: string };
  location?: string;
  attendees?: (string | { displayName?: string; email?: string })[];
  description?: string;
  color?: CalendarEvent["color"];
  reminder?: string;
  reminders?: { overrides?: { minutes: number }[] };
}
export async function listCalendarEvents(
  start: Date,
  end: Date,
  signal: AbortSignal,
): Promise<CalendarEvent[]> {
  const query = new URLSearchParams({
    start_iso: start.toISOString(),
    end_iso: end.toISOString(),
  });
  const events = await workspaceRequest<RawEvent[]>(
    `/integrations/calendar/events?${query}`,
    { signal },
  );
  const date = (value: RawEvent["start"]) =>
    typeof value === "string" ? value : (value.dateTime ?? value.date ?? "");
  return events.map((event, index) => ({
    id: event.id ?? event.event_id ?? `event-${index}`,
    title: event.summary ?? event.title ?? "Untitled event",
    start: date(event.start),
    end: date(event.end),
    location: event.location,
    attendees: (event.attendees ?? []).map((person) =>
      typeof person === "string"
        ? person
        : (person.displayName ?? person.email ?? "Guest"),
    ),
    agenda: event.description,
    reminder:
      event.reminder ??
      (event.reminders?.overrides?.[0]
        ? `${event.reminders.overrides[0].minutes} minutes before`
        : undefined),
    color: event.color ?? "blue",
  }));
}
export function dateKey(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}
export function monthDays(month: Date): Date[] {
  const first = new Date(month.getFullYear(), month.getMonth(), 1);
  const count =
    Math.ceil(
      (first.getDay() +
        new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate()) /
        7,
    ) * 7;
  return Array.from(
    { length: count },
    (_, index) =>
      new Date(
        month.getFullYear(),
        month.getMonth(),
        index - first.getDay() + 1,
      ),
  );
}
export const listIntegrations = (signal: AbortSignal) =>
  workspaceRequest<Integration[]>("/integrations", { signal });
export async function connectionAction(
  provider: string,
  action: "connect" | "disconnect",
) {
  const result = await workspaceRequest<{ authorization_url?: string }>(
    `/integrations/${encodeURIComponent(provider)}/${action}`,
    { method: "POST" },
  );
  window.dispatchEvent(new Event("workspace-connections-changed"));
  if (result.authorization_url) {
    const url = new URL(result.authorization_url);
    if (url.protocol !== "https:")
      throw new Error("The provider returned an invalid authorization URL.");
    window.location.assign(url.href);
  }
}
