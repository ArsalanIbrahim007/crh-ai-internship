import { FormEvent, useEffect, useRef, useState } from "react";
import { Search, SendHorizontal } from "lucide-react";
import { KpiCard } from "../components/analytics/KpiCard";
import { ChartRenderer } from "../components/analytics/ChartRenderer";
import { AlertPanel } from "../components/manager/AlertPanel";
import { BriefingPanel } from "../components/manager/BriefingPanel";
import { fetchAnalyticsOverview, queryAnalytics } from "../lib/api";
import type { AnalyticsResult } from "../types/contracts";
import "./workspace.css";
import "./analytics.css";

const QUICK_FILTERS = [
  "Total revenue by region",
  "Orders by product",
  "Gross margin trend",
  "Top products by revenue",
];

const EMPTY_RESULT: AnalyticsResult = {
  kpis: [],
  chart_spec: { type: "none", title: "", x_key: null, y_keys: [], rows: [] },
  insights: [],
  recommendations: [],
};

export function AnalyticsPage() {
  const [result, setResult] = useState<AnalyticsResult>(EMPTY_RESULT);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [question, setQuestion] = useState("");
  const [activeQuestion, setActiveQuestion] = useState<string | null>(null);
  const requestId = useRef(0);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");
    fetchAnalyticsOverview(controller.signal)
      .then((data) => setResult(data))
      .catch((err) => {
        if (!controller.signal.aborted) setError(err instanceof Error ? err.message : "Overview could not be loaded.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, []);

  async function runQuery(text: string) {
    const trimmed = text.trim();
    if (!trimmed || loading) return;
    const epoch = ++requestId.current;
    setLoading(true);
    setError("");
    setActiveQuestion(trimmed);
    try {
      const data = await queryAnalytics(trimmed);
      if (requestId.current !== epoch) return;
      setResult(data);
    } catch (err) {
      if (requestId.current === epoch) setError(err instanceof Error ? err.message : "That question could not be answered.");
    } finally {
      if (requestId.current === epoch) setLoading(false);
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    void runQuery(question);
    setQuestion("");
  }

  return (
    <main className="workspace-page analytics-page">
      <div className="workspace-page__surface">
        <header className="workspace-page__header">
          <div>
            <h1>Analytics</h1>
            <p>Ask a business question, or browse the baseline KPIs and trends.</p>
          </div>
        </header>

        <section className="analytics-page__content workspace-scroll" aria-label="Analytics workspace">
          <form className="analytics-page__query" onSubmit={onSubmit}>
            <Search aria-hidden="true" />
            <input
              type="text"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="Ask a question, e.g. “total revenue by region”"
              aria-label="Ask a business question"
            />
            <button type="submit" className="workspace-page__button workspace-page__button--primary" disabled={!question.trim() || loading}>
              <SendHorizontal aria-hidden="true" /> Ask
            </button>
          </form>

          <div className="analytics-page__filters" role="group" aria-label="Quick filters">
            {QUICK_FILTERS.map((filter) => (
              <button
                key={filter}
                type="button"
                className={`analytics-page__filter ${activeQuestion === filter ? "active" : ""}`}
                onClick={() => void runQuery(filter)}
                disabled={loading}
              >
                {filter}
              </button>
            ))}
            {activeQuestion && (
              <button
                type="button"
                className="analytics-page__filter analytics-page__filter--reset"
                onClick={() => {
                  setActiveQuestion(null);
                  setLoading(true);
                  setError("");
                  fetchAnalyticsOverview()
                    .then((data) => setResult(data))
                    .catch((err) => setError(err instanceof Error ? err.message : "Overview could not be loaded."))
                    .finally(() => setLoading(false));
                }}
                disabled={loading}
              >
                Reset to overview
              </button>
            )}
          </div>

          {error && (
            <p className="workspace-page__notice" role="alert">
              {error}
            </p>
          )}

          {loading && result.kpis.length === 0 ? (
            <p role="status">Loading analytics…</p>
          ) : (
            <>
              {result.kpis.length > 0 && (
                <div className="kpi-grid analytics-page__kpis">
                  {result.kpis.map((kpi) => (
                    <KpiCard key={kpi.key} kpi={kpi} />
                  ))}
                </div>
              )}

              <ChartRenderer spec={result.chart_spec} />

              {(result.insights.length > 0 || result.recommendations.length > 0) && (
                <div className="analytics-page__notes">
                  {result.insights.length > 0 && (
                    <div className="analytics-page__note-block">
                      <h3>Insights</h3>
                      <ul>
                        {result.insights.map((insight, index) => (
                          <li key={index}>{insight}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {result.recommendations.length > 0 && (
                    <div className="analytics-page__note-block">
                      <h3>Recommendations</h3>
                      <ul>
                        {result.recommendations.map((recommendation, index) => (
                          <li key={index}>{recommendation}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </>
          )}

          <div className="analytics-page__manager-grid">
            <AlertPanel />
            <BriefingPanel />
          </div>
        </section>
      </div>
    </main>
  );
}
