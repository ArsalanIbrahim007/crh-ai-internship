import { Brain, Mic, Paperclip, SendHorizontal, Sparkles } from "lucide-react";
import { FormEvent, useRef, useState } from "react";

interface ComposerProps {
  busy: boolean;
  onSend: (queryText: string, voiceMode: boolean) => void;
}

export function Composer({ busy, onSend }: ComposerProps) {
  const [text, setText] = useState("");
  const inputRef = useRef<HTMLTextAreaElement | null>(null);

  function submit(event: FormEvent) {
    event.preventDefault();
    const queryText = text.trim();
    if (!queryText || busy) return;
    onSend(queryText, false);
    setText("");
    inputRef.current?.focus();
  }

  return (
    <form className="composer" onSubmit={submit}>
      <textarea
        ref={inputRef}
        aria-label="Ask anything"
        placeholder="Ask me anything..."
        value={text}
        rows={2}
        disabled={busy}
        onChange={(event) => setText(event.target.value)}
      />
      <div className="composer-actions">
        <button type="button" disabled aria-label="Attach file">
          <Paperclip size={14} /> Attach
        </button>
        <button type="button" disabled aria-label="Deep think">
          <Brain size={14} /> Deep Think
        </button>
        <span className="composer-spacer" />
        <button type="button" disabled aria-label="Voice mode">
          <Sparkles size={14} /> Voice
        </button>
        <button type="submit" className="send-button" disabled={busy || !text.trim()}>
          {busy ? <Mic size={14} /> : <SendHorizontal size={14} />} Send
        </button>
      </div>
    </form>
  );
}
