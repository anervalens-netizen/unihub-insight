import { useQuery } from '@tanstack/react-query';
import { Download, FileSpreadsheet, LoaderCircle, X } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';

import type { GlobalSearch } from '../../lib/search';
import {
  buildExportRequest,
  buildInspectRequest,
  exportQueryCsv,
  exportQueryXlsx,
  inspectQueryOptions,
} from './api';
import type {
  DatasetDimension,
  DatasetValue,
  MetricDefinition,
  QueryDataset,
  WidgetQueryResult,
} from './schemas';

function filenameFromDisposition(value: string | null, fallback: string): string {
  if (!value) return fallback;
  const utf8 = value.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
  if (utf8) return decodeURIComponent(utf8);
  return value.match(/filename="?([^";]+)"?/i)?.[1] ?? fallback;
}

function formatValue(value: DatasetValue | undefined): string {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'boolean') return value ? 'Da' : 'Nu';
  return String(value);
}

function DatasetTable({ dataset }: { dataset: QueryDataset }) {
  const keyDimension =
    dataset.dimensions.find((dimension) => dimension.role === 'key') ?? dataset.dimensions[0];
  return (
    <div className="table-scroll">
      <table className="data-table data-table--inspect">
        <thead>
          <tr>
            {dataset.dimensions.map((dimension) => (
              <th key={dimension.id}>{dimension.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {dataset.rows.map((row) => (
            <tr key={String(keyDimension ? row[keyDimension.id] : JSON.stringify(row))}>
              {dataset.dimensions.map((dimension: DatasetDimension) => (
                <td key={dimension.id}>{formatValue(row[dimension.id])}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function QueryInspector({
  dashboardId,
  snapshotId,
  search,
  result,
  metric,
  onClose,
}: {
  dashboardId: string | null;
  snapshotId: string;
  search: GlobalSearch & { period: string };
  result: Pick<WidgetQueryResult, 'widget_id' | 'query' | 'meta'>;
  metric: MetricDefinition;
  onClose: () => void;
}) {
  const dialogRef = useRef<HTMLElement>(null);
  const [exporting, setExporting] = useState<'csv' | 'xlsx' | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const pageSize = 100;
  const request = useMemo(
    () => buildInspectRequest(snapshotId, dashboardId, result.query, page, pageSize),
    [dashboardId, page, result.query, snapshotId],
  );
  const inspectQuery = useMemo(() => inspectQueryOptions(request, search, true), [request, search]);
  const inspection = useQuery(inspectQuery);
  const sources = inspection.data
    ? Object.values(inspection.data.meta.sources)
    : result.meta?.source
      ? [result.meta.source]
      : [];

  useEffect(() => {
    const previouslyFocused =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const dialog = dialogRef.current;
    dialog?.focus();
    const handler = (event: KeyboardEvent): void => {
      if (event.key === 'Escape') {
        onClose();
        return;
      }
      if (event.key !== 'Tab' || !dialog) return;
      const focusable = [
        ...dialog.querySelectorAll<HTMLElement>(
          'button:not([disabled]), [href], [tabindex]:not([tabindex="-1"])',
        ),
      ];
      if (focusable.length === 0) {
        event.preventDefault();
        dialog.focus();
        return;
      }
      const first = focusable[0];
      const last = focusable.at(-1);
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    };
    window.addEventListener('keydown', handler);
    return () => {
      window.removeEventListener('keydown', handler);
      previouslyFocused?.focus();
    };
  }, [onClose]);

  const exportDataset = (format: 'csv' | 'xlsx'): void => {
    setExporting(format);
    setExportError(null);
    const exporter = format === 'csv' ? exportQueryCsv : exportQueryXlsx;
    void exporter(buildExportRequest(snapshotId, dashboardId, result.query), search)
      .then(({ blob, filename }) => {
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = filenameFromDisposition(
          filename,
          `${result.widget_id}-${search.period}.${format}`,
        );
        link.click();
        window.setTimeout(() => URL.revokeObjectURL(url), 0);
      })
      .catch((error: unknown) =>
        setExportError(error instanceof Error ? error.message : 'Exportul a eșuat.'),
      )
      .finally(() => setExporting(null));
  };

  return createPortal(
    <div className="widget-modal-backdrop">
      <section
        ref={dialogRef}
        className="data-inspector"
        role="dialog"
        aria-modal="true"
        aria-labelledby="query-inspector-title"
        tabIndex={-1}
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header className="data-inspector-header">
          <div>
            <span>Inspect server-side · snapshot {snapshotId}</span>
            <h2 id="query-inspector-title">{metric.display_name}</h2>
            <p>
              {result.query.module} · {result.query.metric_id} · query v
              {result.query.query_contract_version}
            </p>
          </div>
          <div>
            <button
              type="button"
              className="button button--secondary"
              disabled={exporting !== null}
              onClick={() => exportDataset('csv')}
            >
              {exporting === 'csv' ? (
                <LoaderCircle className="spin" size={15} />
              ) : (
                <Download size={15} />
              )}
              CSV server-side
            </button>
            <button
              type="button"
              className="button button--secondary"
              disabled={exporting !== null}
              onClick={() => exportDataset('xlsx')}
            >
              {exporting === 'xlsx' ? (
                <LoaderCircle className="spin" size={15} />
              ) : (
                <FileSpreadsheet size={15} />
              )}
              XLSX server-side
            </button>
            <button type="button" className="icon-button" aria-label="Închide" onClick={onClose}>
              <X size={17} />
            </button>
          </div>
        </header>
        <div className="data-inspector-body query-inspector-body">
          <section className="query-metric-dictionary">
            <strong>Dicționar metrică</strong>
            <span>{metric.description}</span>
            <span>Formulă: {metric.formula_reference}</span>
            <span>Missing: {metric.missing_policy}</span>
            <span>
              Sursă: {metric.source_authority} · versiunea {metric.version}
            </span>
          </section>
          {sources.map((source) => (
            <section
              className={`query-source-meta query-source-meta--${source.status}`}
              key={source.domain}
            >
              <strong>
                {source.status.toUpperCase()} · {source.domain} · {source.source}
              </strong>
              <span>
                Cutoff: {source.cutoff ?? '—'} · authority: {source.authority}
              </span>
              {source.warnings.length > 0 ? (
                <span>Warnings: {source.warnings.join(' · ')}</span>
              ) : null}
            </section>
          ))}
          {exportError ? <div className="excel-export-error">{exportError}</div> : null}
          {inspection.isPending ? (
            <div className="empty-state">Se inspectează snapshotul…</div>
          ) : null}
          {inspection.isError ? (
            <div className="page-state page-state--error">
              {inspection.error instanceof Error ? inspection.error.message : 'Inspectul a eșuat.'}
            </div>
          ) : null}
          {inspection.data ? (
            <>
              <div className="query-inspect-summary">
                <span>
                  {inspection.data.total_rows} rânduri · pagina {inspection.data.page} /{' '}
                  {Math.max(1, Math.ceil(inspection.data.total_rows / inspection.data.page_size))}
                </span>
                <div>
                  <button
                    type="button"
                    className="button button--ghost"
                    disabled={inspection.data.page <= 1 || inspection.isFetching}
                    onClick={() => setPage((value) => Math.max(1, value - 1))}
                  >
                    Anterior
                  </button>
                  <button
                    type="button"
                    className="button button--ghost"
                    disabled={
                      inspection.data.page * inspection.data.page_size >=
                        inspection.data.total_rows || inspection.isFetching
                    }
                    onClick={() => setPage((value) => value + 1)}
                  >
                    Următor
                  </button>
                </div>
              </div>
              <DatasetTable dataset={inspection.data.dataset} />
            </>
          ) : null}
        </div>
      </section>
    </div>,
    document.body,
  );
}
