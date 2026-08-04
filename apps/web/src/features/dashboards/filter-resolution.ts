import type { GlobalSearch } from '../../lib/search';
import type { DashboardWidget } from './schemas';

const BUSINESS_KEYS = ['firm', 'regional', 'asm', 'stores', 'agent'] as const;
type BusinessKey = (typeof BUSINESS_KEYS)[number];

function localFilters(widget: DashboardWidget): Partial<Record<BusinessKey, string>> {
  const result: Partial<Record<BusinessKey, string>> = {};
  for (const key of BUSINESS_KEYS) {
    const value = widget.filters[key]?.trim();
    if (value) result[key] = value;
  }
  return result;
}

export function resolveWidgetSearch(
  global: GlobalSearch & { period: string },
  widget: DashboardWidget,
): GlobalSearch & { period: string } {
  const local = localFilters(widget);
  let resolved: GlobalSearch & { period: string };
  if (widget.filter_mode === 'inherit') {
    resolved = { ...global };
  } else if (widget.filter_mode === 'augment') {
    resolved = { ...global, ...local };
  } else if (widget.filter_mode === 'override') {
    resolved = {
      period: global.period,
      comparison: global.comparison,
      ...local,
    };
  } else {
    resolved = {
      period: global.period,
      comparison: global.comparison,
    };
  }
  if (widget.module === 'finance' || widget.module === 'planning') {
    const { agent: _agent, ...withoutAgent } = resolved;
    return withoutAgent;
  }
  return resolved;
}

export function widgetFilterLabel(widget: DashboardWidget): string {
  const count = Object.values(localFilters(widget)).length;
  if (widget.filter_mode === 'inherit') return 'Filtre globale';
  if (widget.filter_mode === 'ignore') return 'Rețea, fără filtre globale';
  return `${widget.filter_mode === 'augment' ? 'Completează' : 'Suprascrie'} · ${count} locale`;
}
