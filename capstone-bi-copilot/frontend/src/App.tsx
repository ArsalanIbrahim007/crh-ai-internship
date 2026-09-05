import { useEffect, useMemo, useRef, useState } from "react";
import { OrbHero } from "./components/copilot/OrbHero";
import { Sidebar } from "./components/layout/Sidebar";
import { listConversations, loadConversation, sendChat, type SavedConversation } from "./lib/api";
import { CopilotPage, type LocalMessage } from "./pages/CopilotPage";
import { DocumentsPage } from "./pages/DocumentsPage";
import { CalendarPage } from "./pages/CalendarPage";
import { ConnectionsPage } from "./pages/ConnectionsPage";
import { AnalyticsPage } from "./pages/AnalyticsPage";

export type AppView = "copilot" | "history" | "documents" | "calendar" | "connections" | "analytics";

function viewFromPath(): AppView {
  if (window.location.pathname === "/history") return "history";
  if (window.location.pathname === "/documents") return "documents";
  if (window.location.pathname === "/calendar") return "calendar";
  if (window.location.pathname === "/connections") return "connections";
  if (window.location.pathname === "/analytics") return "analytics";
  return "copilot";
}

export function App() {
  const [view, setView] = useState<AppView>(viewFromPath);
  const [messages, setMessages] = useState<LocalMessage[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [history, setHistory] = useState<SavedConversation[]>([]);
  const [historyBusy, setHistoryBusy] = useState(false);
  const [historyError, setHistoryError] = useState("");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [composerKey, setComposerKey] = useState(0);
  const [voiceActivity,setVoiceActivity]=useState<"idle"|"listening"|"processing"|"speaking"|"error">("idle");
  const requestEpoch = useRef(0);
  const heroOrbTargetRef = useRef<HTMLDivElement | null>(null);
  const sidebarOrbTargetRef = useRef<HTMLDivElement | null>(null);

  const hasActiveConversation = Boolean(conversationId) || messages.length > 0;
  const orbIsParked = hasActiveConversation || view !== "copilot";

  const conversationHistory = useMemo(() => {
    if (!hasActiveConversation) return history;
    const firstQuestion = messages.find((message) => message.role === "user")?.text;
    const current: SavedConversation = {
      id: conversationId ?? "current-conversation",
      title: firstQuestion ?? "Current conversation",
      updated_at: new Date().toISOString(),
      message_count: messages.length,
    };
    return [current, ...history.filter((item) => item.id !== current.id)];
  }, [conversationId, hasActiveConversation, history, messages]);

  useEffect(() => {
    if (view !== "history") return;
    let active = true;
    setHistoryBusy(true); setHistoryError("");
    listConversations().then((items) => { if (active) setHistory(items); })
      .catch((error) => { if (active) setHistoryError(error instanceof Error ? error.message : "Chat history could not be loaded."); })
      .finally(() => { if (active) setHistoryBusy(false); });
    return () => { active = false; };
  }, [view]);

  useEffect(() => {
    const onPopState = () => setView(viewFromPath());
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  function navigate(nextView: AppView, replace = false) {
    const path = nextView === "copilot" ? "/" : `/${nextView}`;
    if (window.location.pathname !== path) {
      window.history[replace ? "replaceState" : "pushState"]({}, "", path);
    }
    setView(nextView);
  }

  function startNewChat() {
    requestEpoch.current += 1;
    const firstQuestion = messages.find((message) => message.role === "user")?.text;
    if (hasActiveConversation && firstQuestion) {
      setHistory((items) => [
        {
          id: conversationId ?? `local-${Date.now()}`,
          title: firstQuestion,
          updated_at: new Date().toISOString(),
          message_count: messages.length,
        },
        ...items.filter((item) => item.id !== conversationId),
      ]);
    }
    setMessages([]);
    setConversationId(null);
    setBusy(false);
    setStatus(null);
    setComposerKey((key) => key + 1);
    navigate("copilot");
  }

  async function onSend(queryText: string, voiceMode = false) {
    const epoch = requestEpoch.current;
    setBusy(true);
    setStatus(null);
    setMessages((items) => [...items, { role: "user", text: queryText }]);

    try {
      const response = await sendChat({
        conversation_id: conversationId,
        query_text: queryText,
        attachment_ids: [],
        voice_mode: voiceMode,
      });
      if (requestEpoch.current !== epoch) return;
      setConversationId(response.conversation_id);
      setMessages((items) => [...items, { role: "assistant", response }]);
      if (response.error) setStatus("I could not complete that request. Please try again.");
    } catch {
      if (requestEpoch.current === epoch) {
        setStatus("I could not complete that request. Please try again.");
      }
    } finally {
      if (requestEpoch.current === epoch) setBusy(false);
    }
  }

  async function openConversation(id: string) {
    setHistoryBusy(true); setHistoryError("");
    try {
      const saved = await loadConversation(id);
      setConversationId(saved.id);
      setMessages(saved.messages.map((item) => item.role === "user"
        ? { role: "user", text: item.content }
        : { role: "assistant", response: {
            request_id: `history-${item.id}`, conversation_id: saved.id, message_id: item.id,
            answer: item.content, intent: "general_chat", kpis: [],
            chart_spec: { type: "none", title: "", x_key: null, y_keys: [], rows: [] },
            insights: [], recommendations: [], forecast: null, sources: [], tool_calls: [],
            requires_approval: false, suggested_questions: [], error: null,
          } }));
      navigate("copilot");
    } catch (error) {
      setHistoryError(error instanceof Error ? error.message : "Chat history could not be loaded.");
    } finally { setHistoryBusy(false); }
  }

  return (
    <div className="app-shell">
      <Sidebar
        activeView={view}
        hasActiveConversation={hasActiveConversation}
        orbTargetRef={sidebarOrbTargetRef}
        onNewChat={startNewChat}
        onNavigate={navigate}
      />
      <OrbHero busy={busy || voiceActivity !== "idle"} destinationRef={orbIsParked ? sidebarOrbTargetRef : heroOrbTargetRef} parked={orbIsParked} />
            {view === "documents" && <DocumentsPage />}
      {view === "calendar" && <CalendarPage onNavigate={navigate} />}
      {view === "connections" && <ConnectionsPage />}
      {view === "analytics" && <AnalyticsPage />}
      <div style={{ display: view === "documents" || view === "calendar" || view === "connections" || view === "analytics" ? "none" : "contents" }}>
      <CopilotPage
        busy={busy}
        composerKey={composerKey}
        conversationHistory={conversationHistory}
        historyBusy={historyBusy}
        historyError={historyError}
        hasActiveConversation={hasActiveConversation}
        heroOrbTargetRef={heroOrbTargetRef}
        messages={messages}
        onSend={onSend}
        onOpenConversation={openConversation}
        onVoiceActivity={setVoiceActivity}
        status={status}
        view={view}
      />
      </div>
    </div>
  );
}
