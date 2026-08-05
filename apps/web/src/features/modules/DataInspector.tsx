import { Download, X } from 'lucide-react';
import { useEffect, useMemo } from 'react';
import { createPortal } from 'react-dom';

import type { ModuleAnalytics } from './schemas';

type InspectValue = string | number | boolean | null;
type InspectRow = Record<string, InspectValue>;

function rowsFor(widgetId: string, data: ModuleAnalytics): InspectRow[] {
  if (widgetId.startsWith('kpi-')) {
    const index = Number(widgetId.slice(4));
    const item = data.kpis[index];
    return item
      ? [
          {
            metric: item.label,
            value: item.value,
            unit: item.unit,
            delta_pct: item.delta_pct ?? null,
            supporting_value: item.supporting_value ?? null,
            supporting_label: item.supporting_label ?? null,
          },
        ]
      : [];
  }
  if (widgetId === 'trend')
    return data.trend.map((row) => ({
      period: row.label,
      primary: row.primary,
      comparison: row.comparison ?? null,
      target: row.target ?? null,
      secondary: row.secondary ?? null,
      estimated: row.is_estimate,
    }));
  if (widgetId === 'distribution')
    return data.distribution.map((row) => ({
      entity: row.label,
      value: row.value,
      share_pct: row.share_pct,
    }));
  if (widgetId === 'matrix')
    return data.matrix.map((row) => ({
      period: row.x,
      entity: row.y,
      value: row.value,
      label: row.label ?? null,
      risk: row.risk,
    }));
  if (widgetId === 'breakdown')
    return data.breakdown.map((row) => ({
      entity: row.label,
      context: row.context,
      primary: row.primary,
      secondary: row.secondary ?? null,
      tertiary: row.tertiary ?? null,
      progress_pct: row.progress_pct ?? null,
      delta_pct: row.delta_pct ?? null,
      risk: row.risk,
    }));
  if (widgetId === 'alerts')
    return data.alerts.map((row) => ({
      severity: row.severity,
      title: row.title,
      description: row.description,
      entity: row.entity_label ?? null,
    }));
  return [];
}

function csvCell(value: InspectValue): string {
  if (value === null) return '';
  const text = String(value);
  return /[",\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

function downloadCsv(filename: string, columns: string[], rows: InspectRow[]): void {
  const content = [
    columns.join(','),
    ...rows.map((row) => columns.map((column) => csvCell(row[column] ?? null)).join(',')),
  ].join('\n');
  const blob = new Blob([`\uFEFF${content}`], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export function DataInspector({
  widgetId,
  data,
  onClose,
}: {
  widgetId: string;
  data: ModuleAnalytics;
  onClose: () => void;
}) {
  const rows = useMemo(() => rowsFor(widgetId, data), [data, widgetId]);
  const columns = useMemo(() => (rows[0] ? Object.keys(rows[0]) : []), [rows]);
  useEffect(() => {
    const handler = (event: KeyboardEvent): void => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);
  return createPortal(
    <div
      className="widget-modal-backdrop"
      role="button"
      tabIndex={0}
      aria-label="Închide inspectorul de date"
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') onClose();
      }}
      onMouseDown={onClose}
    >
      <section
        className="data-inspector"
        role="dialog"
        aria-modal="true"
        aria-labelledby="data-inspector-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header className="data-inspector-header">
          <div>
            <span>Date sursă</span>
            <h2 id="data-inspector-title">
              {data.title} · {widgetId}
            </h2>
            <p>
              {data.meta.scope_label} · {data.meta.period} · {data.meta.source}
            </p>
          </div>
          <div>
            <button
              type="button"
              className="button button--secondary"
              disabled={rows.length === 0}
              onClick={() =>
                downloadCsv(`${data.module}_${widgetId}_${data.meta.period}.csv`, columns, rows)
              }
            >
              <Download size={15} />
              CSV
            </button>
            <button type="button" className="icon-button" aria-label="Închide" onClick={onClose}>
              <X size={17} />
            </button>
          </div>
        </header>
        <div className="data-inspector-body">
          {rows.length === 0 ? (
            <p>Nu există rânduri pentru această vizualizare.</p>
          ) : (
            <table className="data-table data-table--inspect">
              <thead>
                <tr>
                  {columns.map((column) => (
                    <th key={column}>{column}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr
                    key={`${widgetId}-${columns.map((column) => String(row[column] ?? '')).join('|')}`}
                  >
                    {columns.map((column) => (
                      <td key={column}>{String(row[column] ?? '')}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </section>
    </div>,
    document.body,
  );
}
