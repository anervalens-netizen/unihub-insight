import { useQueries } from '@tanstack/react-query';
import { useMemo } from 'react';

import { DashboardCanvas } from '../../components/dashboard/DashboardCanvas';
import type {
  DashboardLayoutItem,
  DashboardWidgetDefinition,
} from '../../components/dashboard/types';
import { ErrorState } from '../../components/ui/ErrorState';
import { LoadingState } from '../../components/ui/LoadingState';
import type { GlobalSearch } from '../../lib/search';
import { moduleAnalyticsQuery } from '../modules/api';
import { ConfiguredWidget } from './ConfiguredWidget';
import { resolveWidgetSearch } from './filter-resolution';
import type { DashboardDocument, DashboardWidget } from './schemas';

export function CustomDashboardPreview({
  dashboard,
  search,
  editMode,
  resetToken,
  onLayoutChange,
}: {
  dashboard: DashboardDocument;
  search: GlobalSearch & { period: string };
  editMode: boolean;
  resetToken: number;
  onLayoutChange: (items: DashboardLayoutItem[]) => void;
}) {
  const queryInputs = useMemo(
    () => dashboard.widgets.map((widget) => resolveWidgetSearch(search, widget)),
    [dashboard.widgets, search],
  );
  const queries = useQueries({
    queries: dashboard.widgets.map((widget, index) =>
      moduleAnalyticsQuery(widget.module, queryInputs[index] ?? search),
    ),
  });
  if (queries.some((query) => query.isPending))
    return <LoadingState label="Se încarcă dashboardul personalizat…" />;
  const firstError = queries.find((query) => query.isError);
  if (firstError?.error)
    return (
      <ErrorState
        message={
          firstError.error instanceof Error
            ? firstError.error.message
            : 'Un card nu a putut fi încărcat.'
        }
      />
    );
  const definitions: DashboardWidgetDefinition[] = dashboard.widgets.map(
    (widget: DashboardWidget, index) => {
      const data = queries[index]?.data;
      const Component = () => <ConfiguredWidget widget={widget} data={data} />;
      return {
        id: widget.id,
        title: widget.title,
        subtitle: `${widget.module} · ${widget.metric_id}`,
        component: Component,
        x: widget.layout.x,
        y: widget.layout.y,
        w: widget.layout.w,
        h: widget.layout.h,
        minW: widget.layout.min_w,
        minH: widget.layout.min_h,
      };
    },
  );
  const widgetKey = dashboard.widgets.map((widget) => widget.id).join('|');
  return (
    <DashboardCanvas
      key={widgetKey}
      widgets={definitions}
      editMode={editMode}
      resetToken={resetToken}
      storageKey={`unihub-insight:custom:${dashboard.id}:v${dashboard.version}`}
      onLayoutChange={onLayoutChange}
    />
  );
}
