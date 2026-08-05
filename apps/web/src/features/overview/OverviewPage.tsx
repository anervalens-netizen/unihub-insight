import { useQuery } from '@tanstack/react-query';
import { LayoutGrid, Lock, RefreshCw, RotateCcw, Unlock } from 'lucide-react';
import { useMemo, useState } from 'react';

import { useGlobalSearch } from '../../app/search-hooks';
import { DashboardCanvas } from '../../components/dashboard/DashboardCanvas';
import { ExcelExportButton } from '../../components/ui/ExcelExportButton';
import { ErrorState } from '../../components/ui/ErrorState';
import { LoadingState } from '../../components/ui/LoadingState';
import { analyticsSearchParams } from '../../lib/download';
import { formatDate, formatMonth } from '../../lib/format';
import { currentBusinessMonth } from '../../lib/search';
import { overviewQuery } from './api';
import { OverviewProvider } from './context';
import { overviewWidgets } from './widget-catalog';

export function OverviewPage() {
  const search = useGlobalSearch();
  const period = search.period ?? currentBusinessMonth();
  const queryInput = useMemo(() => ({ ...search, period }), [period, search]);
  const overview = useQuery(overviewQuery(queryInput));
  const [editMode, setEditMode] = useState(false);
  const [resetToken, setResetToken] = useState(0);

  if (overview.isPending) return <LoadingState />;
  if (overview.isError) {
    return (
      <ErrorState
        message={overview.error instanceof Error ? overview.error.message : 'Eroare necunoscută.'}
        onRetry={() => void overview.refetch()}
      />
    );
  }

  const data = overview.data;
  return (
    <OverviewProvider data={data}>
      <section className="overview-toolbar" aria-label="Starea analizei">
        <div className="overview-meta">
          <span className="meta-chip meta-chip--strong">{formatMonth(data.meta.period)}</span>
          <span className="meta-chip">Scope: {data.meta.scope_label}</span>
          <span className="meta-chip">Cutoff: {formatDate(data.meta.as_of)}</span>
          <span className={`meta-chip data-mode data-mode--${data.meta.data_mode}`}>
            {data.meta.data_mode === 'demo' ? 'Date demo deterministe' : 'PostgreSQL live'}
          </span>
          {overview.isFetching ? (
            <span className="meta-chip meta-chip--sync">Actualizare…</span>
          ) : null}
        </div>
        <div className="overview-actions">
          <ExcelExportButton
            path="/exports/overview.xlsx"
            params={analyticsSearchParams(queryInput)}
            filename={`overview-${period}.xlsx`}
          />
          <button
            type="button"
            className="button button--secondary"
            onClick={() => void overview.refetch()}
          >
            <RefreshCw size={15} />
            Actualizează
          </button>
          {editMode ? (
            <button
              type="button"
              className="button button--ghost"
              onClick={() => setResetToken((value) => value + 1)}
            >
              <RotateCcw size={15} />
              Layout implicit
            </button>
          ) : null}
          <button
            type="button"
            className={`button ${editMode ? 'button--primary' : 'button--secondary'}`}
            onClick={() => setEditMode((value) => !value)}
          >
            {editMode ? <Lock size={15} /> : <Unlock size={15} />}
            {editMode ? 'Salvează layout' : 'Editează layout'}
          </button>
        </div>
      </section>

      {editMode ? (
        <div className="edit-notice">
          <LayoutGrid size={16} />
          Trage cardurile din antet și redimensionează-le din margini. Layoutul se salvează local
          automat.
        </div>
      ) : null}

      <DashboardCanvas
        widgets={overviewWidgets}
        editMode={editMode}
        resetToken={resetToken}
        storageKey="unihub-insight:overview-layout:v1"
      />
    </OverviewProvider>
  );
}
