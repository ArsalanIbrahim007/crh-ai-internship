import { dateKey, type CalendarEvent } from "./workspace";
export const START_HOUR = 8;
export const END_HOUR = 20;
export function eventsOnDay(events: CalendarEvent[], day: Date) {
  const next = new Date(day.getFullYear(), day.getMonth(), day.getDate() + 1);
  return events.filter((event) =>
    event.start.length === 10
      ? dateKey(day) >= event.start && dateKey(day) < event.end
      : new Date(event.start) < next && new Date(event.end) > day,
  );
}
export function timedLayout(events: CalendarEvent[], day: Date) {
  const start = new Date(
    day.getFullYear(),
    day.getMonth(),
    day.getDate(),
    START_HOUR,
  ).getTime();
  const end = new Date(
    day.getFullYear(),
    day.getMonth(),
    day.getDate(),
    END_HOUR,
  ).getTime();
  const range = end - start;
  const items = events
    .filter((event) => event.start.length > 10)
    .map((event) => ({
      event,
      start: Math.max(start, new Date(event.start).getTime()),
      end: Math.min(end, new Date(event.end).getTime()),
      column: 0,
      columns: 1,
    }))
    .filter((item) => item.end > item.start)
    .sort((a, b) => a.start - b.start || b.end - a.end);
  let group: typeof items = [],
    groupEnd = 0,
    columns: number[] = [];
  function finish() {
    group.forEach((item) => {
      item.columns = columns.length;
    });
  }
  for (const item of items) {
    if (item.start >= groupEnd) {
      finish();
      group = [];
      columns = [];
    }
    let column = columns.findIndex((end) => end <= item.start);
    if (column < 0) column = columns.length;
    columns[column] = item.end;
    item.column = column;
    group.push(item);
    groupEnd = Math.max(...group.map((item) => item.end));
  }
  finish();
  return items.map((item) => ({
    ...item,
    top: ((item.start - start) / range) * 100,
    height: ((item.end - item.start) / range) * 100,
  }));
}
