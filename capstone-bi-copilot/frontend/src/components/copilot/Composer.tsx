import { ArrowUp, LoaderCircle, Mic, Square } from "lucide-react";
import { FormEvent, KeyboardEvent, useEffect, useRef, useState } from "react";
import { useVoiceInput, type VoiceInputState } from "../../lib/useVoiceInput";
import { useVoicePreferences } from "../../lib/voicePreferences";

interface ComposerProps {
  busy: boolean;
  onSend: (queryText: string) => void;
  onVoiceCommand?: (queryText:string)=>void;
  onVoiceState?: (state: VoiceInputState) => void;
}

const MAX_TEXTAREA_HEIGHT = 170;

export function Composer({ busy, onSend, onVoiceCommand, onVoiceState }: ComposerProps) {
  const [text, setText] = useState("");
  const inputRef = useRef<HTMLTextAreaElement | null>(null);
  const {preferences}=useVoicePreferences();
  const voice=useVoiceInput((transcript)=>{setText(transcript);requestAnimationFrame(()=>inputRef.current&&resizeTextarea(inputRef.current));if(preferences.autoSend)(onVoiceCommand??onSend)(transcript)});
  useEffect(()=>onVoiceState?.(voice.state),[voice.state,onVoiceState]);

  function submit(event: FormEvent) {
    event.preventDefault();
    const queryText = text.trim();
    if (!queryText || busy) return;
    onSend(queryText);
    setText("");
    requestAnimationFrame(() => {
      if (!inputRef.current) return;
      resizeTextarea(inputRef.current);
      inputRef.current.focus();
    });
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    const nativeEvent = event.nativeEvent as KeyboardEvent<HTMLTextAreaElement>["nativeEvent"] & {
      isComposing?: boolean;
    };
    if (nativeEvent.isComposing || nativeEvent.keyCode === 229) return;
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      event.currentTarget.form?.requestSubmit();
    }
  }

  function onTextChange(value: string, textarea: HTMLTextAreaElement) {
    setText(value);
    resizeTextarea(textarea);
  }

  return (
    <form className="composer" onSubmit={submit}>
      <textarea
        ref={inputRef}
        aria-label="Ask anything about your business"
        placeholder="Ask about your business..."
        value={text}
        rows={1}
        onChange={(event) => onTextChange(event.target.value, event.currentTarget)}
        onKeyDown={onKeyDown}
      />
      <button type="button" className={`voice-button is-${voice.state}`} disabled={busy||voice.state==="processing"||!preferences.commands} aria-label={voice.state==="listening"?"Stop listening":"Start voice input"} title={voice.state==="listening"?"Stop listening":"Voice input"} onClick={()=>voice.state==="listening"?voice.stop():void voice.start()}>{voice.state==="processing"?<LoaderCircle size={18}/>:voice.state==="listening"?<Square size={16}/>:<Mic size={18}/>}</button>
      <button type="submit" className="send-button" disabled={busy || !text.trim()} aria-label="Send message" title="Send">
        <ArrowUp size={20} />
      </button>
      {(voice.state==="listening"||voice.error)&&<span className={`voice-caption ${voice.error?"is-error":""}`} role="status">{voice.error||"Listening…"}</span>}
    </form>
  );
}

function resizeTextarea(textarea: HTMLTextAreaElement) {
  textarea.style.height = "auto";
  const nextHeight = Math.min(textarea.scrollHeight, MAX_TEXTAREA_HEIGHT);
  textarea.style.height = `${nextHeight}px`;
  textarea.style.overflowY = textarea.scrollHeight > MAX_TEXTAREA_HEIGHT ? "auto" : "hidden";
}
