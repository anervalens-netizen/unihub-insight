import { useQuery } from '@tanstack/react-query';
import { Lock, RefreshCw, RotateCcw, Unlock } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';

import { useGlobalSearch, useUpdateGlobalSearch } from '../../app/search-hooks';
import { DashboardCanvas } from '../../components/dashboard/DashboardCanvas';
import { ErrorState } from '../../components/ui/ErrorState';
import { ExcelExportButton } from '../../components/ui/ExcelExportButton';
import { LoadingState } from '../../components/ui/LoadingState';
import { analyticsSearchParams } from '../../lib/download';
import { formatDate, formatMonth } from '../../lib/format';
import { currentBusinessMonth, updateDrillPath } from '../../lib/search';
import { useIdentity } from '../identity/context';
import { moduleAnalyticsQuery } from './api';
import { ModuleProvider } from './context';
import { DataInspector } from './DataInspector';
import type { ModuleAnalytics, ModuleId } from './schemas';
import { type ModuleSubview, moduleSubviewConfig, subviewForId, subviewStatus } from './subviews';
import { moduleWidgets } from './widget-catalog';

function SubviewNavigation({
  views,
  selected,
  statuses,
  onSelect,
}: {
  views: readonly ModuleSubview[];
  selected: ModuleSubview;
  statuses: ReadonlyMap<string, ReturnType<typeof subviewStatus>>;
  onSelect: (id: ModuleSubview['id']) => void;
}) {
  return (
    <nav className="module-subview-nav" aria-label="Sub-view analiză">
      {views.map((view) => {
        const status = statuses.get(view.id);
        return (
          <button
            type="button"
            key={view.id}
            className={view.id === selected.id ? 'module-subview is-active' : 'module-subview'}
            onClick={() => onSelect(view.id)}
          >
            <span>{view.label}</span>
            <small
              className={`availability-dot availability-dot--${status?.availability ?? 'unavailable'}`}
            >
              {status?.availability === 'available'
                ? 'LIVE'
                : status?.availability === 'partial'
                  ? 'PARTIAL'
                  : 'UNAVAILABLE'}
            </small>
          </button>
        );
      })}
    </nav>
  );
}

function SourceMetadataStrip({ data }: { data: ModuleAnalytics }) {
  const sources = Object.values(data.meta.sources ?? {});
  return (
    <section className="module-source-strip" aria-labelledby="module-source-metadata-title">
      <h3 id="module-source-metadata-title" className="sr-only">
        Metadata surse
      </h3>
      {data.meta.range_start && data.meta.range_end ? (
        <span className="meta-chip">
          Interval: {data.meta.range_start} → {data.meta.range_end}
        </span>
      ) : null}
      {data.meta.warnings?.map((warning) => (
        <span className="meta-chip meta-chip--warning" key={warning}>
          {warning}
        </span>
      ))}
      {sources.length === 0 ? (
        <span className="meta-chip meta-chip--warning">Metadata sursă indisponibilă</span>
      ) : (
        sources.map((source) => (
          <details className="source-meta" key={source.domain}>
            <summary>
              <span>{source.domain}</span>
              <strong className={`source-status source-status--${source.status}`}>
                {source.status}
              </strong>
            </summary>
            <div>
              <span>{source.source}</span>
              <span>Cutoff: {source.cutoff ?? '—'}</span>
              <span>Autoritate: {source.authority}</span>
              {source.warnings.length > 0 ? (
                <span>Warnings: {source.warnings.join(' · ')}</span>
              ) : null}
            </div>
          </details>
        ))
      )}
    </section>
  );
}

export function AnalyticsModulePage({ module }: { module: ModuleId }) {
  const search = useGlobalSearch();
  const updateSearch = useUpdateGlobalSearch();
  const identity = useIdentity();
  const period = search.period ?? currentBusinessMonth();
  const input = useMemo(() => ({ ...search, period }), [period, search]);
  const views = moduleSubviewConfig[module];
  const selectedSubview = subviewForId(module, search.subview);
  useEffect(() => {
    if (search.subview !== selectedSubview.id) updateSearch({ subview: selectedSubview.id }, true);
  }, [search.subview, selectedSubview.id, updateSearch]);
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
  const statuses = new Map(views.map((view) => [view.id, subviewStatus(data, view)]));
  const status = statuses.get(selectedSubview.id);
  const widgets =
    status?.availability === 'unavailable' ? [] : moduleWidgets(data, selectedSubview.id);
  const handleUrlState = (event: { dimensionId: string; value: string; label: string | null }) => {
    updateSearch({
      drill: updateDrillPath(search.drill, {
        dimension: event.dimensionId,
        value: event.value,
        label: event.label,
      }),
      ...(event.dimensionId === 'store' || event.dimensionId === 'site_code'
        ? { stores: event.value }
        : {}),
    });
  };
  return (
    <ModuleProvider
      data={data}
      onUrlStateChange={handleUrlState}
      onUrlStateReset={() => updateSearch({ drill: undefined, stores: undefined })}
    >
      <SubviewNavigation
        views={views}
        selected={selectedSubview}
        statuses={statuses}
        onSelect={(id) => updateSearch({ subview: id })}
      />
      <section className="module-view-heading">
        <div>
          <span>Sub-view specializat</span>
          <h2>{selectedSubview.label}</h2>
          <p>{selectedSubview.description}</p>
        </div>
        {status ? (
          <div className={`module-contract-state module-contract-state--${status.availability}`}>
            <strong>
              {status.availability === 'available'
                ? 'Contract disponibil'
                : status.availability === 'partial'
                  ? 'Contract parțial'
                  : 'Contract lipsă'}
            </strong>
            <span>{status.reason}</span>
          </div>
        ) : null}
      </section>
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
      <SourceMetadataStrip data={data} />
      {editMode ? (
        <div className="edit-notice">
          Trage cardurile din antet și redimensionează-le. Layoutul local este versionat separat
          pentru fiecare modul.
        </div>
      ) : null}
      {status?.availability === 'unavailable' ? (
        <div className="module-unavailable" role="status">
          <strong>{selectedSubview.label} nu este disponibil</strong>
          <span>{status.reason}</span>
          <small>
            Contractul lipsă nu este înlocuit cu cifre din alt mecanism sau din altă generație.
          </small>
        </div>
      ) : (
        <DashboardCanvas
          widgets={widgets}
          editMode={editMode}
          resetToken={resetToken}
          storageKey={`unihub-insight:${module}-${selectedSubview.id}-layout:v2`}
          onInspect={setInspectWidget}
        />
      )}
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
