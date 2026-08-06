import type { SourceMetadata } from '../../lib/analytics-contracts';
import type { ModuleAnalytics, ModuleId } from './schemas';

export type ModuleSubviewId =
  | 'pace'
  | 'trend'
  | 'mix'
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
  readonly mechanism?: readonly string[];
  readonly blockedByWarnings?: readonly string[];
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
      mechanism: ['promo'],
    },
    {
      id: 'incentive',
      label: 'Incentive',
      description: 'Mecanism separat; regulile de eligibilitate nu sunt reconstituite în UI.',
      sourceDomain: 'campaigns',
      mechanism: ['incentive'],
    },
    {
      id: 'contest',
      label: 'Concurs',
      description: 'Identitatea și participarea trebuie livrate de contractul Concurs.',
      sourceDomain: 'campaigns',
      mechanism: ['contest', 'concurs'],
    },
    {
      id: 'focus',
      label: 'Focus',
      description: 'Rezultatul Focus din read-model-ul disponibil.',
      sourceDomain: 'campaigns',
      mechanism: ['focus'],
    },
    {
      id: 'folii',
      label: 'Folii',
      description: 'Mecanism separat; nu este substituit cu altă campanie.',
      sourceDomain: 'campaigns',
      mechanism: ['folii', 'foil'],
    },
  ],
  workforce: [
    {
      id: 'people',
      label: 'People',
      description: 'Headcount și identitate opacă din read-model.',
      sourceDomain: 'workforce',
      blockedByWarnings: ['not an official workforce roster'],
    },
    {
      id: 'movements',
      label: 'Mișcări',
      description: 'Intrări, ieșiri și transferuri oficiale.',
      sourceDomain: 'workforce',
      blockedByWarnings: ['not an official workforce roster'],
    },
    {
      id: 'stability',
      label: 'Stability',
      description: 'Vechime și stabilitate în perioada selectată.',
      sourceDomain: 'workforce',
      blockedByWarnings: ['not an official workforce roster'],
    },
    {
      id: 'coverage',
      label: 'Coverage',
      description: 'Acoperirea magazinelor livrată de sursă.',
      sourceDomain: 'workforce',
      blockedByWarnings: ['not an official workforce roster'],
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
    },
    {
      id: 'grile',
      label: 'Grile',
      description: 'Statusul grilelor numai din contractul Grile.',
      sourceDomain: 'grile',
      blockedByWarnings: ['unavailable'],
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
      mechanism: ['reconcil'],
    },
    {
      id: 'break-even',
      label: 'Break-even',
      description: 'Disponibil numai dacă metrica este publicată de sursă.',
      sourceDomain: 'finance',
      mechanism: ['break-even', 'breakeven'],
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
      mechanism: ['scenario'],
    },
    {
      id: 'sensitivity',
      label: 'Sensitivity',
      description: 'Sensibilitate numai dacă există contract explicit.',
      sourceDomain: 'planning',
      mechanism: ['sensitivity'],
    },
  ],
};

export type SubviewAvailability = 'available' | 'partial' | 'unavailable';

export interface SubviewStatus {
  availability: SubviewAvailability;
  reason: string;
  source: SourceMetadata | undefined;
}

export function subviewForId(module: ModuleId, id: string | undefined): ModuleSubview {
  const views = moduleSubviewConfig[module];
  const fallback = views[0];
  if (!fallback) throw new Error(`Modulul ${module} nu are sub-view canonic.`);
  return views.find((view) => view.id === id) ?? fallback;
}

export function subviewStatus(data: ModuleAnalytics, view: ModuleSubview): SubviewStatus {
  const source = data.meta.sources?.[view.sourceDomain];
  if (!source) {
    return {
      availability: 'unavailable',
      reason: `Contractul ${view.sourceDomain} nu este prezent în metadata snapshotului.`,
      source,
    };
  }
  if (source.status === 'unavailable') {
    return {
      availability: 'unavailable',
      reason: `Sursa ${source.source} este marcată unavailable pentru ${view.label}.`,
      source,
    };
  }
  const normalize = (value: string): string =>
    value
      .toLocaleLowerCase('ro-RO')
      .replace(/[^a-z0-9ăâîșț]+/gi, ' ')
      .trim();
  const warnings = source.warnings.map(normalize);
  const sourceText = normalize(
    [
      source.source,
      source.source_generation,
      source.authority,
      source.authority_head,
      source.rule_version,
      ...source.warnings,
    ]
      .filter(Boolean)
      .join(' '),
  );
  const blockingWarning = view.blockedByWarnings?.find((marker) =>
    warnings.some((warning) => warning.includes(normalize(marker))),
  );
  if (blockingWarning) {
    return {
      availability: 'unavailable',
      reason: `Sursa curentă declară explicit că ${view.label} nu are contract oficial eligibil.`,
      source,
    };
  }
  if (
    view.mechanism?.some((token) =>
      warnings.some(
        (warning) =>
          warning.includes(normalize(token)) &&
          warning.includes('unavailable') &&
          !warning.includes(`${normalize(token)} only`),
      ),
    )
  ) {
    return {
      availability: 'unavailable',
      reason: `Metadata marchează mecanismul ${view.label} ca unavailable.`,
      source,
    };
  }
  if (view.mechanism && !view.mechanism.some((token) => sourceText.includes(token))) {
    return {
      availability: 'unavailable',
      reason: `Metadata nu publică un contract pentru mecanismul ${view.label}; Focus nu îl substituie.`,
      source,
    };
  }
  if (source.status === 'partial' || source.status === 'stale') {
    return {
      availability: 'partial',
      reason: `Sursa este ${source.status}; vezi cutoff-ul și warnings înainte de interpretare.`,
      source,
    };
  }
  return {
    availability: 'available',
    reason: 'Sursa este oficială pentru snapshotul curent.',
    source,
  };
}
