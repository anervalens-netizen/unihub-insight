import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { CopyPlus, Eye, Lock, Plus, Save, Settings2, Share2, Trash2, Unlock } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';

import { useGlobalSearch } from '../../app/search-hooks';
import type { DashboardLayoutItem } from '../../components/dashboard/types';
import { ErrorState } from '../../components/ui/ErrorState';
import { LoadingState } from '../../components/ui/LoadingState';
import { currentBusinessMonth } from '../../lib/search';
import { useIdentity } from '../identity/context';
import type { ModuleId } from '../modules/schemas';
import { createDashboard, dashboardsQuery, deleteDashboard, updateDashboard } from './api';
import { CustomDashboardPreview } from './CustomDashboardPreview';
import type { DashboardDocument, DashboardWidget } from './schemas';
import { compatibleVisualizations, dashboardTemplates, moduleMetrics } from './templates';

const moduleCapability: Record<ModuleId, string> = { sales: 'insight:analytics', performance: 'insight:analytics', campaigns: 'insight:analytics', workforce: 'insight:management', compensation: 'insight:hr', finance: 'insight:pnl', planning: 'insight:management' };

function cloneDocument(document: DashboardDocument): DashboardDocument {
  return structuredClone(document);
}

function nextWidget(module: ModuleId, existing: DashboardWidget[]): DashboardWidget {
  const metrics = moduleMetrics[module];
  const metric = metrics[0];
  const y = existing.reduce((maximum, item) => Math.max(maximum, item.layout.y + item.layout.h), 0);
  return { id: crypto.randomUUID(), module, title: metric?.label ?? 'Widget nou', metric_id: metric?.id ?? 'sales.total', visualization: 'kpi', dimension: null, time_grain: 'month', filter_mode: 'inherit', filters: {}, options: {}, layout: { x: 0, y, w: 6, h: 5, min_w: 4, min_h: 4 } };
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
  useEffect(() => { if (selected) setDraft(cloneDocument(selected)); }, [selected]);
  useEffect(() => { if (!selectedId && documents[0]) setSelectedId(documents[0].id); }, [documents, selectedId]);

  const availableModules = useMemo(() => (Object.keys(moduleMetrics) as ModuleId[]).filter((module) => identity.capabilities.includes(moduleCapability[module] as never)), [identity.capabilities]);
  const availableTemplates = dashboardTemplates.filter((template) => template.requiredCapabilities.every((capability) => identity.capabilities.includes(capability as never)));

  const createMutation = useMutation({ mutationFn: createDashboard, onSuccess: async (document) => { await queryClient.invalidateQueries({ queryKey: ['dashboards'] }); setSelectedId(document.id); setMessage('Dashboard creat.'); } });
  const updateMutation = useMutation({ mutationFn: ({ id, document }: { id: string; document: DashboardDocument }) => updateDashboard(id, { name: document.name, description: document.description, visibility: document.visibility, widgets: document.widgets, version: document.version }), onSuccess: async (document) => { await queryClient.invalidateQueries({ queryKey: ['dashboards'] }); setDraft(document); setMessage('Dashboard salvat.'); } });
  const deleteMutation = useMutation({ mutationFn: deleteDashboard, onSuccess: async () => { setSelectedId(null); setDraft(null); await queryClient.invalidateQueries({ queryKey: ['dashboards'] }); } });

  if (listQuery.isPending) return <LoadingState label="Se încarcă dashboardurile…" />;
  if (listQuery.isError) return <ErrorState message={listQuery.error instanceof Error ? listQuery.error.message : 'Dashboardurile nu au putut fi încărcate.'} onRetry={() => void listQuery.refetch()} />;

  const updateWidget = (id: string, patch: Partial<DashboardWidget>): void => setDraft((current) => current ? { ...current, widgets: current.widgets.map((widget) => widget.id === id ? { ...widget, ...patch } : widget) } : current);
  const applyLayout = (items: DashboardLayoutItem[]): void => setDraft((current) => current ? { ...current, widgets: current.widgets.map((widget) => { const layout = items.find((item) => item.id === widget.id); return layout ? { ...widget, layout: { x: layout.x, y: layout.y, w: layout.w, h: layout.h, min_w: layout.minW ?? widget.layout.min_w, min_h: layout.minH ?? widget.layout.min_h } } : widget; }) } : current);

  return <section className="dashboard-manager">
    <aside className="dashboard-library"><header><div><span>Bibliotecă</span><h2>Dashboarduri</h2></div><button type="button" className="icon-button" title="Creează dashboard gol" onClick={() => createMutation.mutate({ name: 'Dashboard nou', description: '', visibility: 'private', widgets: [] })}><Plus size={16} /></button></header><div className="dashboard-list">{documents.map((document) => <button type="button" key={document.id} className={document.id === selectedId ? 'dashboard-list-item is-active' : 'dashboard-list-item'} onClick={() => { setSelectedId(document.id); setMode('view'); }}><strong>{document.name}</strong><span>{document.widgets.length} carduri · v{document.version}</span><small>{document.visibility === 'shared' ? <Share2 size={11} /> : <Lock size={11} />}{document.visibility}</small></button>)}</div><div className="dashboard-templates"><h3>Template-uri</h3>{availableTemplates.map((template) => <button type="button" key={template.id} onClick={() => createMutation.mutate({ name: template.name, description: template.description, visibility: template.visibility, widgets: structuredClone(template.widgets) })}><CopyPlus size={14} /><span><strong>{template.name}</strong><small>{template.description}</small></span></button>)}</div></aside>
    <div className="dashboard-workbench">{draft ? <><header className="dashboard-workbench-header"><div><input className="dashboard-name-input" value={draft.name} readOnly={mode === 'view'} onChange={(event) => setDraft({ ...draft, name: event.target.value })} /><p>{draft.description || 'Fără descriere'}</p>{message ? <span className="save-message">{message}</span> : null}</div><div className="dashboard-mode"><button type="button" className={mode === 'view' ? 'is-active' : ''} onClick={() => setMode('view')}><Eye size={14} />Vizualizare</button><button type="button" className={mode === 'configure' ? 'is-active' : ''} onClick={() => setMode('configure')}><Settings2 size={14} />Configurare</button></div></header>
      {mode === 'view' ? <><div className="dashboard-preview-toolbar"><button type="button" className="button button--secondary" onClick={() => setEditLayout((value) => !value)}>{editLayout ? <Lock size={14} /> : <Unlock size={14} />}{editLayout ? 'Blochează layout' : 'Editează layout'}</button>{editLayout ? <button type="button" className="button button--ghost" onClick={() => setResetToken((value) => value + 1)}>Layout implicit</button> : null}<button type="button" className="button button--primary" disabled={updateMutation.isPending} onClick={() => updateMutation.mutate({ id: draft.id, document: draft })}><Save size={14} />Salvează</button></div><CustomDashboardPreview dashboard={draft} search={{ ...search, period }} editMode={editLayout} resetToken={resetToken} onLayoutChange={applyLayout} /></> : <div className="dashboard-editor"><div className="dashboard-fields"><label><span>Nume</span><input value={draft.name} onChange={(event) => setDraft({ ...draft, name: event.target.value })} /></label><label><span>Descriere</span><textarea value={draft.description} onChange={(event) => setDraft({ ...draft, description: event.target.value })} /></label><label><span>Vizibilitate</span><select value={draft.visibility} onChange={(event) => setDraft({ ...draft, visibility: event.target.value as DashboardDocument['visibility'] })}><option value="private">Privat</option><option value="shared">Partajat read-only</option></select></label></div><div className="widget-editor-header"><h3>Carduri</h3><select defaultValue="" onChange={(event) => { const module = event.target.value as ModuleId; if (module) setDraft({ ...draft, widgets: [...draft.widgets, nextWidget(module, draft.widgets)] }); event.target.value = ''; }}><option value="">Adaugă un card…</option>{availableModules.map((module) => <option key={module} value={module}>{module}</option>)}</select></div><div className="widget-editor-list">{draft.widgets.map((widget) => <article key={widget.id}><input value={widget.title} onChange={(event) => updateWidget(widget.id, { title: event.target.value })} /><select value={widget.module} onChange={(event) => { const module = event.target.value as ModuleId; const metric = moduleMetrics[module][0]; updateWidget(widget.id, { module, metric_id: metric?.id ?? widget.metric_id, title: metric?.label ?? widget.title }); }}>{availableModules.map((module) => <option key={module} value={module}>{module}</option>)}</select><select value={widget.metric_id} onChange={(event) => updateWidget(widget.id, { metric_id: event.target.value, title: moduleMetrics[widget.module].find((metric) => metric.id === event.target.value)?.label ?? widget.title })}>{moduleMetrics[widget.module].map((metric) => <option key={metric.id} value={metric.id}>{metric.label}</option>)}</select><select value={widget.visualization} onChange={(event) => updateWidget(widget.id, { visualization: event.target.value as DashboardWidget['visualization'] })}>{compatibleVisualizations.map((visualization) => <option key={visualization} value={visualization}>{visualization}</option>)}</select><select value={widget.filter_mode} onChange={(event) => updateWidget(widget.id, { filter_mode: event.target.value as DashboardWidget['filter_mode'] })}><option value="inherit">Moștenește</option><option value="augment">Completează</option><option value="override">Suprascrie</option><option value="ignore">Ignoră</option></select><button type="button" className="icon-button" aria-label="Șterge cardul" onClick={() => setDraft({ ...draft, widgets: draft.widgets.filter((item) => item.id !== widget.id) })}><Trash2 size={14} /></button></article>)}</div><footer><button type="button" className="button button--secondary" onClick={() => { if (window.confirm('Ștergi dashboardul?')) deleteMutation.mutate(draft.id); }}><Trash2 size={14} />Șterge dashboard</button><button type="button" className="button button--primary" disabled={updateMutation.isPending} onClick={() => updateMutation.mutate({ id: draft.id, document: draft })}><Save size={14} />Salvează configurația</button></footer></div>}</> : <div className="dashboard-empty"><h2>Creează primul dashboard</h2><p>Alege un template sau pornește de la un canvas gol.</p></div>}</div>
  </section>;
}
