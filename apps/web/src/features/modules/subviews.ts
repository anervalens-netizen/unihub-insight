import type { SourceMetadata } from '../../lib/analytics-contracts';
import type { ModuleAnalytics, ModuleAnalyticsSlice, ModuleId } from './schemas';

export type ModuleSubviewId =
  | 'pace'
  | 'trend'
  | 'mix'
  | 'portfolio-category'
  | 'portfolio-subcategory'
  | 'portfolio-brand'
  | 'portfolio-product'
  | 'drivers'
  | 'transactions'
  | 'calendar'
  | 'overview'
  | 'rankings'
  | 'consistency'
  | 'productivity'
  | 'visits'
  | 'promo'
  | 'incentive'
  | 'contest'
  | 'focus'
  | 'folii'
  | 'people'
  | 'movements'
  | 'stability'
  | 'coverage'
  | 'grile'
  | 'distribution'
  | 'payroll-ratios'
  | 'cost-structure'
  | 'profitability'
  | 'reconciliation'
  | 'break-even'
  | 'current'
  | '12-months'
  | 'accuracy'
  | 'scenarios'
  | 'sensitivity';

export interface ModuleSubview {
  readonly id: ModuleSubviewId;
  readonly label: string;
  readonly description: string;
  readonly sourceDomain: string;
  /** Specialized views must prove their own server-side slice. */
  readonly requiresSlice?: boolean;
}

