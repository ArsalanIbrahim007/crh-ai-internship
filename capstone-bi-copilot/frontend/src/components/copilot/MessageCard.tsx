import { Bot, Check, Copy, LoaderCircle, Square, Volume2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { ChatResponse } from "../../types/contracts";
import { ContentBlockRenderer } from "./ContentBlockRenderer";
import { useVoicePlayback } from "../../lib/useVoicePlayback";
import { useVoicePreferences } from "../../lib/voicePreferences";

interface MessageCardProps {
  message: ChatResponse;
  onSuggestedQuestion: (question: string) => void;
  isLatest?: boolean;
  onVoiceSpeaking?: (speaking:boolean)=>void;
}

export function MessageCard({ message, onSuggestedQuestion, isLatest=false, onVoiceSpeaking }: MessageCardProps) {
  const [copied, setCopied] = useState(false);
  const {preferences}=useVoicePreferences();
  const playback=useVoicePlayback(onVoiceSpeaking);
  const autoPlayed=useRef(false);
  useEffect(()=>{if(isLatest&&preferences.replies&&!message.requires_approval&&message.answer.length<=500&&!autoPlayed.current){autoPlayed.current=true;void playback.play(message.answer)}},[isLatest,message.answer,message.requires_approval,preferences.replies]);

  async function copyAnswer() {
    await navigator.clipboard.writeText(message.answer);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  }

  return (
    <article className={`assistant-message ${message.requires_approval ? "is-approval" : ""}`}>
      {!message.requires_approval && <div className="assistant-identity" aria-hidden="true"><Bot size={16} /></div>}
      <div className="assistant-content">
        <ContentBlockRenderer message={message} />
        <div className="message-actions">
          <button type="button" onClick={copyAnswer} aria-label="Copy response" title="Copy response">{copied ? <Check size={15} /> : <Copy size={15} />}{copied && <span>Copied</span>}</button>
          {!message.requires_approval&&<button type="button" onClick={()=>playback.state==="speaking"?playback.stop():void playback.play(message.answer)} aria-label={playback.state==="speaking"?"Stop speaking":"Play response aloud"} title={playback.error||"Voice reply"}>{playback.state==="loading"?<LoaderCircle size={15}/>:playback.state==="speaking"?<Square size={14}/>:<Volume2 size={15}/>}</button>}
          {playback.error&&<span className="voice-reply-error" role="status">{playback.error}</span>}
        </div>
      </div>
      {!message.requires_approval && message.suggested_questions.length > 0 && (
        <div className="suggested">
          {message.suggested_questions.map((question) => (
            <button key={question} type="button" onClick={() => onSuggestedQuestion(question)}>
              {question}
            </button>
          ))}
        </div>
      )}
    </article>
  );
}
