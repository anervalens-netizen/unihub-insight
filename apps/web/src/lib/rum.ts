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

function send(payload: WebVitalPayload): void {
  const body = new Blob([JSON.stringify(payload)], { type: 'application/json' });
  navigator.sendBeacon(`${environment.apiBaseUrl}/telemetry/web-vital`, body);
}

export async function initializeRum(): Promise<void> {
  if (!import.meta.env.PROD || import.meta.env.VITE_RUM_ENABLED === 'false') return;
  const { onINP, onLCP } = await import('web-vitals');
  const report = (metric: {
    name: string;
    value: number;
    rating: 'good' | 'needs-improvement' | 'poor';
    navigationType?: string;
  }): void => {
    if (metric.name !== 'LCP' && metric.name !== 'INP') return;
    const allowedNavigationTypes = new Set([
      'navigate',
      'reload',
      'back-forward',
      'back-forward-cache',
      'prerender',
      'restore',
    ]);
    const navigationType = allowedNavigationTypes.has(metric.navigationType ?? '')
      ? (metric.navigationType as WebVitalPayload['navigation_type'])
      : 'unknown';
    send({
      metric: metric.name,
      value_ms: metric.value,
      rating: metric.rating,
      navigation_type: navigationType,
    });
  };
  onLCP(report);
  onINP(report);
}
