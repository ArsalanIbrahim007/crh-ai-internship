import { useEffect, useState } from "react";
import {
  Bell,
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  Clock,
  Link2,
  Users,
} from "lucide-react";
import type { AppView } from "../App";
import { WorkspaceDialog } from "../components/workspace/WorkspaceControls";
import {
  connectionAction,
  dateKey,
  listCalendarEvents,
  monthDays,
  type CalendarEvent,
} from "../lib/workspace";
import { useIntegrations } from "../lib/useIntegrations";
import {
  END_HOUR,
  START_HOUR,
  eventsOnDay,
  timedLayout,
} from "../lib/calendarLayout";
import "./workspace.css";
const hours = Array.from(
  { length: END_HOUR - START_HOUR },
  (_, index) => START_HOUR + index,
);
const midnight = (date: Date) =>
  new Date(date.getFullYear(), date.getMonth(), date.getDate());
const addDays = (date: Date, count: number) =>
  new Date(date.getFullYear(), date.getMonth(), date.getDate() + count);
const eventTime = (event: CalendarEvent) =>
  event.start.length === 10
    ? "All day"
    : `${new Date(event.start).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })} – ${new Date(event.end).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}`;
export function CalendarPage({
  onNavigate,
}: {
  onNavigate: (view: AppView) => void;
}) {
  const connection = useIntegrations();
  const provider = connection.integrations.find(
    (integration) => integration.provider === "google-calendar",
  );
  const connected = provider?.state === "connected" && !connection.error;
  const [selected, setSelected] = useState(() => midnight(new Date())),
    [month, setMonth] = useState(() => new Date());
  const [now, setNow] = useState(() => new Date()),
    [events, setEvents] = useState<CalendarEvent[]>([]);
  const [loading, setLoading] = useState(false),
    [error, setError] = useState(""),
    [revision, setRevision] = useState(0);
  const [connecting, setConnecting] = useState(false),
    [connectError, setConnectError] = useState("");
  const [opened, setOpened] = useState<CalendarEvent | null>(null),
    [outside, setOutside] = useState<CalendarEvent[] | null>(null);
  const first = selected;
  const start = dateKey(first),
    end = dateKey(addDays(first, 1));
  const days = [first];
  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 30000);
    return () => clearInterval(timer);
  }, []);
  useEffect(() => {
    if (!connected) {
      setEvents([]);
      setOpened(null);
      setOutside(null);
      return;
    }
    const controller = new AbortController();
    setLoading(true);
    setError("");
    setEvents([]);
    listCalendarEvents(
      new Date(`${start}T00:00:00`),
      new Date(`${end}T00:00:00`),
      controller.signal,
    )
      .then(setEvents)
      .catch((error) => {
        if (!controller.signal.aborted) {
          setError(error.message);
          connection.refresh();
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [connected, start, end, revision, connection.refresh]);
  function select(date: Date) {
    setSelected(midnight(date));
    setMonth(date);
  }
  async function connect() {
    setConnecting(true);
    setConnectError("");
    try {
      await connectionAction("google-calendar", "connect");
      connection.refresh();
    } catch (error) {
      setConnectError((error as Error).message);
    } finally {
      setConnecting(false);
    }
  }
  return (
    <main className="workspace-page calendar-page">
      <div className="workspace-page__surface">
        <header className="workspace-page__header">
          <div>
            <h1>Calendar</h1>
            <p>Your schedule, with room to focus.</p>
          </div>
        </header>
        {connection.loading && !connection.integrations.length ? (
          <div className="workspace-page__empty" role="status">
            Loading connection status…
          </div>
        ) : connection.error ? (
          <div className="workspace-page__empty" role="alert">
            <h2>Couldn’t load Calendar</h2>
            <p>{connection.error}</p>
            <button
              className="workspace-page__button"
              onClick={connection.refresh}
            >
              Retry
            </button>
          </div>
        ) : !connected ? (
          <div className="calendar-page__connection">
            <span className="calendar-page__connection-icon">
              <CalendarDays size={38} />
            </span>
            <h2>Connect Google Calendar</h2>
            <p>
              Connect your Google Calendar to view your schedule, check
              availability and manage meetings with your AI assistant.
            </p>
            <button
              className="workspace-page__button workspace-page__button--primary"
              disabled={connecting}
              onClick={() => void connect()}
            >
              <Link2 size={18} />
              {connecting ? "Connecting…" : "Connect Google Calendar"}
            </button>
            <button
              className="calendar-page__manage"
              onClick={() => onNavigate("connections")}
            >
              Manage connections
            </button>
            {provider?.message && (
              <p className="calendar-page__setup">{provider.message}</p>
            )}
            {connectError && <p role="alert">{connectError}</p>}
          </div>
        ) : (
          <div className="calendar-page__layout">
            <aside
              className="calendar-page__sidebar"
              aria-label="Calendar navigation"
            >
              <div className="calendar-page__mini-heading">
                <strong>
                  {month.toLocaleDateString(undefined, {
                    month: "short",
                    year: "numeric",
                  })}
                </strong>
                <button
                  aria-label="Previous mini calendar month"
                  onClick={() =>
                    setMonth(
                      new Date(month.getFullYear(), month.getMonth() - 1, 1),
                    )
                  }
                >
                  <ChevronLeft size={17} />
                </button>
                <button
                  aria-label="Next mini calendar month"
                  onClick={() =>
                    setMonth(
                      new Date(month.getFullYear(), month.getMonth() + 1, 1),
                    )
                  }
                >
                  <ChevronRight size={17} />
                </button>
              </div>
              <div className="calendar-page__mini">
                {["S", "M", "T", "W", "T", "F", "S"].map((label, index) => (
                  <span key={index}>{label}</span>
                ))}
                {monthDays(month).map((day) => (
                  <button
                    key={dateKey(day)}
                    className={`${dateKey(day) === dateKey(selected) ? "is-selected" : ""} ${day.getMonth() !== month.getMonth() ? "is-outside" : ""}`}
                    aria-label={`Select ${day.toLocaleDateString()}`}
                    aria-pressed={dateKey(day) === dateKey(selected)}
                    onClick={() => select(day)}
                  >
                    {day.getDate()}
                  </button>
                ))}
              </div>
            </aside>
            <section className="calendar-page__main" aria-label="Schedule">
              {(loading || error) && (
                <div
                  className="calendar-page__status"
                  role={error ? "alert" : "status"}
                >
                  {loading ? "Loading calendar events…" : (
                  <>
                    Couldn’t load Calendar. {error}{" "}
                    <button onClick={() => setRevision((value) => value + 1)}>
                      Retry
                    </button>
                  </>
                  )}
                </div>
              )}
              <div
                className="calendar-page__all-day"
                style={{
                  gridTemplateColumns: `48px repeat(${days.length}, minmax(0, 1fr))`,
                }}
              >
                <span>All day</span>
                {days.map((day) => {
                  const items = eventsOnDay(events, day);
                  const other = items.filter(
                    (event) =>
                      event.start.length === 10 ||
                      !timedLayout([event], day).length,
                  );
                  return (
                    <div key={dateKey(day)}>
                      {other.length > 0 && (
                        <button onClick={() => setOutside(other)}>
                          {other.length} all-day / outside hours
                        </button>
                      )}
                    </div>
                  );
                })}
              </div>
              <div
                className="calendar-page__time-grid"
                style={{
                  gridTemplateColumns: `48px repeat(${days.length}, minmax(0, 1fr))`,
                }}
              >
                <div className="calendar-page__hours">
                  {hours.map((hour) => (
                    <span key={hour}>{String(hour).padStart(2, "0")}:00</span>
                  ))}
                </div>
                {days.map((day) => {
                  const dayEvents = eventsOnDay(events, day);
                  const current =
                    ((now.getHours() + now.getMinutes() / 60 - START_HOUR) /
                      (END_HOUR - START_HOUR)) *
                    100;
                  return (
                    <div
                      className="calendar-page__time-column"
                      key={dateKey(day)}
                      aria-label={day.toLocaleDateString()}
                    >
                      <div className="calendar-page__hour-lines">
                        {hours.map((hour) => (
                          <span key={hour} />
                        ))}
                      </div>
                      {timedLayout(dayEvents, day).map((item) => (
                        <button
                          className={`calendar-page__event calendar-page__event--${item.event.color}`}
                          key={item.event.id}
                          style={{
                            top: `${item.top}%`,
                            height: `${item.height}%`,
                            left: `${(item.column / item.columns) * 100}%`,
                            width: `calc(${100 / item.columns}% - 4px)`,
                          }}
                          title={`${item.event.title}, ${eventTime(item.event)}`}
                          onClick={() => setOpened(item.event)}
                        >
                          <strong>{item.event.title}</strong>
                          <span>{eventTime(item.event)}</span>
                        </button>
                      ))}
                      {dateKey(day) === dateKey(now) &&
                        current >= 0 &&
                        current <= 100 && (
                          <div
                            className="calendar-page__now"
                            aria-label={`Current time ${now.toLocaleTimeString()}`}
                            style={{ top: `${current}%` }}
                          >
                            <span />
                          </div>
                        )}
                    </div>
                  );
                })}
              </div>
            </section>
          </div>
        )}
        {(opened || outside) && (
          <WorkspaceDialog
            title={opened ? opened.title : "All-day and outside-hours events"}
            close={() => {
              setOpened(null);
              setOutside(null);
            }}
          >
            {opened ? (
              <>
                <p>{opened.location}</p>
                <ul className="calendar-page__event-details">
                  <li>
                    <Clock size={19} />
                    {eventTime(opened)}
                  </li>
                  <li>
                    <Users size={19} />
                    {opened.attendees.length} attendees
                  </li>
                  {opened.reminder && (
                    <li>
                      <Bell size={19} />
                      {opened.reminder}
                    </li>
                  )}
                </ul>
                {opened.agenda && <p>{opened.agenda}</p>}
                <div className="calendar-page__attendees">
                  {opened.attendees.slice(0, 4).map((person, index) => (
                    <span key={index} title={person}>
                      {person.slice(0, 2).toUpperCase()}
                    </span>
                  ))}
                  {opened.attendees.length > 4 && (
                    <span>+{opened.attendees.length - 4}</span>
                  )}
                </div>
              </>
            ) : (
              outside?.map((event) => (
                <button
                  className="calendar-page__outside-event"
                  key={event.id}
                  onClick={() => setOpened(event)}
                >
                  {event.title}
                  <span>{eventTime(event)}</span>
                </button>
              ))
            )}
          </WorkspaceDialog>
        )}
      </div>
    </main>
  );
}
