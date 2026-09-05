import { Bot, CircleEllipsis, Plus, Search, TrendingUp, WalletCards } from "lucide-react";
import { useState } from "react";
import { Composer } from "../components/copilot/Composer";
import { MessageCard } from "../components/copilot/MessageCard";
import { OrbHero } from "../components/copilot/OrbHero";
import { sendChat } from "../lib/api";
import type { ChatResponse } from "../types/contracts";

interface LocalMessage {
  role: "user" | "assistant";
  text?: string;
  response?: ChatResponse;
}

const quickActions = [
  { label: "Market Update", icon: TrendingUp },
  { label: "Top Gainers", icon: Bot },
  { label: "My Portfolio", icon: WalletCards },
  { label: "Trending Tokens", icon: Search },
];

export function CopilotPage() {
  const [messages, setMessages] = useState<LocalMessage[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);

  async function onSend(queryText: string, voiceMode: boolean) {
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
      setConversationId(response.conversation_id);
      setMessages((items) => [...items, { role: "assistant", response }]);
      if (response.error) setStatus("I could not complete that request. Please try again.");
    } catch {
      setStatus("I could not complete that request. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  const hasChat = messages.length > 0;

  return (
    <main className={`copilot-page ${hasChat ? "chat-mode" : ""}`}>
      <header className="topbar">
        <span />
        <button className="wallet-button" type="button">
          <Plus size={14} /> Connect Wallet
        </button>
      </header>

      {!hasChat && (
        <>
          <h1>
            <span>AI Powers</span> Easy Wallet <span>And</span>
            <br />
            Voice Access
          </h1>
          <OrbHero />
        </>
      )}

      {hasChat && (
        <section className="messages" aria-live="polite">
          {messages.map((message, index) =>
            message.role === "user" ? (
              <div className="user-message" key={`${message.role}-${index}`}>
                {message.text}
              </div>
            ) : message.response ? (
              <MessageCard message={message.response} key={message.response.message_id} />
            ) : null,
          )}
        </section>
      )}

      <section className="command-dock">
        <div className="quick-actions">
          {quickActions.map(({ label, icon: Icon }) => (
            <button type="button" key={label}>
              <Icon size={14} /> {label}
            </button>
          ))}
          <button type="button" aria-label="More options">
            <CircleEllipsis size={16} />
          </button>
        </div>
        <Composer busy={busy} onSend={onSend} />
        {status && <p className="status">{status}</p>}
      </section>
    </main>
  );
}
