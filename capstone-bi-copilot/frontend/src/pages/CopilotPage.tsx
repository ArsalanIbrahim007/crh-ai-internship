import { ArrowDown, Bot, FileText, MessageSquare } from "lucide-react";
import { useEffect, useRef, useState, type RefObject } from "react";
import type { AppView } from "../App";
import { Composer } from "../components/copilot/Composer";
import { MessageCard } from "../components/copilot/MessageCard";
import type { ChatResponse } from "../types/contracts";
import type { SavedConversation } from "../lib/api";
import { useVoicePreferences } from "../lib/voicePreferences";
import { useWakePhrase } from "../lib/useWakePhrase";
import type { VoiceInputState } from "../lib/useVoiceInput";

export interface LocalMessage {
  role: "user" | "assistant";
  text?: string;
  response?: ChatResponse;
}

interface CopilotPageProps {
  busy: boolean;
  composerKey: number;
  conversationHistory: SavedConversation[];
  historyBusy: boolean;
  historyError: string;
  hasActiveConversation: boolean;
  heroOrbTargetRef: RefObject<HTMLDivElement | null>;
  messages: LocalMessage[];
  onSend: (queryText: string, voiceMode?: boolean) => void;
  onOpenConversation: (id: string) => void;
  onVoiceActivity: (state:"idle"|"listening"|"processing"|"speaking"|"error")=>void;
  status: string | null;
  view: AppView;
}

export function CopilotPage({ busy, composerKey, conversationHistory, historyBusy, historyError, hasActiveConversation, heroOrbTargetRef, messages, onOpenConversation, onSend, onVoiceActivity, status, view }: CopilotPageProps) {
  const showLanding = view === "copilot" && !hasActiveConversation;
  const showChat = view === "copilot" && hasActiveConversation;
  const messagesRef = useRef<HTMLElement | null>(null);
  const nearBottomRef = useRef(true);
  const [showJumpToLatest, setShowJumpToLatest] = useState(false);
  const {preferences}=useVoicePreferences();
  const wake=useWakePhrase(preferences.wakePhrase,(command)=>onSend(command,true));
  function voiceInputState(state:VoiceInputState){onVoiceActivity(state)}

  useEffect(() => {
    if (!showChat || !nearBottomRef.current) return;
    requestAnimationFrame(() => messagesRef.current?.scrollTo({ top: messagesRef.current.scrollHeight, behavior: "smooth" }));
  }, [busy, messages, showChat]);

  function trackScroll() {
    const element = messagesRef.current;
    if (!element) return;
    const nearBottom = element.scrollHeight - element.scrollTop - element.clientHeight < 120;
    nearBottomRef.current = nearBottom;
    setShowJumpToLatest(!nearBottom);
  }

  function jumpToLatest() {
    nearBottomRef.current = true;
    setShowJumpToLatest(false);
    messagesRef.current?.scrollTo({ top: messagesRef.current.scrollHeight, behavior: "smooth" });
  }

  return (
    <main className={`copilot-page ${showChat ? "chat-mode" : ""} ${view !== "copilot" ? "section-mode" : ""}`}>
      <section className={`landing-hero ${showLanding ? "is-visible" : "is-hidden"}`} aria-label="AI Business Intelligence Copilot">
        <h1 className="hero-heading"><span>Insight in Sight.</span><strong>Decisions Done Right.</strong></h1>
        <div ref={heroOrbTargetRef} className="hero-orb-target" aria-hidden="true" />
      </section>

      {showChat && (
        <section className="messages" ref={messagesRef} onScroll={trackScroll} aria-live="polite" aria-label="Conversation">
          {messages.map((message, index) => message.role === "user" ? (
            <div className="user-message" key={`${message.role}-${index}`}>{message.text}</div>
          ) : message.response ? <MessageCard message={message.response} onSuggestedQuestion={onSend} isLatest={index===messages.length-1} onVoiceSpeaking={(speaking)=>onVoiceActivity(speaking?"speaking":"idle")} key={message.response.message_id} /> : null)}
          {busy && <div className="thinking-message" role="status"><span className="activity-icon"><Bot size={15} /></span><span><strong>BusinessAgent</strong>Analyzing your request<span className="thinking-dots" aria-hidden="true">…</span></span></div>}
        </section>
      )}

      {showChat && showJumpToLatest && <button className="jump-latest" type="button" onClick={jumpToLatest}><ArrowDown size={16} /> Jump to latest</button>}

      {view === "history" && (
        <section className="content-panel" aria-labelledby="history-title">
          <div className="panel-heading"><MessageSquare /><div><p>Workspace</p><h1 id="history-title">Chat History</h1></div></div>
          {historyError && <p className="history-error" role="alert">{historyError}</p>}
          {historyBusy && !conversationHistory.length ? <p className="empty-copy">Loading conversations…</p> : conversationHistory.length ? (
            <div className="history-table-wrap"><table className="history-table">
              <thead><tr><th>Conversation</th><th>Messages</th><th>Last activity</th></tr></thead>
              <tbody>{conversationHistory.map((conversation) => (
                <tr key={conversation.id}>
                  <td><button type="button" onClick={() => onOpenConversation(conversation.id)}>{conversation.title}</button></td>
                  <td>{conversation.message_count}</td>
                  <td><time dateTime={conversation.updated_at}>{new Date(conversation.updated_at).toLocaleString([], { dateStyle: "medium", timeStyle: "short" })}</time></td>
                </tr>
              ))}</tbody>
            </table></div>
          ) : <p className="empty-copy">Your previous conversations will appear here.</p>}
        </section>
      )}

      {view === "documents" && (
        <section className="content-panel" aria-labelledby="documents-title">
          <div className="panel-heading"><FileText /><div><p>Knowledge base</p><h1 id="documents-title">Documents</h1></div></div>
          <div className="document-dropzone"><FileText /><h2>Your business documents</h2><p>Documents connected to the copilot will appear here.</p></div>
        </section>
      )}

      {view === "copilot" && (
        <section className="command-dock" aria-label="Business copilot prompt">
          <Composer key={composerKey} busy={busy} onSend={onSend} onVoiceCommand={(text)=>onSend(text,true)} onVoiceState={voiceInputState} />
          {preferences.wakePhrase&&<span className={`wake-indicator ${wake.active?"is-active":""}`} title={wake.error||"Wake phrase works while this tab remains open."}>{wake.error||"Hey Agent enabled"}</span>}
          {status && <p className="status">{status}</p>}
        </section>
      )}
    </main>
  );
}