export const moduleSubviewConfig: Record<ModuleId, readonly ModuleSubview[]> = {
  sales: [
    {
      id: 'pace',
      label: 'Pace',
      description: 'Realizat, target și gap în luna selectată.',
      sourceDomain: 'sales',
    },
    {
      id: 'trend',
      label: 'Trend',
      description: 'Evoluție istorică și repere comparabile.',
      sourceDomain: 'sales',
    },
    {
      id: 'mix',
      label: 'Mix',
      description: 'Contribuție pe dimensiunile livrate de API.',
      sourceDomain: 'sales',
    },
    {
      id: 'portfolio-category',
      label: 'Categorii',
      description: 'Portofoliu pe categorie: vânzări, cantitate netă și contribuție pozitivă.',
      sourceDomain: 'sales',
    },
    {
      id: 'portfolio-subcategory',
      label: 'Subcategorii',
      description: 'Portofoliu pe subcategorie, păstrând categoria în context.',
      sourceDomain: 'sales',
    },
    {
      id: 'portfolio-brand',
      label: 'Branduri',
      description: 'Portofoliu pe brand, cu retururi semnate de sursa Retail.',
      sourceDomain: 'sales',
    },
    {
      id: 'portfolio-product',
      label: 'Produse',
      description: 'Portofoliu pe SKU, cu retururi și incidențe SKU în bonuri.',
      sourceDomain: 'sales',
    },
    {
      id: 'drivers',
      label: 'Drivers',
      description: 'Abateri și entități care explică diferența observată.',
      sourceDomain: 'sales',
    },
    {
      id: 'transactions',
      label: 'Transactions',
      description: 'Bonuri și volum numai unde metrica există în snapshot.',
      sourceDomain: 'sales',
    },
    {
      id: 'calendar',
      label: 'Calendar',
      description: 'Acoperire temporală fără a transforma lipsa în zero.',
      sourceDomain: 'sales',
    },
  ],
  performance: [
    {
      id: 'overview',
      label: 'Overview',
      description: 'Starea agregată a performanței.',
      sourceDomain: 'sales',
    },
    {
      id: 'rankings',
      label: 'Rankings',
      description: 'Clasamente pe entitățile întoarse de API.',
      sourceDomain: 'sales',
    },
    {
      id: 'consistency',
      label: 'Consistency',
      description: 'Volatilitate și repere istorice disponibile.',
      sourceDomain: 'sales',
    },
    {
      id: 'productivity',
      label: 'Productivity',
      description: 'Productivitate numai cu metrica autoritativă prezentă.',
      sourceDomain: 'sales',
    },
    {
      id: 'visits',
      label: 'Visits',
      description: 'Vizite numai dacă sursa de vizite este livrată în metadata.',
      sourceDomain: 'visits',
    },
  ],
  campaigns: [
    {
      id: 'overview',
      label: 'Overview',
      description: 'Starea mecanismelor și acoperirea lor.',
      sourceDomain: 'campaigns',
    },
    {
      id: 'promo',
      label: 'Promo',
      description: 'Mecanism separat; nu este dedus din Focus.',
      sourceDomain: 'campaigns',
      requiresSlice: true,
    },
    {
      id: 'incentive',
      label: 'Incentive',
      description: 'Mecanism separat; regulile de eligibilitate nu sunt reconstituite în UI.',
      sourceDomain: 'campaigns',
      requiresSlice: true,
    },
    {
      id: 'contest',
      label: 'Concurs',
      description:
        'Clasamentul și punctajul din read-model-ul canonic Retail; Focus nu îl substituie.',
      sourceDomain: 'contest',
      requiresSlice: true,
    },
    {
      id: 'focus',
      label: 'Focus',
      description: 'Rezultatul Focus din read-model-ul disponibil.',
      sourceDomain: 'campaigns',
    },
    {
      id: 'folii',
      label: 'Folii',
      description: 'Mecanism separat; nu este substituit cu altă campanie.',
      sourceDomain: 'campaigns',
      requiresSlice: true,
    },
  ],
  workforce: [
    {
      id: 'people',
      label: 'People',
      description: 'Agenți observați în activitate comercială; nu este un roster oficial.',
      sourceDomain: 'workforce',
      requiresSlice: true,
    },
    {
      id: 'movements',
      label: 'Mișcări',
      description: 'Agenți nou observați sau reactivați; fără ieșiri și transferuri oficiale.',
      sourceDomain: 'workforce',
      requiresSlice: true,
    },
    {
      id: 'stability',
      label: 'Stability',
      description: 'Continuitatea activității comerciale observate în perioada selectată.',
      sourceDomain: 'workforce',
      requiresSlice: true,
    },
    {
      id: 'coverage',
      label: 'Coverage',
      description: 'Acoperirea magazinelor livrată de sursă.',
      sourceDomain: 'workforce',
      requiresSlice: true,
    },
    {
      id: 'productivity',
      label: 'Productivity',
      description: 'Productivitate pe baza metricii existente.',
      sourceDomain: 'workforce',
    },
    {
      id: 'visits',
      label: 'Visits',
      description: 'Vizite cu autorul Team Leader păstrat de sursă.',
      sourceDomain: 'visits',
      requiresSlice: true,
    },
    {
      id: 'grile',
      label: 'Grile',
      description: 'Statusul grilelor numai din contractul Grile.',
      sourceDomain: 'grile',
      requiresSlice: true,
    },
  ],
  compensation: [
    {
      id: 'overview',
      label: 'Overview',
      description: 'Agregate aprobate și praguri de suprimare.',
      sourceDomain: 'compensation',
    },
    {
      id: 'distribution',
      label: 'Distribution',
      description: 'Distribuție agregată, fără identificarea persoanelor.',
      sourceDomain: 'compensation',
    },
    {
      id: 'payroll-ratios',
      label: 'Payroll ratios',
      description: 'Payroll/sales și payroll/profit când sursa le permite.',
      sourceDomain: 'compensation',
    },
  ],
  finance: [
    {
      id: 'overview',
      label: 'Overview',
      description: 'Venit, cost și profit cu statut actual/estimate.',
      sourceDomain: 'finance',
    },
    {
      id: 'trend',
      label: 'Trend',
      description: 'Evoluție financiară pe perioade acoperite.',
      sourceDomain: 'finance',
    },
    {
      id: 'cost-structure',
      label: 'Cost structure',
      description: 'Categorii de cost livrate de contractul Finance.',
      sourceDomain: 'finance',
    },
    {
      id: 'profitability',
      label: 'Profitability',
      description: 'EBIT și marjă fără agregări client-side.',
      sourceDomain: 'finance',
    },
    {
      id: 'reconciliation',
      label: 'Reconciliation',
      description: 'Reconciliere și autoritatea generației.',
      sourceDomain: 'finance',
    },
    {
      id: 'break-even',
      label: 'Break-even',
      description: 'Disponibil numai dacă metrica este publicată de sursă.',
      sourceDomain: 'finance',
    },
  ],
  planning: [
    {
      id: 'current',
      label: 'Current',
      description: 'Run-ul curent și gap-ul față de target.',
      sourceDomain: 'planning',
    },
    {
      id: '12-months',
      label: '12 luni',
      description: 'Forecast pe orizontul livrat de run.',
      sourceDomain: 'planning',
    },
    {
      id: 'accuracy',
      label: 'Accuracy',
      description: 'Acuratețe doar pentru perioade cu actual observat.',
      sourceDomain: 'planning',
    },
    {
      id: 'scenarios',
      label: 'Scenarios',
      description: 'Snapshoturi versionate, fără a promova drafturi implicit.',
      sourceDomain: 'planning',
      requiresSlice: true,
    },
    {
      id: 'sensitivity',
      label: 'Sensitivity',
      description: 'Sensibilitate numai dacă există contract explicit.',
      sourceDomain: 'planning',
      requiresSlice: true,
    },
  ],
};

