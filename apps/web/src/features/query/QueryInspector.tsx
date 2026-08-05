import { useQuery } from '@tanstack/react-query';
import { Download, LoaderCircle, X } from 'lucide-react';
import { useMemo, useState } from 'react';
import { createPortal } from 'react-dom';

import type { GlobalSearch } from '../../lib/search';
import {
  buildExportRequest,
  buildInspectRequest,
  exportQueryCsv,
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
  dashboardId: string;
  snapshotId: string;
  search: GlobalSearch & { period: string };
  result: WidgetQueryResult;
  metric: MetricDefinition;
  onClose: () => void;
}) {
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const request = useMemo(
    () => buildInspectRequest(snapshotId, dashboardId, result.query),
    [dashboardId, result.query, snapshotId],
  );
  const inspectQuery = useMemo(() => inspectQueryOptions(request, search, true), [request, search]);
  const inspection = useQuery(inspectQuery);
  const sources = inspection.data
    ? Object.values(inspection.data.snapshot.sources)
    : result.meta?.source
      ? [result.meta.source]
      : [];

  const exportCsv = (): void => {
    setExporting(true);
    setExportError(null);
    void exportQueryCsv(buildExportRequest(snapshotId, dashboardId, result.query), search)
      .then(({ blob, filename }) => {
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = filenameFromDisposition(
          filename,
          `${result.widget_id}-${search.period}.csv`,
        );
        link.click();
        window.setTimeout(() => URL.revokeObjectURL(url), 0);
      })
      .catch((error: unknown) =>
        setExportError(error instanceof Error ? error.message : 'Exportul a eșuat.'),
      )
      .finally(() => setExporting(false));
  };

  return createPortal(
    <div className="widget-modal-backdrop">
      <section
        className="data-inspector"
        role="dialog"
        aria-modal="true"
        aria-labelledby="query-inspector-title"
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
              disabled={exporting}
              onClick={exportCsv}
            >
              {exporting ? <LoaderCircle className="spin" size={15} /> : <Download size={15} />}
              CSV server-side
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
                {inspection.data.total_rows} rânduri · pagina {inspection.data.page}
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
