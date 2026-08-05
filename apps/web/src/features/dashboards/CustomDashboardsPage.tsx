import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Eye, Lock, Save, Settings2, Share2, Unlock } from 'lucide-react';
import { useCallback, useEffect, useMemo, useState } from 'react';

import { useGlobalSearch } from '../../app/search-hooks';
import type { DashboardLayoutItem } from '../../components/dashboard/types';
import { ErrorState } from '../../components/ui/ErrorState';
import { LoadingState } from '../../components/ui/LoadingState';
import { currentBusinessMonth } from '../../lib/search';
import { useIdentity } from '../identity/context';
import type { Capability } from '../identity/schemas';
import type { ModuleId } from '../modules/schemas';
import { createDashboard, dashboardsQuery, deleteDashboard, updateDashboard } from './api';
import { CustomDashboardPreview } from './CustomDashboardPreview';
import { DashboardEditor } from './DashboardEditor';
import { DashboardLibrary } from './DashboardLibrary';
import type { DashboardDocument, DashboardWidget } from './schemas';
import { dashboardTemplates, moduleMetrics, type DashboardTemplate } from './templates';

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

function nextWidget(module: ModuleId, existing: DashboardWidget[]): DashboardWidget {
  const metric = moduleMetrics[module][0];
  const y = existing.reduce((maximum, item) => Math.max(maximum, item.layout.y + item.layout.h), 0);
  return {
    id: crypto.randomUUID(),
    module,
    title: metric?.label ?? 'Widget nou',
    metric_id: metric?.id ?? 'sales.total',
    visualization: 'kpi',
    dimension: null,
    time_grain: 'month',
    filter_mode: 'inherit',
    filters: {},
    options: {},
    layout: { x: 0, y, w: 6, h: 5, min_w: 4, min_h: 4 },
  };
}

export function CustomDashboardsPage() {
  const identity = useIdentity();
  const search = useGlobalSearch();
  const period = search.period ?? currentBusinessMonth();
  const queryClient = useQueryClient();
  const listQuery = useQuery(dashboardsQuery);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [draft, setDraft] = useState<DashboardDocument | null>(null);
  const [mode, setMode] = useState<'view' | 'configure'>('view');
  const [editLayout, setEditLayout] = useState(false);
  const [resetToken, setResetToken] = useState(0);
  const [message, setMessage] = useState<string | null>(null);

  const documents = listQuery.data?.items ?? [];
  const selected = documents.find((item) => item.id === selectedId) ?? null;

  useEffect(() => {
    if (selected) setDraft(cloneDocument(selected));
  }, [selected]);

  useEffect(() => {
    if (!selectedId && documents[0]) setSelectedId(documents[0].id);
  }, [documents, selectedId]);

  const canEdit = Boolean(
    draft &&
      (draft.owner_subject === identity.subject || identity.capabilities.includes('insight:admin')),
  );

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
      setMessage('Dashboard creat.');
      await queryClient.invalidateQueries({ queryKey: ['dashboards'] });
    },
    onError: (error) => setMessage(error instanceof Error ? error.message : 'Crearea a eșuat.'),
  });
  const updateMutation = useMutation({
    mutationFn: ({ id, document }: { id: string; document: DashboardDocument }) =>
      updateDashboard(id, {
        name: document.name,
        description: document.description,
        visibility: document.visibility,
        widgets: document.widgets,
        version: document.version,
      }),
    onSuccess: async (document) => {
      setDraft(document);
      setMessage('Dashboard salvat.');
      await queryClient.invalidateQueries({ queryKey: ['dashboards'] });
    },
    onError: (error) => setMessage(error instanceof Error ? error.message : 'Salvarea a eșuat.'),
  });
  const deleteMutation = useMutation({
    mutationFn: deleteDashboard,
    onSuccess: async () => {
      setSelectedId(null);
      setDraft(null);
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
    if (draft && canEdit && window.confirm('Ștergi dashboardul?')) {
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
                />
              </>
            ) : canEdit ? (
              <DashboardEditor
                draft={draft}
                availableModules={availableModules}
                pending={updateMutation.isPending}
                onDraftChange={setDraft}
                onAddWidget={(module) =>
                  setDraft({
                    ...draft,
                    widgets: [...draft.widgets, nextWidget(module, draft.widgets)],
                  })
                }
                onUpdateWidget={updateWidget}
                onRemoveWidget={(id) =>
                  setDraft({
                    ...draft,
                    widgets: draft.widgets.filter((item) => item.id !== id),
                  })
                }
                onSave={save}
                onDelete={remove}
              />
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
