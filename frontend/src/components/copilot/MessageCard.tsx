import type { ChatResponse } from "../../types/contracts";

interface MessageCardProps {
  message: ChatResponse;
}

export function MessageCard({ message }: MessageCardProps) {
  return (
    <article className="message-card">
      <p>{message.answer}</p>
      {message.sources.length > 0 && (
        <div className="sources">
          {message.sources.map((source) => (
            <span key={source.source_id}>{source.title}</span>
          ))}
        </div>
      )}
      {message.suggested_questions.length > 0 && (
        <div className="suggested">
          {message.suggested_questions.map((question) => (
            <button key={question} type="button">
              {question}
            </button>
          ))}
        </div>
      )}
    </article>
  );
}
