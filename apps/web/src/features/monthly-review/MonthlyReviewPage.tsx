import { useQuery } from '@tanstack/react-query';
import type { EChartsCoreOption } from 'echarts/core';
import { AlertCircle, CheckCircle2, FileSpreadsheet, RefreshCw, TriangleAlert } from 'lucide-react';
import { useMemo, useState } from 'react';

import { useGlobalSearch } from '../../app/search-hooks';
import { EChart } from '../../components/charts/EChart';
import { ErrorState } from '../../components/ui/ErrorState';
import { ExcelExportButton } from '../../components/ui/ExcelExportButton';
import { LoadingState } from '../../components/ui/LoadingState';
import { analyticsSearchParams } from '../../lib/download';
import { formatCurrency, formatDate, formatInteger, formatPercent } from '../../lib/format';
import { currentBusinessMonth } from '../../lib/search';
import { monthlyReviewQuery } from './api';
import { PerformanceTable, ProductTable } from './ReviewTables';
import type { MonthlyReview } from './schemas';

const sections = [
  ['summary', 'Sinteză'],
  ['performance', 'RM & magazine'],
  ['products', 'Produse'],
  ['returns', 'Retururi'],
  ['agents', 'Agenți'],
  ['methodology', 'Metodologie'],
] as const;

function metricValue(metric: MonthlyReview['executive'][number]): string {
  if (metric.unit === 'currency') return formatCurrency(metric.current, true);
  if (metric.unit === 'percent') return formatPercent(metric.current);
  if (metric.unit === 'integer') return formatInteger(metric.current);
  return metric.current.toLocaleString('ro-RO', { maximumFractionDigits: 2 });
}

function Delta({ label, value }: { label: string; value: number | null | undefined }) {
  return (
    <span className={`review-delta ${(value ?? 0) < 0 ? 'is-negative' : 'is-positive'}`}>
      <small>{label}</small>
      <strong>{formatPercent(value)}</strong>
    </span>
  );
}

function TrendChart({ data }: { data: MonthlyReview }) {
  const option = useMemo<EChartsCoreOption>(
    () => ({
      animationDuration: 260,
      grid: { top: 42, right: 22, bottom: 36, left: 66 },
      tooltip: { trigger: 'axis' },
      legend: { top: 0, right: 0 },
      xAxis: { type: 'category', data: data.trend.map((point) => point.period) },
      yAxis: {
        type: 'value',
        axisLabel: {
          formatter: (value: string | number) => formatCurrency(Number(value), true),
        },
      },
      series: [
        {
          type: 'line',
          name: 'Vânzări',
          data: data.trend.map((point) => point.sales),
          showSymbol: false,
          smooth: 0.16,
          lineStyle: { width: 3, color: '#4f46e5' },
          itemStyle: { color: '#4f46e5' },
          areaStyle: { color: 'rgba(79,70,229,.10)' },
        },
        {
          type: 'line',
          name: 'Target',
          data: data.trend.map((point) => point.target),
          showSymbol: false,
          lineStyle: { width: 2, type: 'dashed', color: '#0f766e' },
          itemStyle: { color: '#0f766e' },
        },
      ],
    }),
    [data.trend],
  );
  return <EChart option={option} className="chart--fill" ariaLabel="Evoluție lunară" />;
}

function DriverChart({ data }: { data: MonthlyReview }) {
  const driver = data.drivers[0];
  const option = useMemo<EChartsCoreOption>(
    () => ({
      grid: { top: 16, right: 16, bottom: 44, left: 66 },
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      xAxis: {
        type: 'category',
        data: ['Bonuri', 'Produse / bon', 'Valoare / produs'],
        axisLabel: { interval: 0, rotate: 12 },
      },
      yAxis: {
        type: 'value',
        axisLabel: {
          formatter: (value: string | number) => formatCurrency(Number(value), true),
        },
      },
      series: [
        {
          type: 'bar',
          data: driver
            ? [
                driver.receipts_effect,
                driver.units_per_receipt_effect,
                driver.value_per_unit_effect,
              ].map((value) => ({
                value,
                itemStyle: {
                  color: value < 0 ? '#be123c' : '#0f766e',
                },
              }))
            : [],
        },
      ],
    }),
    [driver],
  );
  return <EChart option={option} className="chart--fill" ariaLabel="Driverii diferenței" />;
}

function withSection(base: URLSearchParams, section: string): URLSearchParams {
  const params = new URLSearchParams(base);
  params.set('section', section);
  return params;
}

