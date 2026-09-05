import { AlertCircle, BarChart3, CheckCircle2, Search } from "lucide-react";
import { useState } from "react";
import type { ChatResponse, ToolCall } from "../../types/contracts";
import { decideToolAction } from "../../lib/api";
import { ChartBlock } from "./ChartBlock";
import { MarkdownBlock } from "./MarkdownBlock";

interface ContentBlockRendererProps {
  message: ChatResponse;
}

export function ContentBlockRenderer({ message }: ContentBlockRendererProps) {
  return (
    <>
      <MarkdownBlock content={message.answer} />

      {message.error && <ErrorBlock error={message.error} />}

      {message.kpis.length > 0 && (
        <section className="kpi-grid" aria-label="Key metrics">
          {message.kpis.map((kpi) => <div className="kpi-item" key={kpi.key}><span>{kpi.label}</span><strong>{kpi.value}{kpi.unit ? ` ${kpi.unit}` : ""}</strong>{kpi.delta != null && <small>{kpi.delta > 0 ? "+" : ""}{kpi.delta}%</small>}</div>)}
        </section>
      )}

      <ChartBlock spec={message.chart_spec} />

      {message.insights.length > 0 && <ListBlock icon={<BarChart3 size={17} />} title="Key insights" items={message.insights} />}
      {message.recommendations.length > 0 && <ListBlock icon={<CheckCircle2 size={17} />} title="Recommendations" items={message.recommendations} ordered />}

      {message.forecast && (
        <details className="structured-block forecast-block">
          <summary>Forecast details</summary>
          <div className="table-scroll"><table><tbody>{Object.entries(message.forecast).map(([key, value]) => <tr key={key}><th>{key}</th><td>{typeof value === "object" ? JSON.stringify(value) : String(value)}</td></tr>)}</tbody></table></div>
        </details>
      )}

      {message.tool_calls.length > 0 && <ToolCalls calls={message.tool_calls} requiresApproval={message.requires_approval} messageId={message.message_id} />}
      {message.requires_approval && message.tool_calls.length === 0 && <ApprovalBlock />}

      {message.sources.length > 0 && (
        <section className="sources-block" aria-labelledby={`sources-${message.message_id}`}>
          <h3 id={`sources-${message.message_id}`}><Search size={16} /> Sources</h3>
          <ol>{message.sources.map((source) => <li key={source.source_id}>{source.location ? <a href={source.location} target="_blank" rel="noreferrer">{source.title}</a> : <strong>{source.title}</strong>}{source.snippet && <p>{source.snippet}</p>}</li>)}</ol>
        </section>
      )}
    </>
  );
}

function ListBlock({ icon, title, items, ordered = false }: { icon: React.ReactNode; title: string; items: string[]; ordered?: boolean }) {
  const List = ordered ? "ol" : "ul";
  return <section className="list-block"><h3>{icon}{title}</h3><List>{items.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}</List></section>;
}

function ToolCalls({ calls, requiresApproval, messageId }: { calls: ToolCall[]; requiresApproval: boolean; messageId: string }) {
  const [currentCalls, setCurrentCalls] = useState(calls);
  const [processing, setProcessing] = useState<"approve" | "cancel" | null>(null);
  const [requestError, setRequestError] = useState("");
  async function decide(decision: "approve" | "cancel") {
    setProcessing(decision); setRequestError("");
    try {
      const updated = await decideToolAction(messageId, decision);
      setCurrentCalls((items) => items.map((item, index) => index === 0 ? updated : item));
    } catch (error) {
      setRequestError(error instanceof Error ? error.message : "The action could not be processed.");
    } finally { setProcessing(null); }
  }
  if (!requiresApproval) return null;
  const call = currentCalls[0];
  const pending = call?.status === "proposed";
  const isEmail = call?.tool_name === "send_email";
  const isCalendar = call?.tool_name === "create_calendar_event";
  const details = Object.entries(call?.arguments ?? {}).filter(([key, value]) => !["start", "end", "request", "message"].includes(key) && value !== "");
  const rawStatus = processing === "approve" ? (isEmail ? "sending" : "creating") : call?.status ?? "proposed";
  const status = isEmail && rawStatus === "executed" ? "Sent" : isCalendar && rawStatus === "executed" ? "Created" : humanize(rawStatus);
  const actionName = isEmail ? "Email" : isCalendar ? "Calendar Event" : "External Action";
  const description = isEmail ? "Review the proposed email before sending." : isCalendar ? "Review the proposed calendar event before creation." : "Review the proposed agent action before execution.";
  const primaryLabel = isEmail ? "Send Email" : isCalendar ? "Create Event" : "Approve";
  return <section className="tool-block approval-block" aria-label="Approval required">
    <div className="block-heading"><div><strong>Approval required</strong><span>{description}</span></div></div>
    <div className="approval-action-heading"><strong>{actionName}</strong><small className={`approval-status is-${call?.status}`}>Status: {status}</small></div>
    {details.length > 0 && <dl className="approval-details">{details.map(([key, value]) => <div key={key}><dt>{humanize(key)}</dt><dd>{typeof value === "object" ? JSON.stringify(value) : String(value)}</dd></div>)}</dl>}
    {isEmail && typeof call.arguments.message === "string" && <div className="approval-message"><strong>Message</strong><p>{call.arguments.message}</p></div>}
    {(requestError || call?.error) && <p className="approval-error" role="alert">{requestError || call.error}</p>}
    {pending && <div className="approval-actions"><button type="button" disabled={Boolean(processing)} onClick={() => decide("cancel")}>Cancel</button><button className="is-primary" type="button" disabled={Boolean(processing)} onClick={() => decide("approve")}>{processing === "approve" ? (isEmail ? "Sending..." : isCalendar ? "Creating..." : "Approving...") : primaryLabel}</button></div>}
  </section>;
}

function ApprovalBlock() {
  return <section className="tool-block approval-block"><div className="block-heading"><div><strong>Approval required</strong><span>This request is waiting in the existing approval workflow.</span></div></div></section>;
}

function ErrorBlock({ error }: { error: Record<string, unknown> }) {
  const message = typeof error.message === "string" ? error.message : "The agent could not complete this step.";
  return <section className="error-block" role="alert"><AlertCircle size={18} /><div><strong>Request incomplete</strong><p>{message}</p><details><summary>View technical details</summary><dl>{Object.entries(error).filter(([key]) => key !== "message").map(([key, value]) => <div key={key}><dt>{humanize(key)}</dt><dd>{String(value)}</dd></div>)}</dl></details></div></section>;
}

function humanize(value: string) {
  return value.replace(/_/g, " ").replace(/\b\w/g, (character: string) => character.toUpperCase());
}
