import {
  ArrowRight,
  Blocks,
  ChartSpline,
  CircleDotDashed,
  Database,
  Layers3,
  ShieldCheck,
} from 'lucide-react';

const modulePlans = {
  sales: {
    eyebrow: 'P1.2',
    title: 'Sales Intelligence',
    statement: 'Analiză comercială multi-perioadă, fără a fragmenta luna curentă de istoric.',
    capabilities: ['Pace și forecast', 'Trend MTD / YTD / 12 luni', 'Mix și tranzacții', 'Calendar heatmap'],
  },
  performance: {
    eyebrow: 'P1.3',
    title: 'Performance',
    statement: 'Drill-down coerent de la rețea până la agent, cu risc și stabilitate explicabile.',
    capabilities: ['RM și ASM', 'Magazine', 'Agenți', 'Heatmap și scatter'],
  },
  campaigns: {
    eyebrow: 'P2.1',
    title: 'Campaigns',
    statement: 'Promo, Incentive, Concurs și Focus analizate în același model de perioadă și scope.',
    capabilities: ['Coverage', 'Adopție', 'Discount', 'Contribuție'],
  },
  workforce: {
    eyebrow: 'P2.2–P2.3',
    title: 'Workforce',
    statement: 'O vedere unificată asupra structurii, stabilității, productivității și compensației.',
    capabilities: ['Headcount', 'Mișcări', 'Grile', 'Compensații RBAC'],
  },
  finance: {
    eyebrow: 'P3.1',
    title: 'Finance & P&L',
    statement: 'Profitabilitate detaliată, cu actual/estimat și reconciliere vizibile permanent.',
    capabilities: ['Venit și cost', 'Marjă', 'Waterfall', 'Break-even'],
  },
  planning: {
    eyebrow: 'P3.2',
    title: 'Planning',
    statement: 'Forecast și target în scenarii versionate, comparabile și reproductibile.',
    capabilities: ['Forecast 12 luni', 'Acuratețe', 'Scenarii', 'Sensitivitate'],
  },
  dashboards: {
    eyebrow: 'P1.4',
    title: 'Custom Dashboards',
    statement: 'Layouturi personale și template-uri sigure, fără a deveni un editor SQL arbitrar.',
    capabilities: ['Template-uri', 'Clone', 'Preseturi', 'Share read-only'],
  },
} as const;

export type ModuleId = keyof typeof modulePlans;

export function ModulePage({ module }: { module: ModuleId }) {
  const plan = modulePlans[module];
  return (
    <section className="module-page">
      <div className="module-hero">
        <div>
          <span className="module-eyebrow">Roadmap {plan.eyebrow}</span>
          <h2>{plan.title}</h2>
          <p>{plan.statement}</p>
        </div>
        <div className="module-status">
          <CircleDotDashed size={18} />
          Fundație pregătită
        </div>
      </div>

      <div className="module-grid">
        {plan.capabilities.map((capability, index) => {
          const icons = [ChartSpline, Layers3, Blocks, Database] as const;
          const Icon = icons[index] ?? Blocks;
          return (
            <article key={capability} className="module-capability">
              <Icon size={18} />
              <strong>{capability}</strong>
              <span>Contractul va folosi catalogul comun de metrici și filtrele globale.</span>
            </article>
          );
        })}
      </div>

      <div className="foundation-panel">
        <div className="foundation-step">
          <ShieldCheck size={19} />
          <div>
            <strong>Regulă de implementare</strong>
            <span>Fiecare lot intră numai după reconciliere cu adevărul din UniHub Retail.</span>
          </div>
        </div>
        <ArrowRight size={18} />
        <div className="foundation-step">
          <Database size={19} />
          <div>
            <strong>Următorul gate</strong>
            <span>Integrare PostgreSQL live, Authentik și metric catalog versionat.</span>
          </div>
        </div>
      </div>
    </section>
  );
}
