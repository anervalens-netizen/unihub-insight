import { useQueries } from '@tanstack/react-query';
import { useMemo } from 'react';

import { DashboardCanvas } from '../../components/dashboard/DashboardCanvas';
import type { DashboardLayoutItem, DashboardWidgetDefinition } from '../../components/dashboard/types';
import { ErrorState } from '../../components/ui/ErrorState';
import { LoadingState } from '../../components/ui/LoadingState';
import type { GlobalSearch } from '../../lib/search';
import { moduleAnalyticsQuery } from '../modules/api';
import type { ModuleAnalytics, ModuleId } from '../modules/schemas';
import { ConfiguredWidget } from './ConfiguredWidget';
import type { DashboardDocument, DashboardWidget } from './schemas';

export function CustomDashboardPreview({ dashboard, search, editMode, resetToken, onLayoutChange }: { dashboard: DashboardDocument; search: GlobalSearch & { period: string }; editMode: boolean; resetToken: number; onLayoutChange: (items: DashboardLayoutItem[]) => void }) {
  const modules = useMemo(() => [...new Set(dashboard.widgets.map((widget) => widget.module))], [dashboard.widgets]);
  const queries = useQueries({ queries: modules.map((module) => moduleAnalyticsQuery(module, search)) });
  if (queries.some((query) => query.isPending)) return <LoadingState label="Se încarcă dashboardul personalizat…" />;
  const firstError = queries.find((query) => query.isError);
  if (firstError?.error) return <ErrorState message={firstError.error instanceof Error ? firstError.error.message : 'Un modul nu a putut fi încărcat.'} />;
  const dataByModule = new Map<ModuleId, ModuleAnalytics>();
  modules.forEach((module, index) => { const data = queries[index]?.data; if (data) dataByModule.set(module, data); });
  const definitions: DashboardWidgetDefinition[] = dashboard.widgets.map((widget: DashboardWidget) => { const data = dataByModule.get(widget.module); const Component = () => <ConfiguredWidget widget={widget} data={data} />; return { id: widget.id, title: widget.title, subtitle: `${widget.module} · ${widget.metric_id}`, component: Component, x: widget.layout.x, y: widget.layout.y, w: widget.layout.w, h: widget.layout.h, minW: widget.layout.min_w, minH: widget.layout.min_h }; });
  const widgetKey = dashboard.widgets.map((widget) => widget.id).join('|');
  return <DashboardCanvas key={widgetKey} widgets={definitions} editMode={editMode} resetToken={resetToken} storageKey={`unihub-insight:custom:${dashboard.id}:v${dashboard.version}`} onLayoutChange={onLayoutChange} />;
}
