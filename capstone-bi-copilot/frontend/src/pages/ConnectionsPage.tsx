import { useState } from "react";
import { Ellipsis } from "lucide-react";
import { WorkspaceDialog } from "../components/workspace/WorkspaceControls";
import { connectionAction, type Integration } from "../lib/workspace";
import { useIntegrations } from "../lib/useIntegrations";
import "./workspace.css";
const labels = {
  not_connected: "Not connected",
  connecting: "Connecting…",
  connected: "Connected",
  error: "Connection error",
  needs_reauthorization: "Needs reauthorization",
};
export function ConnectionsPage() {
  const { integrations, loading, error, refresh } = useIntegrations();
  const [pending, setPending] = useState<string | null>(null),
    [actionError, setActionError] = useState("");
  const [pendingAction, setPendingAction] = useState("Connecting…");
  const [openMenu, setOpenMenu] = useState<string | null>(null);
  const [dialog, setDialog] = useState<{
    integration: Integration;
    action: "manage" | "disconnect";
  } | null>(null);
  const oauthResult = new URLSearchParams(window.location.search).get("oauth");
  async function act(
    integration: Integration,
    action: "connect" | "disconnect",
  ) {
    setPending(integration.provider);
    setPendingAction(action === "disconnect" ? "Disconnecting…" : "Connecting…");
    setActionError("");
    try {
      await connectionAction(integration.provider, action);
      setDialog(null);
      refresh();
    } catch (error) {
      setActionError((error as Error).message);
    } finally {
      setPending(null);
    }
  }
  return (
    <main className="workspace-page connections-page">
      <div className="workspace-page__surface">
        <header className="workspace-page__header">
          <div>
            <h1>Connections</h1>
            <p>Bring your business services into your workspace.</p>
          </div>
        </header>
        <section
          className="connections-page__content workspace-scroll"
          aria-label="Available integrations"
        >
          {oauthResult === "connected" && (
            <p className="workspace-page__notice" role="status">
              Google account connected successfully.
            </p>
          )}
          {oauthResult === "error" && (
            <p className="workspace-page__notice" role="alert">
              Google authorization was not completed. Please try connecting again.
            </p>
          )}
          {loading && !integrations.length ? (
            <p role="status">Checking integrations…</p>
          ) : error ? (
            <div className="workspace-page__empty" role="alert">
              <h2>Couldn’t retrieve connection status.</h2>
              <p>{error}</p>
              <button className="workspace-page__button" onClick={refresh}>
                Retry
              </button>
            </div>
          ) : (
            <>
              <div className="connections-page__grid">
                {integrations.map((integration) => (
                  <article
                    className="connections-page__card"
                    key={integration.provider}
                  >
                    <span className="connections-page__icon" aria-hidden="true">
                      {integration.provider === "gmail" ? <GmailMark /> : <CalendarMark />}
                    </span>
                    <div className="connections-page__card-body">
                      <div className="connections-page__card-title">
                        <div><h2>{integration.name}</h2><span className="connections-page__category">{integration.provider === "gmail" ? "Communication" : "Productivity"}</span></div>
                        <div className="connections-page__menu-wrap">
                          <button className="connections-page__menu-button" type="button" aria-label={`${integration.name} options`} aria-expanded={openMenu === integration.provider} onClick={() => setOpenMenu(openMenu === integration.provider ? null : integration.provider)}><Ellipsis size={20} /></button>
                          {openMenu === integration.provider && integration.state === "connected" && <div className="connections-page__menu"><button type="button" onClick={() => { setOpenMenu(null); setDialog({ integration, action: "disconnect" }); }}>Disconnect</button></div>}
                        </div>
                      </div>
                      <p className="connections-page__description">{integration.provider === "gmail" ? "Search, summarize, and draft emails with AI. Send emails with your approval." : "View your schedule, check availability, and manage meetings with AI."}</p>
                      <span className={`connections-page__status connections-page__status--${integration.state}`} role="status">
                        <i aria-hidden="true" />{pending === integration.provider ? pendingAction : labels[integration.state]}
                      </span>
                      {!integration.configured && <p className="connections-page__setup">Google OAuth is not configured.</p>}
                      {integration.configured && integration.state === "needs_reauthorization" && integration.missing_scopes?.length ? <p className="connections-page__setup">{integration.provider === "gmail" ? "Gmail needs permission to send email." : "Google Calendar needs permission to create events."}</p> : null}
                    </div>
                    <div className="connections-page__actions">
                      {integration.state === "connected" ? (
                        <button className="workspace-page__button" disabled={Boolean(pending)} onClick={() => setDialog({ integration, action: "manage" })}>Manage</button>
                      ) : (
                        <button
                          className="workspace-page__button workspace-page__button--primary"
                          disabled={Boolean(pending)}
                          onClick={() => void act(integration, "connect")}
                        >
                          {pending === integration.provider
                            ? "Connecting…"
                            : integration.state === "needs_reauthorization" ||
                                integration.state === "error"
                              ? "Reconnect"
                              : "Connect"}
                        </button>
                      )}
                    </div>
                  </article>
                ))}
              </div>
              <p className="connections-page__approval-note">
                Calendar changes and sending email require your approval.
                Connecting a service does not approve these actions.
              </p>
            </>
          )}
          {actionError && (
            <p className="workspace-page__notice" role="alert">
              {actionError}
            </p>
          )}
        </section>
        {dialog && (
          <WorkspaceDialog
            title={
              dialog.action === "disconnect"
                ? `Disconnect ${dialog.integration.name}?`
                : dialog.integration.name
            }
            close={() => {
              if (!pending) setDialog(null);
            }}
          >
            <p>
              {dialog.action === "disconnect"
                ? "Your calendar or email data will no longer be available to this workspace. This does not delete data from Google."
                : `${dialog.integration.account ?? "Connected account"} · ${labels[dialog.integration.state]}`}
            </p>
            {dialog.action === "disconnect" && (
              <div className="workspace-dialog__actions">
                <button
                  disabled={Boolean(pending)}
                  onClick={() => setDialog(null)}
                >
                  Cancel
                </button>
                <button
                  disabled={Boolean(pending)}
                  onClick={() => void act(dialog.integration, "disconnect")}
                >
                  {pending ? "Disconnecting…" : "Disconnect"}
                </button>
              </div>
            )}
            {actionError && <p role="alert">{actionError}</p>}
          </WorkspaceDialog>
        )}
      </div>
    </main>
  );
}

function CalendarMark() {
  return <svg viewBox="0 0 48 48"><path fill="#4285F4" d="M8 7h25l7 7v27H8z"/><path fill="#34A853" d="M8 31h32v10H8z"/><path fill="#FBBC04" d="M32 7h8v17h-8z"/><path fill="#EA4335" d="M8 7h24v8H8z"/><rect x="14" y="17" width="19" height="18" rx="2" fill="white"/><text x="23.5" y="31" textAnchor="middle" fontSize="16" fontWeight="700" fill="#4285F4">31</text></svg>;
}

function GmailMark() {
  return <svg viewBox="0 0 48 48"><path fill="#4285F4" d="M6 13v28h8V20z"/><path fill="#34A853" d="M34 20v21h8V13z"/><path fill="#EA4335" d="M6 13l5-5 13 10L37 8l5 5-18 14z"/><path fill="#FBBC04" d="M34 20l8-7v10l-8 6z"/><path fill="#C5221F" d="M6 13l8 7v9l-8-6z"/></svg>;
}
