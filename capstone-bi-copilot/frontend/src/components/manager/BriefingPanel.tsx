import { useEffect, useState } from "react";
import { Newspaper, RefreshCw } from "lucide-react";
import { fetchBriefing } from "../../lib/api";
import type { Briefing } from "../../types/contracts";

export function BriefingPanel() {
  const [briefing, setBriefing] = useState<Briefing | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");
    fetchBriefing(controller.signal)
      .then((result) => setBriefing(result))
      .catch((err) => {
        if (!controller.signal.aborted) setError(err instanceof Error ? err.message : "Briefing could not be loaded.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [revision]);

  return (
    <section className="manager-panel briefing-panel" aria-label="Daily executive briefing">
      <header className="manager-panel__header">
        <h2>
          <Newspaper aria-hidden="true" /> Daily Briefing
        </h2>
        <button type="button" className="manager-panel__refresh" aria-label="Refresh briefing" onClick={() => setRevision((value) => value + 1)}>
          <RefreshCw aria-hidden="true" />
        </button>
      </header>

      {loading ? (
        <p className="manager-panel__status" role="status">Compiling briefing…</p>
      ) : error ? (
        <div className="manager-panel__empty" role="alert">
          <p>{error}</p>
          <button className="workspace-page__button" onClick={() => setRevision((value) => value + 1)}>Retry</button>
        </div>
      ) : briefing ? (
        <div className="briefing-panel__body">
          <p className="briefing-panel__date">{briefing.date}</p>

          {briefing.kpis.length > 0 && (
            <div className="briefing-panel__kpis">
              {briefing.kpis.map((kpi) => (
                <div key={kpi.key} className="briefing-panel__kpi">
                  <span>{kpi.label}</span>
                  <strong>
                    {kpi.value}
                    {kpi.unit ? ` ${kpi.unit}` : ""}
                  </strong>
                </div>
              ))}
            </div>
          )}

          {briefing.alerts.length > 0 ? (
            <ul className="briefing-panel__alerts">
              {briefing.alerts.map((alert) => (
                <li key={alert.alert_id}>
                  <strong>{alert.title}:</strong> {alert.message}
                </li>
              ))}
            </ul>
          ) : (
            <p className="manager-panel__status manager-panel__status--ok">No active alerts today.</p>
          )}
        </div>
      ) : null}
    </section>
  );
}
