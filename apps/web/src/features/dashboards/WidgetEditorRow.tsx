import { CopyPlus, Trash2 } from 'lucide-react';

import { moduleEntityDimension } from '../modules/interactions';
import type { ModuleId } from '../modules/schemas';
import type { MetricDefinition } from '../query/schemas';
import { type DashboardWidget, dashboardWidgetDimensions } from './schemas';
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

function metricAllowsComparison(metric: MetricDefinition | undefined, comparison: string): boolean {
  return metric?.allowed_comparisons.some((allowed) => allowed === comparison) ?? false;
}

function dimensionsForVisualization(
  module: ModuleId,
  visualization: DashboardWidget['visualization'],
  metric: MetricDefinition | undefined,
  dimensions: string[],
): string[] {
  if (!metric) return [];
  if (visualization === 'heatmap') {
    const required = [moduleEntityDimension[module], 'time'];
    return required.every((dimension) => metric.allowed_dimensions.includes(dimension))
      ? required
      : [];
  }
  if (visualization === 'line' || visualization === 'area') {
    return metric.allowed_dimensions.includes('time') ? ['time'] : [];
  }
  return dimensions.slice(0, 1);
}

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
  const selectedDimensions = dashboardWidgetDimensions(widget);
  const allowedComparisons: ReadonlySet<string> = new Set(metric?.allowed_comparisons ?? []);
  const availableComparisonOptions = selectedDimensions.includes('time')
    ? comparisonOptions.filter(([value]) => allowedComparisons.has(value))
    : [];

  const dimensionPatch = (dimensions: string[]): Partial<DashboardWidget> => ({
    dimensions,
    dimension: dimensions[0] ?? null,
    comparisons: dimensions.includes('time')
      ? widget.comparisons.filter((comparison) => allowedComparisons.has(comparison))
      : [],
  });

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
              module === 'planning'
                ? Object.fromEntries(
                    Object.entries(widget.filters).filter(([key]) => key !== 'agent'),
                  )
                : widget.filters;
            const dimensions = dimensionsForVisualization(
              module,
              visualization,
              nextMetric,
              selectedDimensions.filter((dimension) =>
                nextMetric?.allowed_dimensions.includes(dimension),
              ),
            );
            onChange({
              module,
              metric_id: nextMetric?.id ?? widget.metric_id,
              title: nextMetric?.display_name ?? nextMetricReference?.label ?? widget.title,
              visualization,
              ...dimensionPatch(dimensions),
              time_grain: nextMetric?.allowed_grains.includes(widget.time_grain)
                ? widget.time_grain
                : (nextMetric?.allowed_grains[0] ?? 'month'),
              comparisons: widget.comparisons.filter((comparison) =>
                metricAllowsComparison(nextMetric, comparison),
              ),
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
          multiple
          size={widget.visualization === 'heatmap' ? 2 : 1}
          value={selectedDimensions}
          aria-label="Dimensiuni"
          disabled={widget.visualization === 'heatmap'}
          title={
            widget.visualization === 'heatmap'
              ? 'Heatmap folosește perechea fixă entitate × timp.'
              : undefined
          }
          onChange={(event) =>
            onChange(
              dimensionPatch(
                [...event.target.selectedOptions].slice(0, 1).map((option) => option.value),
              ),
            )
          }
        >
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
          {availableComparisonOptions.map(([value, label]) => (
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
          onChange={(event) => {
            const limit = Number(event.target.value) || 1;
            onChange({
              limit,
              options:
                widget.options.top_n && widget.options.top_n > limit
                  ? { ...widget.options, top_n: limit }
                  : widget.options,
            });
          }}
        />
        <select
          value={widget.metric_id}
          aria-label="Metrică"
          onChange={(event) => {
            const nextMetric = metrics.find((item) => item.id === event.target.value);
            if (!nextMetric) return;
            const visualization = nextMetric.allowed_shapes.includes(widget.visualization)
              ? widget.visualization
              : (nextMetric.allowed_shapes[0] ?? 'table');
            const dimensions = dimensionsForVisualization(
              widget.module,
              visualization,
              nextMetric,
              selectedDimensions.filter((dimension) =>
                nextMetric.allowed_dimensions.includes(dimension),
              ),
            );
            onChange({
              metric_id: nextMetric.id,
              metric_version: nextMetric.version,
              query_contract_version: nextMetric.query_contract_version,
              title: nextMetric.display_name,
              visualization,
              ...dimensionPatch(dimensions),
              time_grain: nextMetric.allowed_grains.includes(widget.time_grain)
                ? widget.time_grain
                : (nextMetric.allowed_grains[0] ?? 'month'),
              comparisons: dimensions.includes('time')
                ? widget.comparisons.filter((comparison) =>
                    metricAllowsComparison(nextMetric, comparison),
                  )
                : [],
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
          onChange={(event) => {
            const visualization = event.target.value as DashboardWidget['visualization'];
            onChange({
              visualization,
              ...dimensionPatch(
                dimensionsForVisualization(
                  widget.module,
                  visualization,
                  metric,
                  selectedDimensions,
                ),
              ),
            });
          }}
        >
          {availableVisualizations.map((visualization) => (
            <option key={visualization} value={visualization}>
              {visualization}
            </option>
          ))}
        </select>
        <label>
          <input
            type="checkbox"
            checked={widget.options.show_legend !== false}
            onChange={(event) =>
              onChange({ options: { ...widget.options, show_legend: event.target.checked } })
            }
          />
          Legendă
        </label>
        <label>
          <input
            type="checkbox"
            checked={widget.options.show_labels === true}
            onChange={(event) =>
              onChange({ options: { ...widget.options, show_labels: event.target.checked } })
            }
          />
          Etichete
        </label>
        <label>
          <small>Top N</small>
          <input
            type="number"
            min={1}
            max={widget.limit}
            value={widget.options.top_n ?? ''}
            placeholder="Toate"
            aria-label="Top N prezentat"
            onChange={(event) => {
              const value = event.target.value;
              if (!value) {
                const options = { ...widget.options };
                delete options.top_n;
                onChange({ options });
                return;
              }
              onChange({
                options: {
                  ...widget.options,
                  top_n: Math.min(widget.limit, Math.max(1, Number(value) || 1)),
                },
              });
            }}
          />
        </label>
        {widget.visualization === 'line' || widget.visualization === 'area' ? (
          <label>
            <input
              type="checkbox"
              checked={widget.options.smooth === true}
              onChange={(event) =>
                onChange({ options: { ...widget.options, smooth: event.target.checked } })
              }
            />
            Netezire
          </label>
        ) : null}
        {widget.visualization === 'bar' ? (
          <label>
            <input
              type="checkbox"
              checked={widget.options.stacked === true}
              onChange={(event) =>
                onChange({ options: { ...widget.options, stacked: event.target.checked } })
              }
            />
            Stivuit
          </label>
        ) : null}
        <label>
          <small>PNG</small>
          <select
            aria-label="Rezoluție PNG"
            value={widget.options.pixel_ratio === 1 ? '1' : '2'}
            onChange={(event) =>
              onChange({
                options: {
                  ...widget.options,
                  pixel_ratio: event.target.value === '1' ? 1 : 2,
                },
              })
            }
          >
            <option value="1">1×</option>
            <option value="2">2×</option>
          </select>
        </label>
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
            .filter((field) => field.key !== 'agent' || widget.module !== 'planning')
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
