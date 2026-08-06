import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { CopyPlus, Eye, Lock, Save, Settings2, Share2, Unlock } from 'lucide-react';
import { lazy, Suspense, useCallback, useEffect, useMemo, useState } from 'react';

import { useGlobalSearch, useUpdateGlobalSearch } from '../../app/search-hooks';
import type { DashboardLayoutItem } from '../../components/dashboard/types';
import { ErrorState } from '../../components/ui/ErrorState';
import { LoadingState } from '../../components/ui/LoadingState';
import { currentBusinessMonth, updateDrillPath } from '../../lib/search';
import { useIdentity } from '../identity/context';
import type { Capability } from '../identity/schemas';
import type { ModuleId } from '../modules/schemas';
import { analyticsCatalogQuery } from '../query/api';
import {
  createDashboard,
  dashboardSubjectsQuery,
  dashboardsQuery,
  dashboardVersionsQuery,
  deleteDashboard,
  updateDashboard,
} from './api';
import { CustomDashboardPreview } from './CustomDashboardPreview';
import { DashboardLibrary } from './DashboardLibrary';
import { dashboardCanDelete, dashboardCanEdit, dashboardCanManageSharing } from './permissions';
import type { DashboardDocument, DashboardWidget } from './schemas';
import { type DashboardTemplate, dashboardTemplates, moduleMetrics } from './templates';

const DashboardEditor = lazy(() =>
  import('./DashboardEditor').then((module) => ({ default: module.DashboardEditor })),
);

const moduleCapability: Record<ModuleId, Capability> = {
  sales: 'insight:analytics',
  performance: 'insight:analytics',
  campaigns: 'insight:analytics',
  workforce: 'insight:management',
  compensation: 'insight:hr',
  finance: 'insight:pnl',
  planning: 'insight:management',
};

function cloneDocument(document: DashboardDocument): DashboardDocument {
  return structuredClone(document);
}

function cloneCreateInput(document: DashboardDocument) {
  return {
    name: `${document.name} (copie)`,
    description: document.description,
    visibility: 'private' as const,
    widgets: document.widgets.map((widget) => ({
      ...structuredClone(widget),
      id: crypto.randomUUID(),
    })),
    scope_ceiling: structuredClone(document.scope_ceiling),
    acl: [],
    query_contract_version: document.query_contract_version,
  };
}

function nextWidget(module: ModuleId, existing: DashboardWidget[]): DashboardWidget {
  const metric = moduleMetrics[module][0];
  const y = existing.reduce((maximum, item) => Math.max(maximum, item.layout.y + item.layout.h), 0);
  return {
    id: crypto.randomUUID(),
    module,
    title: metric?.label ?? 'Widget nou',
    metric_id: metric?.id ?? 'sales.total',
    metric_version: 1,
    query_contract_version: 1,
    visualization: 'kpi',
    dimension: null,
    dimensions: [],
    time_grain: 'month',
    filter_mode: 'inherit',
    filters: {},
    options: {},
    comparisons: [],
    sort: [],
    limit: 30,
    layout: { x: 0, y, w: 6, h: 5, min_w: 4, min_h: 4 },
  };
}

