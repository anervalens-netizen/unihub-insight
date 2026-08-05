import { useQuery } from '@tanstack/react-query';
import { Lock, RefreshCw, RotateCcw, Unlock } from 'lucide-react';
import { useMemo, useState } from 'react';

import { useGlobalSearch, useUpdateGlobalSearch } from '../../app/search-hooks';
import { DashboardCanvas } from '../../components/dashboard/DashboardCanvas';
import { ExcelExportButton } from '../../components/ui/ExcelExportButton';
import { ErrorState } from '../../components/ui/ErrorState';
import { LoadingState } from '../../components/ui/LoadingState';
import { analyticsSearchParams } from '../../lib/download';
import { formatDate, formatMonth } from '../../lib/format';
import { currentBusinessMonth } from '../../lib/search';
import { useIdentity } from '../identity/context';
import { moduleAnalyticsQuery } from './api';
import { ModuleProvider } from './context';
import { DataInspector } from './DataInspector';
import type { ModuleId } from './schemas';
import { moduleWidgets } from './widget-catalog';

export function AnalyticsModulePage({ module }: { module: ModuleId }) {
  const search = useGlobalSearch();
  const updateSearch = useUpdateGlobalSearch();
  const identity = useIdentity();
  const period = search.period ?? currentBusinessMonth();
  const input = useMemo(() => ({ ...search, period }), [period, search]);
  const incompatibleAgent = Boolean(
    search.agent && (module === 'finance' || module === 'planning'),
  );
  const query = useQuery({
    ...moduleAnalyticsQuery(module, input),
    enabled: !incompatibleAgent,
  });
  const [editMode, setEditMode] = useState(false);
  const [resetToken, setResetToken] = useState(0);
  const [inspectWidget, setInspectWidget] = useState<string | null>(null);

  if (incompatibleAgent) {
    return (
      <ErrorState
        title="Filtru incompatibil"
        message="Finance și Planning funcționează la nivel de rețea, structură și magazin, nu la nivel de agent."
        onRetry={() => updateSearch({ agent: undefined }, true)}
      />
    );
  }
  if (query.isPending) return <LoadingState label="Se construiește analiza…" />;
  if (query.isError) {
    return (
      <ErrorState
        message={query.error instanceof Error ? query.error.message : 'Eroare necunoscută.'}
        onRetry={() => void query.refetch()}
      />
    );
  }

  const data = query.data;
  if (!identity.capabilities.includes(data.required_capability)) {
    return (
      <ErrorState
        title="Acces indisponibil"
        message={`Modulul necesită capabilitatea ${data.required_capability}.`}
      />
    );
  }
  const widgets = moduleWidgets(data);
  return (
    <ModuleProvider data={data}>
      <section className="overview-toolbar" aria-label="Starea analizei">
        <div className="overview-meta">
          <span className="meta-chip meta-chip--strong">{formatMonth(data.meta.period)}</span>
          <span className="meta-chip">Scope: {data.meta.scope_label}</span>
          <span className="meta-chip">Cutoff: {formatDate(data.meta.as_of)}</span>
          <span className={`meta-chip data-mode data-mode--${data.meta.data_mode}`}>
            {data.meta.data_mode === 'demo' ? 'Date demo deterministe' : 'PostgreSQL live'}
          </span>
          <span className="meta-chip">Sursă: {data.meta.source}</span>
        </div>
        <div className="overview-actions">
          <ExcelExportButton
            path={`/exports/modules/${module}.xlsx`}
            params={analyticsSearchParams(input)}
            filename={`${module}-${period}.xlsx`}
          />
          <button
            type="button"
            className="button button--secondary"
            onClick={() => void query.refetch()}
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
          Trage cardurile din antet și redimensionează-le. Layoutul local este versionat separat
          pentru fiecare modul.
        </div>
      ) : null}
      <DashboardCanvas
        widgets={widgets}
        editMode={editMode}
        resetToken={resetToken}
        storageKey={`unihub-insight:${module}-layout:v2`}
        onInspect={setInspectWidget}
      />
      {inspectWidget ? (
        <DataInspector
          widgetId={inspectWidget}
          data={data}
          onClose={() => setInspectWidget(null)}
        />
      ) : null}
    </ModuleProvider>
  );
}