export function MonthlyReviewPage() {
  const search = useGlobalSearch();
  const period = search.period ?? currentBusinessMonth();
  const [recentMonths, setRecentMonths] = useState(3);
  const input = useMemo(() => ({ ...search, period }), [period, search]);
  const query = useQuery(monthlyReviewQuery(input, recentMonths));
  const exportParams = analyticsSearchParams(input);
  exportParams.set('recent_months', String(recentMonths));

  if (query.isPending) return <LoadingState label="Se generează raportul lunar…" />;
  if (query.isError) {
    return (
      <ErrorState
        message={
          query.error instanceof Error ? query.error.message : 'Raportul nu a putut fi generat.'
        }
        onRetry={() => void query.refetch()}
      />
    );
  }
  const data = query.data;
  const alertIcons = {
    info: CheckCircle2,
    warning: TriangleAlert,
    critical: AlertCircle,
  } as const;
  return (
    <section className="monthly-review-page">
      <header className="review-hero">
        <div>
          <span>Raport managerial lunar</span>
          <h2>Analiză vânzări · {data.meta.period}</h2>
          <p>
            YoY, luna precedentă și media recentă, de la rețea la produs și agent. Datele numerice
            se exportă în Excel ca numere, nu text.
          </p>
          <div className="review-pills">
            <b>{data.meta.scope_label}</b>
            <b>Cutoff {formatDate(data.meta.as_of)}</b>
            <b>{data.meta.is_final ? 'Lună finală' : 'Lună deschisă'}</b>
            <b>{data.meta.data_mode === 'demo' ? 'Date demo' : 'PostgreSQL live'}</b>
          </div>
        </div>
        <div className="review-hero-actions">
          <label>
            <span>Reper recent</span>
            <select
              value={recentMonths}
              onChange={(event) => setRecentMonths(Number(event.target.value))}
            >
              <option value={3}>Ultimele 3 luni</option>
              <option value={6}>Ultimele 6 luni</option>
              <option value={12}>Ultimele 12 luni</option>
            </select>
          </label>
          <button
            type="button"
            className="button button--secondary"
            onClick={() => void query.refetch()}
          >
            <RefreshCw size={15} /> Actualizează
          </button>
          <ExcelExportButton
            path="/exports/monthly-review.xlsx"
            params={exportParams}
            filename={`raport-lunar-${period}.xlsx`}
            label="Raport Excel complet"
            className="button button--primary"
          />
        </div>
      </header>

      <nav className="review-section-nav" aria-label="Secțiuni raport">
        {sections.map(([id, label]) => (
          <a key={id} href={`#review-${id}`}>
            {label}
          </a>
        ))}
      </nav>

      <section id="review-summary" className="review-section">
        <div className="review-section-heading">
          <div>
            <span>Sinteză</span>
            <h3>Rețea și indicatori comerciali</h3>
          </div>
          <ExcelExportButton
            path="/exports/monthly-review.xlsx"
            params={withSection(exportParams, 'summary')}
            filename={`sinteza-${period}.xlsx`}
          />
        </div>
        <div className="review-kpi-grid">
          {data.executive.map((metric) => (
            <article key={metric.id} className="review-kpi">
              <span>{metric.label}</span>
              <strong>{metricValue(metric)}</strong>
              <div>
                <Delta label="YoY" value={metric.yoy_delta} />
                <Delta label="MoM" value={metric.mom_delta} />
                <Delta label={`vs ${recentMonths} luni`} value={metric.recent_delta} />
              </div>
            </article>
          ))}
        </div>
        <div className="review-visual-grid">
          <article className="review-panel">
            <h4>Evoluție și target</h4>
            <TrendChart data={data} />
          </article>
          <article className="review-panel">
            <h4>Driverii diferenței YoY</h4>
            <DriverChart data={data} />
            {data.drivers[0] ? (
              <p>
                Diferență reconciliată: <b>{formatCurrency(data.drivers[0].sales_difference)}</b>.
              </p>
            ) : null}
          </article>
        </div>
        <article className="review-seasonality">
          <div>
            <span>Sezonalitate</span>
            <h4>Schimbarea lunii anterioare în luna analizată</h4>
          </div>
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>An</th>
                  <th>Interval</th>
                  <th>Vânzări</th>
                  <th>Unități</th>
                  <th>Bonuri</th>
                  <th>Vânzări / zi-magazin</th>
                  <th>Cohortă</th>
                </tr>
              </thead>
              <tbody>
                {data.seasonality.map((row) => (
                  <tr key={row.year} className={row.is_current ? 'is-current' : undefined}>
                    <td>
                      <strong>{row.year}</strong>
                    </td>
                    <td>
                      {row.previous_period} → {row.current_period}
                    </td>
                    <td>{formatPercent(row.sales_lift_pct)}</td>
                    <td>{formatPercent(row.units_lift_pct)}</td>
                    <td>{formatPercent(row.receipts_lift_pct)}</td>
                    <td>{formatPercent(row.sales_per_store_day_lift_pct)}</td>
                    <td>{formatInteger(row.store_count)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>
        <div className="review-alerts">
          {data.alerts.map((alert) => {
            const Icon = alertIcons[alert.severity];
            return (
              <article key={alert.id} className={`review-alert review-alert--${alert.severity}`}>
                <Icon size={17} />
                <div>
                  <strong>{alert.title}</strong>
                  <p>{alert.description}</p>
                </div>
              </article>
            );
          })}
        </div>
      </section>

      <section id="review-performance" className="review-section">
        <div className="review-section-heading">
          <div>
            <span>Managementul performanței</span>
            <h3>RM, companii și magazine</h3>
          </div>
          <ExcelExportButton
            path="/exports/monthly-review.xlsx"
            params={withSection(exportParams, 'stores')}
            filename={`magazine-${period}.xlsx`}
          />
        </div>
        <div className="review-subsection">
          <h4>Regional Managers</h4>
          <PerformanceTable rows={data.managers} recentMonths={recentMonths} />
        </div>
        <div className="review-subsection">
          <h4>Magazine</h4>
          <PerformanceTable rows={data.stores} recentMonths={recentMonths} />
        </div>
      </section>

      <section id="review-products" className="review-section">
        <div className="review-section-heading">
          <div>
            <span>Portofoliu</span>
            <h3>Categorii și produse</h3>
          </div>
          <ExcelExportButton
            path="/exports/monthly-review.xlsx"
            params={withSection(exportParams, 'products')}
            filename={`produse-${period}.xlsx`}
          />
        </div>
        <div className="review-subsection">
          <h4>Categorii</h4>
          <ProductTable rows={data.categories} />
        </div>
        <div className="review-subsection">
          <h4>Produse cu impact</h4>
          <ProductTable rows={data.products} />
        </div>
      </section>

      <section id="review-returns" className="review-section">
        <div className="review-section-heading">
          <div>
            <span>Calitate comercială</span>
            <h3>Retururi</h3>
          </div>
          <ExcelExportButton
            path="/exports/monthly-review.xlsx"
            params={withSection(exportParams, 'returns')}
            filename={`retururi-${period}.xlsx`}
          />
        </div>
        <div className="table-scroll review-table-scroll">
          <table className="data-table review-table">
            <thead>
              <tr>
                <th>Tip / entitate</th>
                <th>Valoare retur</th>
                <th>Rată</th>
                <th>Rată anul trecut</th>
                <th>Vs recent</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {data.returns.map((row) => (
                <tr key={`${row.entity_type}:${row.id}`}>
                  <td>
                    <strong>{row.label}</strong>
                    <small className="table-context">
                      {row.entity_type} · {row.context}
                    </small>
                  </td>
                  <td>{formatCurrency(row.current_value, true)}</td>
                  <td>{formatPercent(row.current_rate_pct)}</td>
                  <td>{formatPercent(row.previous_year_rate_pct)}</td>
                  <td>{formatPercent(row.recent_rate_delta_pp)}</td>
                  <td>
                    <span className={`review-status review-status--${row.status}`}>
                      {row.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section id="review-agents" className="review-section">
        <div className="review-section-heading">
          <div>
            <span>Echipă</span>
            <h3>Agenți</h3>
          </div>
          <ExcelExportButton
            path="/exports/monthly-review.xlsx"
            params={withSection(exportParams, 'agents')}
            filename={`agenti-${period}.xlsx`}
          />
        </div>
        <PerformanceTable rows={data.agents} recentMonths={recentMonths} />
      </section>

      <section id="review-methodology" className="review-section">
        <div className="review-section-heading">
          <div>
            <span>Trasabilitate</span>
            <h3>Metodologie</h3>
          </div>
          <FileSpreadsheet size={18} />
        </div>
        <ol className="review-methodology">
          {data.methodology.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ol>
      </section>
    </section>
  );
}