export function CustomDashboardsPage() {
  const identity = useIdentity();
  const search = useGlobalSearch();
  const updateSearch = useUpdateGlobalSearch();
  const period = search.period ?? currentBusinessMonth();
  const queryClient = useQueryClient();
  const listQuery = useQuery(dashboardsQuery);
  const catalogQuery = useQuery(analyticsCatalogQuery());
  const [selectedId, setSelectedId] = useState<string | null>(search.dashboard_id ?? null);
  const [draft, setDraft] = useState<DashboardDocument | null>(null);
  const [mode, setMode] = useState<'view' | 'configure'>('view');
  const [editLayout, setEditLayout] = useState(false);
  const [resetToken, setResetToken] = useState(0);
  const [message, setMessage] = useState<string | null>(null);

  const documents = listQuery.data?.items ?? [];
  const selectedCurrent = documents.find((item) => item.id === selectedId) ?? null;
  const versionsQuery = useQuery({
    ...dashboardVersionsQuery(selectedId ?? ''),
    enabled: Boolean(selectedId),
  });
  const selected =
    versionsQuery.data?.find((item) => item.version === search.dashboard_version) ??
    selectedCurrent;

  useEffect(() => {
    if (selected) setDraft(cloneDocument(selected));
  }, [selected]);

  useEffect(() => {
    if (search.dashboard_id && documents.some((item) => item.id === search.dashboard_id)) {
      if (selectedId !== search.dashboard_id) setSelectedId(search.dashboard_id);
      return;
    }
    if (!selectedId && documents[0]) {
      setSelectedId(documents[0].id);
      updateSearch(
        { dashboard_id: documents[0].id, dashboard_version: documents[0].version },
        true,
      );
    }
  }, [documents, search.dashboard_id, selectedId, updateSearch]);

  useEffect(() => {
    if (selected && search.dashboard_version !== selected.version && !versionsQuery.isFetching) {
      updateSearch({ dashboard_version: selected.version }, true);
    }
  }, [search.dashboard_version, selected, updateSearch, versionsQuery.isFetching]);

  const historical = Boolean(
    selectedCurrent && selected && selected.version !== selectedCurrent.version,
  );
  const canEdit = Boolean(draft && !historical && dashboardCanEdit(draft, identity));
  const canManageSharing = Boolean(
    draft && !historical && dashboardCanManageSharing(draft, identity),
  );
  const canDelete = Boolean(draft && !historical && dashboardCanDelete(draft, identity));
  const subjectsQuery = useQuery({
    ...dashboardSubjectsQuery,
    enabled: canManageSharing,
  });

  useEffect(() => {
    if (!canEdit) {
      setMode('view');
      setEditLayout(false);
    }
  }, [canEdit]);

  const availableModules = useMemo(
    () =>
      (Object.keys(moduleMetrics) as ModuleId[]).filter((module) =>
        identity.capabilities.includes(moduleCapability[module]),
      ),
    [identity.capabilities],
  );
  const availableTemplates = dashboardTemplates.filter((template) =>
    template.requiredCapabilities.every((capability) => identity.capabilities.includes(capability)),
  );

  const createMutation = useMutation({
    mutationFn: createDashboard,
    onSuccess: async (document) => {
      setDraft(document);
      setSelectedId(document.id);
      updateSearch({ dashboard_id: document.id, dashboard_version: document.version }, true);
      setMessage('Dashboard creat.');
      await queryClient.invalidateQueries({ queryKey: ['dashboards'] });
    },
    onError: (error) => setMessage(error instanceof Error ? error.message : 'Crearea a eșuat.'),
  });
  const cloneMutation = useMutation({
    mutationFn: (document: DashboardDocument) => createDashboard(cloneCreateInput(document)),
    onSuccess: async (document) => {
      setDraft(document);
      setSelectedId(document.id);
      updateSearch({ dashboard_id: document.id, dashboard_version: document.version }, true);
      setMessage('Dashboard clonat, privat și fără ACL moștenit.');
      await queryClient.invalidateQueries({ queryKey: ['dashboards'] });
    },
    onError: (error) => setMessage(error instanceof Error ? error.message : 'Clonarea a eșuat.'),
  });
  const updateMutation = useMutation({
    mutationFn: ({ id, document }: { id: string; document: DashboardDocument }) =>
      updateDashboard(id, {
        name: document.name,
        description: document.description,
        visibility: document.visibility,
        widgets: document.widgets,
        acl: document.acl,
        scope_ceiling: document.scope_ceiling,
        query_contract_version: document.query_contract_version,
        version: document.version,
      }),
    onSuccess: async (document) => {
      setDraft(document);
      updateSearch({ dashboard_version: document.version }, true);
      setMessage('Dashboard salvat.');
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['dashboards'] }),
        queryClient.invalidateQueries({ queryKey: ['dashboard-versions', document.id] }),
      ]);
    },
    onError: (error) => setMessage(error instanceof Error ? error.message : 'Salvarea a eșuat.'),
  });
  const deleteMutation = useMutation({
    mutationFn: deleteDashboard,
    onSuccess: async () => {
      setSelectedId(null);
      setDraft(null);
      updateSearch({ dashboard_id: undefined, dashboard_version: undefined }, true);
      setMessage(null);
      await queryClient.invalidateQueries({ queryKey: ['dashboards'] });
    },
    onError: (error) => setMessage(error instanceof Error ? error.message : 'Ștergerea a eșuat.'),
  });

  const updateWidget = (id: string, patch: Partial<DashboardWidget>): void =>
    setDraft((current) =>
      current
        ? {
            ...current,
            widgets: current.widgets.map((widget) =>
              widget.id === id ? { ...widget, ...patch } : widget,
            ),
          }
        : current,
    );

  const duplicateWidget = (id: string): void =>
    setDraft((current) => {
      if (!current) return current;
      const source = current.widgets.find((widget) => widget.id === id);
      if (!source) return current;
      const bottom = current.widgets.reduce(
        (maximum, widget) => Math.max(maximum, widget.layout.y + widget.layout.h),
        0,
      );
      return {
        ...current,
        widgets: [
          ...current.widgets,
          {
            ...structuredClone(source),
            id: crypto.randomUUID(),
            layout: { ...source.layout, x: 0, y: bottom },
          },
        ],
      };
    });

  const applyLayout = useCallback((items: DashboardLayoutItem[]): void => {
    setDraft((current) =>
      current
        ? {
            ...current,
            widgets: current.widgets.map((widget) => {
              const layout = items.find((item) => item.id === widget.id);
              return layout
                ? {
                    ...widget,
                    layout: {
                      x: layout.x,
                      y: layout.y,
                      w: layout.w,
                      h: layout.h,
                      min_w: layout.minW ?? widget.layout.min_w,
                      min_h: layout.minH ?? widget.layout.min_h,
                    },
                  }
                : widget;
            }),
          }
        : current,
    );
  }, []);

  if (listQuery.isPending) return <LoadingState label="Se încarcă dashboardurile…" />;
  if (listQuery.isError) {
    return (
      <ErrorState
        message={
          listQuery.error instanceof Error
            ? listQuery.error.message
            : 'Dashboardurile nu au putut fi încărcate.'
        }
        onRetry={() => void listQuery.refetch()}
      />
    );
  }

  const save = (): void => {
    if (draft && canEdit) updateMutation.mutate({ id: draft.id, document: draft });
  };
  const remove = (): void => {
    if (draft && canDelete && window.confirm('Ștergi dashboardul?')) {
      deleteMutation.mutate(draft.id);
    }
  };
  const createFromTemplate = (template: DashboardTemplate): void => {
    createMutation.mutate({
      name: template.name,
      description: template.description,
      visibility: template.visibility,
      widgets: structuredClone(template.widgets),
    });
  };

  return (
    <section className="dashboard-manager">
      <DashboardLibrary
        documents={documents}
        selectedId={selectedId}
        templates={availableTemplates}
        onSelect={(id) => {
          setSelectedId(id);
          const document = documents.find((item) => item.id === id);
          updateSearch(
            {
              dashboard_id: id,
              dashboard_version: document?.version,
            },
            true,
          );
          setMode('view');
          setMessage(null);
        }}
        onCreateBlank={() =>
          createMutation.mutate({
            name: 'Dashboard nou',
            description: '',
            visibility: 'private',
            widgets: [],
          })
        }
        onCreateTemplate={createFromTemplate}
      />

      <div className="dashboard-workbench">
        {draft ? (
          <>
            <header className="dashboard-workbench-header">
              <div>
                <input
                  className="dashboard-name-input"
                  value={draft.name}
                  readOnly={mode === 'view' || !canEdit}
                  onChange={(event) => setDraft({ ...draft, name: event.target.value })}
                />
                <p>{draft.description || 'Fără descriere'}</p>
                {versionsQuery.data && versionsQuery.data.length > 0 ? (
                  <label className="dashboard-version-picker">
                    <span>Versiune</span>
                    <select
                      value={String(draft.version)}
                      onChange={(event) =>
                        updateSearch({ dashboard_version: Number(event.target.value) })
                      }
                    >
                      {versionsQuery.data.map((version) => (
                        <option key={version.version} value={version.version}>
                          v{version.version}
                        </option>
                      ))}
                    </select>
                  </label>
                ) : null}
                {!canEdit ? (
                  <span className="save-message">
                    <Share2 size={11} /> Partajat read-only
                  </span>
                ) : message ? (
                  <span className="save-message">{message}</span>
                ) : null}
              </div>
              <div className="dashboard-mode">
                <button
                  type="button"
                  className="button button--ghost"
                  disabled={cloneMutation.isPending}
                  onClick={() => cloneMutation.mutate(draft)}
                >
                  <CopyPlus size={14} />
                  Clonează
                </button>
                <button
                  type="button"
                  className={mode === 'view' ? 'is-active' : ''}
                  onClick={() => setMode('view')}
                >
                  <Eye size={14} />
                  Vizualizare
                </button>
                {canEdit ? (
                  <button
                    type="button"
                    className={mode === 'configure' ? 'is-active' : ''}
                    onClick={() => setMode('configure')}
                  >
                    <Settings2 size={14} />
                    Configurare
                  </button>
                ) : null}
              </div>
            </header>

            {mode === 'view' ? (
              <>
                {canEdit ? (
                  <div className="dashboard-preview-toolbar">
                    <button
                      type="button"
                      className="button button--secondary"
                      onClick={() => setEditLayout((value) => !value)}
                    >
                      {editLayout ? <Lock size={14} /> : <Unlock size={14} />}
                      {editLayout ? 'Blochează layout' : 'Editează layout'}
                    </button>
                    {editLayout ? (
                      <button
                        type="button"
                        className="button button--ghost"
                        onClick={() => setResetToken((value) => value + 1)}
                      >
                        Layout implicit
                      </button>
                    ) : null}
                    <button
                      type="button"
                      className="button button--primary"
                      disabled={updateMutation.isPending}
                      onClick={save}
                    >
                      <Save size={14} />
                      Salvează
                    </button>
                  </div>
                ) : null}
                <CustomDashboardPreview
                  dashboard={draft}
                  search={{ ...search, period }}
                  editMode={canEdit && editLayout}
                  resetToken={resetToken}
                  onLayoutChange={canEdit ? applyLayout : () => undefined}
                  onUrlStateChange={(event) => {
                    updateSearch({
                      drill: updateDrillPath(search.drill, {
                        dimension: event.dimensionId,
                        value: event.value,
                        label: event.label,
                      }),
                      ...(event.dimensionId === 'store' ||
                      event.dimensionId === 'site_code' ||
                      event.dimensionId === 'id'
                        ? { stores: event.value }
                        : {}),
                    });
                  }}
                  onUrlStateReset={() => updateSearch({ drill: undefined, stores: undefined })}
                />
              </>
            ) : canEdit ? (
              <Suspense fallback={<LoadingState label="Se încarcă editorul…" />}>
                <DashboardEditor
                  draft={draft}
                  availableModules={availableModules}
                  metrics={catalogQuery.data?.metrics ?? []}
                  pending={updateMutation.isPending}
                  canManageSharing={canManageSharing}
                  subjects={subjectsQuery.data ?? []}
                  subjectsPending={subjectsQuery.isPending}
                  onDraftChange={setDraft}
                  onAddWidget={(module) =>
                    setDraft({
                      ...draft,
                      widgets: [...draft.widgets, nextWidget(module, draft.widgets)],
                    })
                  }
                  onUpdateWidget={updateWidget}
                  onDuplicateWidget={duplicateWidget}
                  onRemoveWidget={(id) =>
                    setDraft({
                      ...draft,
                      widgets: draft.widgets.filter((item) => item.id !== id),
                    })
                  }
                  onSave={save}
                  {...(canDelete ? { onDelete: remove } : {})}
                />
              </Suspense>
            ) : null}
          </>
        ) : (
          <div className="dashboard-empty">
            <h2>Creează primul dashboard</h2>
            <p>Alege un template sau pornește de la un canvas gol.</p>
          </div>
        )}
      </div>
    </section>
  );
}
