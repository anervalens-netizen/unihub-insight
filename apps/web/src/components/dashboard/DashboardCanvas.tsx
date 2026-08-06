import { GridStack, type GridStackNode, type GridStackWidget } from 'gridstack';
import 'gridstack/dist/gridstack.min.css';
import { useEffect, useMemo, useRef } from 'react';

import type { DashboardLayoutItem, DashboardWidgetDefinition } from './types';
import { WidgetFrame } from './WidgetFrame';

const STORAGE_VERSION = 2;
interface StoredLayout {
  version: number;
  items: DashboardLayoutItem[];
}

function readLayout(
  storageKey: string,
  defaults: DashboardWidgetDefinition[],
): DashboardLayoutItem[] {
  try {
    const raw = localStorage.getItem(storageKey);
    if (!raw) return defaults;
    const parsed = JSON.parse(raw) as StoredLayout;
    if (parsed.version !== STORAGE_VERSION || !Array.isArray(parsed.items)) return defaults;
    const known = new Set(defaults.map((item) => item.id));
    const valid = parsed.items.filter((item) => known.has(item.id));
    return valid.length === defaults.length ? valid : defaults;
  } catch {
    return defaults;
  }
}

function toStoredItem(node: GridStackNode): DashboardLayoutItem | null {
  if (!node.id || node.x === undefined || node.y === undefined || !node.w || !node.h) return null;
  return {
    id: String(node.id),
    x: node.x,
    y: node.y,
    w: node.w,
    h: node.h,
    ...(node.minW ? { minW: node.minW } : {}),
    ...(node.minH ? { minH: node.minH } : {}),
  };
}

export function DashboardCanvas({
  widgets,
  editMode,
  resetToken,
  storageKey,
  onInspect,
  onExport,
  onLayoutChange,
}: {
  widgets: DashboardWidgetDefinition[];
  editMode: boolean;
  resetToken: number;
  storageKey: string;
  onInspect?: (widgetId: string) => void;
  onExport?: (widgetId: string) => void;
  onLayoutChange?: (items: DashboardLayoutItem[]) => void;
}) {
  const hostRef = useRef<HTMLDivElement>(null);
  const gridRef = useRef<GridStack | null>(null);
  const previousResetToken = useRef(resetToken);
  const layoutCallbackRef = useRef(onLayoutChange);
  layoutCallbackRef.current = onLayoutChange;
  const initialLayout = useMemo(() => readLayout(storageKey, widgets), [storageKey, widgets]);
  const layoutById = useMemo(
    () => new Map(initialLayout.map((item) => [item.id, item])),
    [initialLayout],
  );

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    const grid = GridStack.init(
      {
        column: 24,
        cellHeight: 28,
        margin: 10,
        float: false,
        animate: true,
        staticGrid: true,
        handle: '.widget-drag-handle',
        resizable: { handles: 'e,se,s,sw,w' },
        minRow: 1,
      },
      host,
    );
    if (!grid) return;
    gridRef.current = grid;
    const persist = (): void => {
      const items = (grid.save(false) as GridStackWidget[])
        .map((item) => toStoredItem(item as GridStackNode))
        .filter((item): item is DashboardLayoutItem => item !== null);
      localStorage.setItem(
        storageKey,
        JSON.stringify({ version: STORAGE_VERSION, items } satisfies StoredLayout),
      );
      layoutCallbackRef.current?.(items);
    };
    grid.on('change', persist);
    return () => {
      grid.off('change');
      grid.destroy(false);
      gridRef.current = null;
    };
  }, [storageKey]);

  useEffect(() => {
    gridRef.current?.setStatic(!editMode);
  }, [editMode]);

  useEffect(() => {
    if (previousResetToken.current === resetToken) return;
    previousResetToken.current = resetToken;
    const grid = gridRef.current;
    if (!grid) return;
    const defaults: DashboardLayoutItem[] = widgets.map((widget) => ({
      id: widget.id,
      x: widget.x,
      y: widget.y,
      w: widget.w,
      h: widget.h,
      ...(widget.minW === undefined ? {} : { minW: widget.minW }),
      ...(widget.minH === undefined ? {} : { minH: widget.minH }),
    }));
    grid.batchUpdate();
    for (const widget of widgets) {
      const element = hostRef.current?.querySelector<HTMLElement>(`[gs-id="${widget.id}"]`);
      if (element)
        grid.update(element, {
          x: widget.x,
          y: widget.y,
          w: widget.w,
          h: widget.h,
          ...(widget.minW === undefined ? {} : { minW: widget.minW }),
          ...(widget.minH === undefined ? {} : { minH: widget.minH }),
        });
    }
    grid.batchUpdate(false);
    localStorage.removeItem(storageKey);
    layoutCallbackRef.current?.(defaults);
  }, [resetToken, storageKey, widgets]);

  return (
    <div ref={hostRef} className={`grid-stack insight-grid ${editMode ? 'is-editing' : ''}`}>
      {widgets.map((widget) => {
        const position = layoutById.get(widget.id) ?? widget;
        const Widget = widget.component;
        const inspectProps =
          onInspect && widget.inspectable !== false
            ? { onInspect: () => onInspect(widget.id) }
            : {};
        const exportProps =
          onExport && widget.inspectable !== false ? { onExport: () => onExport(widget.id) } : {};
        return (
          <div
            key={widget.id}
            className="grid-stack-item"
            gs-id={widget.id}
            gs-x={position.x}
            gs-y={position.y}
            gs-w={position.w}
            gs-h={position.h}
            gs-min-w={widget.minW}
            gs-min-h={widget.minH}
          >
            <div className="grid-stack-item-content">
              <WidgetFrame
                title={widget.title}
                editMode={editMode}
                {...(widget.subtitle === undefined ? {} : { subtitle: widget.subtitle })}
                {...inspectProps}
                {...exportProps}
              >
                <Widget />
              </WidgetFrame>
            </div>
          </div>
        );
      })}
    </div>
  );
}
