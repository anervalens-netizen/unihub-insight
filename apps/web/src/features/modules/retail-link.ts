import type { ChartUrlStateEvent } from '../../components/charts/chart-spec';
import { type GlobalSearch, parseStoreSelection, rangeBounds } from '../../lib/search';
import type { ModuleId } from './schemas';
import type { ModuleSubviewId } from './subviews';

interface RetailDestination {
  readonly path: string;
  readonly section?: string;
  readonly subtab?: string;
}

function destinationFor(module: ModuleId, subview: ModuleSubviewId): RetailDestination {
  if (module === 'campaigns') {
    const sections: Partial<Record<ModuleSubviewId, string>> = {
      promo: 'promo',
      incentive: 'incentive',
      contest: 'concurs',
      focus: 'focus',
      folii: 'premium',
    };
    return { path: '/focus', section: sections[subview] ?? 'focus' };
  }
  if (module === 'workforce') {
    if (subview === 'visits') return { path: '/hub', section: 'visits' };
    if (subview === 'grile') return { path: '/agenti', section: 'grile' };
    return {
      path: '/agenti',
      section: subview === 'productivity' ? 'analysis' : 'overview',
    };
  }
  if (module === 'compensation') return { path: '/management', subtab: 'salarii' };
  if (module === 'finance') return { path: '/management/pnl', subtab: 'pnl' };
  if (module === 'planning') return { path: '/management', subtab: 'target-calculator' };
  if (module === 'performance') return { path: '/agenti', section: 'analysis' };
  return {
    path: '/hub',
    section: subview === 'pace' ? 'current' : 'history',
  };
}

export function retailContextUrl(
  baseUrl: string,
  module: ModuleId,
  subview: ModuleSubviewId,
  search: GlobalSearch & { period: string },
): string {
  const destination = destinationFor(module, subview);
  const url = new URL(destination.path, `${baseUrl.replace(/\/+$/, '')}/`);
  const range = rangeBounds(search);
  const stores = parseStoreSelection(search.stores);
  url.searchParams.set('source_context', 'insight');
  url.searchParams.set('period', range.end);
  url.searchParams.set('range_start', range.start);
  url.searchParams.set('range_end', range.end);
  if (destination.section) url.searchParams.set('section', destination.section);
  if (destination.subtab) url.searchParams.set('subtab', destination.subtab);
  if (search.firm) url.searchParams.set('firma', search.firm);
  if (search.regional) url.searchParams.set('rm', search.regional);
  if (stores.length === 1 && stores[0]) url.searchParams.set('magazin', stores[0]);
  if (stores.length > 1) url.searchParams.set('stores', stores.join(','));
  if (search.agent) url.searchParams.set('agent', search.agent);
  return url.toString();
}

export function retailEntityContextUrl(
  baseUrl: string,
  module: ModuleId,
  subview: ModuleSubviewId,
  search: GlobalSearch & { period: string },
  event: ChartUrlStateEvent,
): string {
  const url = new URL(retailContextUrl(baseUrl, module, subview, search));
  if (event.dimensionId === 'time') {
    url.searchParams.set('period', event.value);
    url.searchParams.set('range_start', event.value);
    url.searchParams.set('range_end', event.value);
  } else if (event.dimensionId === 'store') {
    url.searchParams.delete('stores');
    url.searchParams.set('magazin', event.value);
  } else {
    const parameter = {
      firm: 'firma',
      regional: 'rm',
      asm: 'asm',
      agent: 'agent',
      team_leader: 'team_leader',
      category: 'category',
    }[event.dimensionId];
    if (parameter) url.searchParams.set(parameter, event.value);
  }
  return url.toString();
}

const defaultDashboardSubview: Record<ModuleId, ModuleSubviewId> = {
  sales: 'trend',
  performance: 'rankings',
  campaigns: 'focus',
  workforce: 'productivity',
  compensation: 'overview',
  finance: 'overview',
  planning: 'current',
};

export function retailDashboardEntityContextUrl(
  baseUrl: string,
  module: ModuleId,
  search: GlobalSearch & { period: string },
  event: ChartUrlStateEvent,
): string {
  return retailEntityContextUrl(baseUrl, module, defaultDashboardSubview[module], search, event);
}

export function openRetailContext(url: string): void {
  const popup = window.open(url, '_blank', 'noopener,noreferrer');
  if (popup) popup.opener = null;
}
