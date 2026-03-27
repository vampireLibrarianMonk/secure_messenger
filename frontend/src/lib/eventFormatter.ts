export interface SyntheticEvent {
  id: string;
  timestamp: string;
  label: string;
  status: "inactive" | "queued" | "active" | "completed" | "warning" | "failed" | "unknown";
}

export interface SyntheticLogLine {
  timestamp: string;
  level: "INFO" | "WARN" | "ERROR";
  text: string;
}

export type ConsoleLifecycleState = "idle" | "running" | "completed" | "failed" | "unknown";

export function createSyntheticEvents(steps: string[]): SyntheticEvent[] {
  return steps.map((step, index) => ({
    id: `${step}-${index + 1}`,
    timestamp: new Date(Date.now() + index * 700).toISOString(),
    label: `STEP ${index + 1}: ${step}`,
    status: index === 0 ? "active" : "inactive",
  }));
}

export function createSyntheticLogLines(events: SyntheticEvent[]): SyntheticLogLine[] {
  return events.map((event) => ({
    timestamp: event.timestamp,
    level: event.status === "active" ? "INFO" : "WARN",
    text: `${event.label} => ${event.status}`,
  }));
}

export function markEventStatus(
  events: SyntheticEvent[],
  index: number,
  status: SyntheticEvent["status"],
): SyntheticEvent[] {
  return events.map((event, i) => (i === index ? { ...event, status, timestamp: new Date().toISOString() } : event));
}
