import { CopyPlus, Trash2 } from 'lucide-react';

import type { ModuleId } from '../modules/schemas';
import type { MetricDefinition } from '../query/schemas';
import type { DashboardWidget } from './schemas';
import { moduleMetrics } from './templates';

const filterFields = [
  { key: 'firm', label: 'Firmă', placeholder: 'MOBIUP' },
  { key: 'regional', label: 'RM', placeholder: 'Nume RM' },
  { key: 'asm', label: 'ASM', placeholder: 'Nume ASM' },
  { key: 'stores', label: 'Magazine', placeholder: 'S001,S002' },
  { key: 'agent', label: 'Agent', placeholder: 'Cod/nume agent' },
] as const;
const comparisonOptions = [
  ['target', 'Target'],
  ['forecast', 'Forecast'],
  ['previous-period', 'Perioadă precedentă'],
  ['previous-year', 'Anul trecut'],
  ['recent-average', 'Media recentă'],
] as const;

export function WidgetEditorRow({
  widget,
  availableModules,
  metrics,
  onChange,
  onRemove,
  onDuplicate,
}: {
  widget: DashboardWidget;
  availableModules: ModuleId[];
  metrics: MetricDefinition[];
  onChange: (patch: Partial<DashboardWidget>) => void;
  onRemove: () => void;
  onDuplicate: () => void;
}) {
  const localFiltersEnabled = widget.filter_mode === 'augment' || widget.filter_mode === 'override';
  const moduleMetricIds = new Set(moduleMetrics[widget.module].map((metric) => metric.id));
  const availableMetrics = metrics.filter((metric) => moduleMetricIds.has(metric.id));
  const metric = metrics.find((item) => item.id === widget.metric_id);
  const availableDimensions = metric?.allowed_dimensions ?? [];
  const availableGrains = metric?.allowed_grains ?? ['month'];
  const availableVisualizations = metric?.allowed_shapes ?? ['table'];

  return (
    <article className="widget-editor-card">
      <div className="widget-editor-main">
        <input
          value={widget.title}
          aria-label="Titlu card"
          onChange={(event) => onChange({ title: event.target.value })}
        />
        <select
          value={widget.module}
          aria-label="Modul"
          onChange={(event) => {
            const module = event.target.value as ModuleId;
            const nextMetricReference = moduleMetrics[module][0];
            const nextMetric = metrics.find((item) => item.id === nextMetricReference?.id);
            const visualization = nextMetric?.allowed_shapes.includes(widget.visualization)
              ? widget.visualization
              : (nextMetric?.allowed_shapes[0] ?? 'table');
            const filters =
              module === 'finance' || module === 'planning'
                ? Object.fromEntries(
                    Object.entries(widget.filters).filter(([key]) => key !== 'agent'),
                  )
                : widget.filters;
            onChange({
              module,
              metric_id: nextMetric?.id ?? widget.metric_id,
              title: nextMetric?.display_name ?? nextMetricReference?.label ?? widget.title,
              visualization,
              dimension:
                widget.dimension && nextMetric?.allowed_dimensions.includes(widget.dimension)
                  ? widget.dimension
                  : null,
              time_grain: nextMetric?.allowed_grains.includes(widget.time_grain)
                ? widget.time_grain
                : (nextMetric?.allowed_grains[0] ?? 'month'),
              filters,
            });
          }}
        >
          {availableModules.map((module) => (
            <option key={module} value={module}>
              {module}
            </option>
          ))}
        </select>
        <select
          value={widget.dimension ?? ''}
          aria-label="Dimensiune"
          onChange={(event) => onChange({ dimension: event.target.value || null })}
        >
          <option value="">Fără dimensiune</option>
          {availableDimensions.map((dimension) => (
            <option key={dimension} value={dimension}>
              {dimension}
            </option>
          ))}
        </select>
        <select
          value={widget.time_grain}
          aria-label="Grain"
          onChange={(event) => onChange({ time_grain: event.target.value })}
        >
          {availableGrains.map((grain) => (
            <option key={grain} value={grain}>
              {grain}
            </option>
          ))}
        </select>
        <select
          multiple
          size={2}
          value={widget.comparisons}
          aria-label="Comparații"
          onChange={(event) =>
            onChange({
              comparisons: [...event.target.selectedOptions].map((option) => option.value),
            })
          }
        >
          {comparisonOptions.map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
        <input
          value={widget.sort.join(',')}
          aria-label="Sortare"
          placeholder="primary:desc"
          onChange={(event) =>
            onChange({
              sort: event.target.value
                .split(',')
                .map((value) => value.trim())
                .filter(Boolean),
            })
          }
        />
        <input
          type="number"
          min={1}
          max={5000}
          value={widget.limit}
          aria-label="Limită rânduri"
          onChange={(event) => onChange({ limit: Number(event.target.value) || 1 })}
        />
        <select
          value={widget.metric_id}
          aria-label="Metrică"
          onChange={(event) => {
            const nextMetric = metrics.find((item) => item.id === event.target.value);
            if (!nextMetric) return;
            onChange({
              metric_id: nextMetric.id,
              metric_version: nextMetric.version,
              query_contract_version: nextMetric.query_contract_version,
              title: nextMetric.display_name,
              visualization: nextMetric.allowed_shapes.includes(widget.visualization)
                ? widget.visualization
                : (nextMetric.allowed_shapes[0] ?? 'table'),
              dimension:
                widget.dimension && nextMetric.allowed_dimensions.includes(widget.dimension)
                  ? widget.dimension
                  : null,
              time_grain: nextMetric.allowed_grains.includes(widget.time_grain)
                ? widget.time_grain
                : (nextMetric.allowed_grains[0] ?? 'month'),
            });
          }}
        >
          {availableMetrics.map((item) => (
            <option key={item.id} value={item.id}>
              {item.display_name}
            </option>
          ))}
        </select>
        <select
          value={widget.visualization}
          aria-label="Vizualizare"
          onChange={(event) =>
            onChange({
              visualization: event.target.value as DashboardWidget['visualization'],
            })
          }
        >
          {availableVisualizations.map((visualization) => (
            <option key={visualization} value={visualization}>
              {visualization}
            </option>
          ))}
        </select>
        <select
          value={widget.filter_mode}
          aria-label="Regulă filtre"
          onChange={(event) => {
            const filterMode = event.target.value as DashboardWidget['filter_mode'];
            onChange({
              filter_mode: filterMode,
              ...(filterMode === 'inherit' || filterMode === 'ignore' ? { filters: {} } : {}),
            });
          }}
        >
          <option value="inherit">Moștenește</option>
          <option value="augment">Completează</option>
          <option value="override">Suprascrie</option>
          <option value="ignore">Ignoră global</option>
        </select>
        <button
          type="button"
          className="icon-button"
          aria-label="Duplică cardul"
          onClick={onDuplicate}
        >
          <CopyPlus size={14} />
        </button>
        <button type="button" className="icon-button" aria-label="Șterge cardul" onClick={onRemove}>
          <Trash2 size={14} />
        </button>
      </div>

      {localFiltersEnabled ? (
        <div className="widget-local-filters">
          <span>Filtre locale</span>
          {filterFields
            .filter(
              (field) =>
                (widget.module !== 'compensation' || field.key === 'firm') &&
                (field.key !== 'agent' ||
                  (widget.module !== 'finance' && widget.module !== 'planning')),
            )
            .map((field) => (
              <label key={field.key}>
                <small>{field.label}</small>
                <input
                  value={widget.filters[field.key] ?? ''}
                  placeholder={field.placeholder}
                  onChange={(event) => {
                    const rawValue = event.target.value;
                    const filters = { ...widget.filters };
                    if (rawValue.trim()) filters[field.key] = rawValue;
                    else delete filters[field.key];
                    onChange({ filters });
                  }}
                />
              </label>
            ))}
        </div>
      ) : null}
    </article>
  );
}
