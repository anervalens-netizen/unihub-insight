import { ArrowDown, ArrowUp, Search } from 'lucide-react';
import { useMemo, useState } from 'react';

import { formatCurrency, formatInteger, formatPercent } from '../../lib/format';
import type { PerformanceReviewRow, ProductReviewRow, ReviewStatus } from './schemas';

const statusLabels: Record<ReviewStatus, string> = {
  outperforming: 'Peste repere',
  healthy: 'Sănătos',
  watch: 'Atenție',
  risk: 'Risc',
  recovering: 'Revenire',
  slowing: 'Încetinire',
  volatile: 'Volatil',
  new: 'Nou',
  exited: 'Ieșit',
};

function StatusBadge({ status }: { status: ReviewStatus }) {
  return <span className={`review-status review-status--${status}`}>{statusLabels[status]}</span>;
}

export function PerformanceTable({
  rows,
  recentMonths,
}: {
  rows: PerformanceReviewRow[];
  recentMonths: number;
}) {
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState<'all' | ReviewStatus>('all');
  const [sort, setSort] = useState<'score' | 'sales' | 'yoy' | 'recent'>('score');
  const [ascending, setAscending] = useState(false);
  const visible = useMemo(() => {
    const needle = search.trim().toLocaleLowerCase('ro-RO');
    return rows
      .filter(
        (row) =>
          (status === 'all' || row.status === status) &&
          (!needle || `${row.label} ${row.context}`.toLocaleLowerCase('ro-RO').includes(needle)),
      )
      .sort((left, right) => {
        const value = (row: PerformanceReviewRow): number => {
          if (sort === 'sales') return row.sales;
          if (sort === 'yoy') return row.yoy_pct ?? Number.NEGATIVE_INFINITY;
          if (sort === 'recent') return row.recent_pct ?? Number.NEGATIVE_INFINITY;
          return row.performance_score;
        };
        const result = value(left) - value(right);
        return ascending ? result : -result;
      });
  }, [ascending, rows, search, sort, status]);

  return (
    <div className="review-table-block">
      <div className="review-table-tools">
        <label className="review-search">
          <Search size={14} />
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Caută entitate…"
          />
        </label>
        <select
          value={status}
          onChange={(event) => setStatus(event.target.value as 'all' | ReviewStatus)}
        >
          <option value="all">Toate statusurile</option>
          {Object.entries(statusLabels).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
        <select value={sort} onChange={(event) => setSort(event.target.value as typeof sort)}>
          <option value="score">Scor</option>
          <option value="sales">Vânzări</option>
          <option value="yoy">YoY</option>
          <option value="recent">Vs recent</option>
        </select>
        <button
          type="button"
          className="icon-button"
          aria-label="Inversează sortarea"
          onClick={() => setAscending((value) => !value)}
        >
          {ascending ? <ArrowUp size={14} /> : <ArrowDown size={14} />}
        </button>
      </div>
      <div className="table-scroll review-table-scroll">
        <table className="data-table review-table">
          <thead>
            <tr>
              <th>Entitate</th>
              <th>Vânzări</th>
              <th>Target</th>
              <th>YoY</th>
              <th>Vs {recentMonths} luni</th>
              <th>Bonuri</th>
              <th>Bon 2+</th>
              <th>Retur</th>
              <th>Scor</th>
              <th>Status</th>
              <th>Driver</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((row) => (
              <tr key={row.id}>
                <td>
                  <strong>{row.label}</strong>
                  <small className="table-context">{row.context}</small>
                </td>
                <td>{formatCurrency(row.sales, true)}</td>
                <td>{formatPercent(row.target_pct)}</td>
                <td className={(row.yoy_pct ?? 0) < 0 ? 'negative-number' : 'positive-number'}>
                  {formatPercent(row.yoy_pct)}
                </td>
                <td className={(row.recent_pct ?? 0) < 0 ? 'negative-number' : 'positive-number'}>
                  {formatPercent(row.recent_pct)}
                </td>
                <td>{formatInteger(row.receipts)}</td>
                <td>{formatPercent(row.bon2acc_pct)}</td>
                <td>{formatPercent(row.return_rate_pct)}</td>
                <td>
                  {row.performance_score.toLocaleString('ro-RO', { maximumFractionDigits: 1 })}
                </td>
                <td>
                  <StatusBadge status={row.status} />
                </td>
                <td>
                  <strong>{row.primary_driver}</strong>
                  <small className="table-context">
                    {formatCurrency(row.primary_driver_impact, true)} · {row.driver_basis}
                  </small>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function ProductTable({ rows }: { rows: ProductReviewRow[] }) {
  const [search, setSearch] = useState('');
  const [direction, setDirection] = useState<'all' | 'positive' | 'negative'>('all');
  const visible = useMemo(() => {
    const needle = search.trim().toLocaleLowerCase('ro-RO');
    return rows.filter((row) => {
      const directionMatches =
        direction === 'all' ||
        (direction === 'positive' ? row.impact_yoy >= 0 : row.impact_yoy < 0);
      return (
        directionMatches &&
        (!needle ||
          `${row.id} ${row.label} ${row.brand} ${row.category}`
            .toLocaleLowerCase('ro-RO')
            .includes(needle))
      );
    });
  }, [direction, rows, search]);
  return (
    <div className="review-table-block">
      <div className="review-table-tools">
        <label className="review-search">
          <Search size={14} />
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Caută SKU, produs, brand…"
          />
        </label>
        <select
          value={direction}
          onChange={(event) => setDirection(event.target.value as typeof direction)}
        >
          <option value="all">Ambele direcții</option>
          <option value="negative">Scăderi YoY</option>
          <option value="positive">Creșteri YoY</option>
        </select>
      </div>
      <div className="table-scroll review-table-scroll">
        <table className="data-table review-table">
          <thead>
            <tr>
              <th>Produs</th>
              <th>Vânzări</th>
              <th>YoY</th>
              <th>Vs recent</th>
              <th>Unități</th>
              <th>Distribuție</th>
              <th>Retur</th>
              <th>Impact YoY</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((row) => (
              <tr key={row.id}>
                <td>
                  <strong>{row.label}</strong>
                  <small className="table-context">
                    {row.id} · {row.brand} · {row.category}
                  </small>
                </td>
                <td>{formatCurrency(row.sales, true)}</td>
                <td>{formatPercent(row.yoy_pct)}</td>
                <td>{formatPercent(row.recent_pct)}</td>
                <td>{formatInteger(row.units)}</td>
                <td>{row.distribution ?? '—'}</td>
                <td>{formatPercent(row.return_rate_pct)}</td>
                <td className={row.impact_yoy < 0 ? 'negative-number' : 'positive-number'}>
                  {formatCurrency(row.impact_yoy, true)}
                </td>
                <td>
                  <StatusBadge status={row.status} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
