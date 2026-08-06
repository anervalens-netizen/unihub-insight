import { environment } from './environment';

interface WebVitalPayload {
  metric: 'LCP' | 'INP';
  value_ms: number;
  rating: 'good' | 'needs-improvement' | 'poor';
  navigation_type:
    | 'navigate'
    | 'reload'
    | 'back-forward'
    | 'back-forward-cache'
    | 'prerender'
    | 'restore'
    | 'unknown';
}

interface InteractionTimingEntry extends PerformanceEntry {
  duration: number;
  interactionId: number;
}

function send(payload: WebVitalPayload): void {
  const body = new Blob([JSON.stringify(payload)], { type: 'application/json' });
  navigator.sendBeacon(`${environment.apiBaseUrl}/telemetry/web-vital`, body);
}

function navigationType(): WebVitalPayload['navigation_type'] {
  const navigation = performance.getEntriesByType('navigation')[0] as
    | PerformanceNavigationTiming
    | undefined;
  if (!navigation) return 'unknown';
  if (navigation.type === 'navigate' || navigation.type === 'reload') return navigation.type;
  if (navigation.type === 'back_forward') return 'back-forward';
  return 'unknown';
}

function rating(metric: WebVitalPayload['metric'], value: number): WebVitalPayload['rating'] {
  if (metric === 'LCP') {
    if (value <= 2_500) return 'good';
    if (value <= 4_000) return 'needs-improvement';
    return 'poor';
  }
  if (value <= 200) return 'good';
  if (value <= 500) return 'needs-improvement';
  return 'poor';
}

function observeLcp(): void {
  let latest = 0;
  let flushed = false;
  const observer = new PerformanceObserver((list) => {
    const entry = list.getEntries().at(-1);
    if (entry) latest = entry.startTime;
  });
  try {
    observer.observe({ type: 'largest-contentful-paint', buffered: true });
  } catch {
    return;
  }
  const flush = (): void => {
    if (flushed) return;
    flushed = true;
    if (latest > 0) {
      send({
        metric: 'LCP',
        value_ms: latest,
        rating: rating('LCP', latest),
        navigation_type: navigationType(),
      });
      latest = 0;
    }
    observer.disconnect();
  };
  document.addEventListener(
    'visibilitychange',
    () => {
      if (document.visibilityState === 'hidden') flush();
    },
    { once: true },
  );
  window.addEventListener('pagehide', flush, { once: true });
}

function observeInp(): void {
  const interactions = new Map<number, number>();
  let flushed = false;
  const observer = new PerformanceObserver((list) => {
    for (const rawEntry of list.getEntries()) {
      const entry = rawEntry as InteractionTimingEntry;
      if (entry.interactionId <= 0) continue;
      interactions.set(
        entry.interactionId,
        Math.max(interactions.get(entry.interactionId) ?? 0, entry.duration),
      );
    }
  });
  try {
    observer.observe({ type: 'event', buffered: true });
  } catch {
    return;
  }
  const flush = (): void => {
    if (flushed) return;
    flushed = true;
    const value = Math.max(0, ...interactions.values());
    if (value > 0) {
      send({
        metric: 'INP',
        value_ms: value,
        rating: rating('INP', value),
        navigation_type: navigationType(),
      });
    }
    observer.disconnect();
  };
  document.addEventListener(
    'visibilitychange',
    () => {
      if (document.visibilityState === 'hidden') flush();
    },
    { once: true },
  );
  window.addEventListener('pagehide', flush, { once: true });
}

export async function initializeRum(): Promise<void> {
  const { VITE_RUM_ENABLED } = import.meta.env;
  if (!import.meta.env.PROD || VITE_RUM_ENABLED === 'false') return;
  observeLcp();
  observeInp();
}
