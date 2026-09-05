import { useCallback, useEffect, useState } from "react";
import { listIntegrations, type Integration } from "./workspace";
export function useIntegrations() {
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  const refresh = useCallback(() => setRevision((value) => value + 1), []);
  useEffect(() => {
    window.addEventListener("workspace-connections-changed", refresh);
    window.addEventListener("focus", refresh);
    const timer = window.setInterval(refresh, 30000);
    return () => {
      window.removeEventListener("workspace-connections-changed", refresh);
      window.removeEventListener("focus", refresh);
      clearInterval(timer);
    };
  }, [refresh]);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");
    listIntegrations(controller.signal)
      .then(setIntegrations)
      .catch((error) => {
        if (!controller.signal.aborted) {
          setError(error.message);
          setIntegrations([]);
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [revision]);
  return { integrations, loading, error, refresh };
}