export type SubviewAvailability = 'available' | 'partial' | 'unavailable';

export interface SubviewStatus {
  availability: SubviewAvailability;
  reason: string;
  source: SourceMetadata | undefined;
}

const portfolioDimensions: Partial<Record<ModuleSubviewId, string>> = {
  'portfolio-category': 'category',
  'portfolio-subcategory': 'subcategory',
  'portfolio-brand': 'brand',
  'portfolio-product': 'product',
};

export function portfolioDimensionForSubview(id: ModuleSubviewId): string | undefined {
  return portfolioDimensions[id];
}

export function specializedSubviewActions(availability: SubviewAvailability): {
  showRetailLink: true;
  showRefresh: true;
  showExport: boolean;
  showLayout: boolean;
} {
  return {
    showRetailLink: true,
    showRefresh: true,
    showExport: availability !== 'unavailable',
    showLayout: availability !== 'unavailable',
  };
}

export function unavailableSubviewCopy(view: ModuleSubview): string {
  if (view.id === 'contest') {
    return 'Retail poate avea mecanismul Concurs, dar Insight nu are un head/read-model oficial eligibil pentru acest mecanism. Cifrele Focus nu sunt folosite ca substitut.';
  }
  return 'Contractul lipsă nu este înlocuit cu cifre din alt mecanism sau din altă generație.';
}

/**
 * Resolve the exact server projection for a sub-view. The parent payload is
 * intentionally not used as a substitute when a specialized slice is required.
 */
export function moduleSliceForSubview(
  data: ModuleAnalytics,
  view: ModuleSubview,
): ModuleAnalyticsSlice | undefined {
  if (view.id === 'visits') return data.visits ?? data.subviews?.[view.id];
  const portfolioDimension = portfolioDimensions[view.id];
  if (portfolioDimension) return data.portfolio?.[portfolioDimension];
  return data.subviews?.[view.id] ?? data.campaigns?.[view.id];
}

function sliceSource(
  slice: ModuleAnalyticsSlice | undefined,
  view: ModuleSubview,
): SourceMetadata | undefined {
  if (!slice) return undefined;
  const sources = slice.sources ?? {};
  return sources[view.sourceDomain] ?? Object.values(sources)[0];
}

function availabilityForStatus(status: ModuleAnalyticsSlice['status']): SubviewAvailability {
  if (status === 'official') return 'available';
  if (status === 'partial' || status === 'stale') return 'partial';
  return 'unavailable';
}

export function subviewForId(module: ModuleId, id: string | undefined): ModuleSubview {
  const views = moduleSubviewConfig[module];
  const fallback = views[0];
  if (!fallback) throw new Error(`Modulul ${module} nu are sub-view canonic.`);
  return views.find((view) => view.id === id) ?? fallback;
}

export function subviewStatus(data: ModuleAnalytics, view: ModuleSubview): SubviewStatus {
  const slice = moduleSliceForSubview(data, view);
  const source = sliceSource(slice, view) ?? data.meta.sources?.[view.sourceDomain];
  if (!slice && view.requiresSlice) {
    return {
      availability: 'unavailable',
      reason: `Slice-ul server-side pentru ${view.label} nu este prezent în răspunsul modulului.`,
      source,
    };
  }
  if (!source) {
    return {
      availability: 'unavailable',
      reason: `Contractul ${view.sourceDomain} nu este prezent în metadata snapshotului.`,
      source,
    };
  }
  const availability = slice
    ? availabilityForStatus(slice.status)
    : availabilityForStatus(source.status);
  if (availability === 'unavailable') {
    return {
      availability: 'unavailable',
      reason: slice
        ? `Slice-ul server-side pentru ${view.label} este marcat unavailable.`
        : `Sursa ${source.source} este marcată unavailable pentru ${view.label}.`,
      source,
    };
  }
  if (availability === 'partial') {
    const observedWorkforceActivity =
      view.sourceDomain === 'workforce' &&
      ['people', 'movements', 'stability', 'coverage'].includes(view.id);
    return {
      availability: 'partial',
      reason: observedWorkforceActivity
        ? 'Activitate comercială observată; nu este un roster oficial de personal. Sursa server-side este PARTIAL.'
        : `Slice-ul server-side pentru ${view.label} este ${slice?.status ?? source.status}.`,
      source,
    };
  }
  return {
    availability: 'available',
    reason: slice
      ? `Slice-ul server-side pentru ${view.label} este oficial.`
      : 'Sursa este oficială pentru snapshotul curent.',
    source,
  };
}
