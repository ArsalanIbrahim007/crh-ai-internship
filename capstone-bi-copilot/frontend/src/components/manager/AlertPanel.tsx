import { useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, RefreshCw, ShieldAlert } from "lucide-react";
import { fetchAlerts } from "../../lib/api";
import type { AlertItem } from "../../types/contracts";

export function AlertPanel() {
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");
    fetchAlerts(controller.signal)
      .then((items) => setAlerts(items))
      .catch((err) => {
        if (!controller.signal.aborted) setError(err instanceof Error ? err.message : "Alerts could not be loaded.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [revision]);

  return (
    <section className="manager-panel alert-panel" aria-label="Active alerts">
      <header className="manager-panel__header">
        <h2>
          <ShieldAlert aria-hidden="true" /> Alerts
        </h2>
        <button type="button" className="manager-panel__refresh" aria-label="Refresh alerts" onClick={() => setRevision((value) => value + 1)}>
          <RefreshCw aria-hidden="true" />
        </button>
      </header>

      {loading ? (
        <p className="manager-panel__status" role="status">Checking alerts…</p>
      ) : error ? (
        <div className="manager-panel__empty" role="alert">
          <p>{error}</p>
          <button className="workspace-page__button" onClick={() => setRevision((value) => value + 1)}>Retry</button>
        </div>
      ) : alerts.length === 0 ? (
        <p className="manager-panel__status manager-panel__status--ok">
          <CheckCircle2 aria-hidden="true" /> All monitored KPIs are within healthy thresholds.
        </p>
      ) : (
        <ul className="alert-panel__list">
          {alerts.map((alert) => (
            <li key={alert.alert_id} className={`alert-panel__item alert-panel__item--${alert.severity}`}>
              <AlertTriangle aria-hidden="true" />
              <div>
                <strong>{alert.title}</strong>
                <p>{alert.message}</p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
