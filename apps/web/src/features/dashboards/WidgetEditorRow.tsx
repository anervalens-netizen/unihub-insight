import { Trash2 } from 'lucide-react';

import type { ModuleId } from '../modules/schemas';
import type { DashboardWidget } from './schemas';
import { moduleMetrics, moduleVisualizations } from './templates';

const filterFields = [
  { key: 'firm', label: 'Firmă', placeholder: 'MOBIUP' },
  { key: 'regional', label: 'RM', placeholder: 'Nume RM' },
  { key: 'asm', label: 'ASM', placeholder: 'Nume ASM' },
  { key: 'stores', label: 'Magazine', placeholder: 'S001,S002' },
  { key: 'agent', label: 'Agent', placeholder: 'Cod/nume agent' },
] as const;

export function WidgetEditorRow({
  widget,
  availableModules,
  onChange,
  onRemove,
}: {
  widget: DashboardWidget;
  availableModules: ModuleId[];
  onChange: (patch: Partial<DashboardWidget>) => void;
  onRemove: () => void;
}) {
  const localFiltersEnabled = widget.filter_mode === 'augment' || widget.filter_mode === 'override';
  return (
    <article className="widget-editor-card">
      <div className="widget-editor-main">
        <input value={widget.title} aria-label="Titlu card" onChange={(event) => onChange({ title: event.target.value })} />
        <select value={widget.module} aria-label="Modul" onChange={(event) => {
          const module = event.target.value as ModuleId;
          const metric = moduleMetrics[module][0];
          const visualization = moduleVisualizations[module].includes(widget.visualization)
            ? widget.visualization
            : moduleVisualizations[module][0] ?? 'kpi';
          const filters = module === 'finance' || module === 'planning'
            ? Object.fromEntries(Object.entries(widget.filters).filter(([key]) => key !== 'agent'))
            : widget.filters;
          onChange({ module, metric_id: metric?.id ?? widget.metric_id, title: metric?.label ?? widget.title, visualization, filters });
        }}>{availableModules.map((module) => <option key={module} value={module}>{module}</option>)}</select>
        <select value={widget.metric_id} aria-label="Metrică" onChange={(event) => onChange({ metric_id: event.target.value, title: moduleMetrics[widget.module].find((metric) => metric.id === event.target.value)?.label ?? widget.title })}>{moduleMetrics[widget.module].map((metric) => <option key={metric.id} value={metric.id}>{metric.label}</option>)}</select>
        <select value={widget.visualization} aria-label="Vizualizare" onChange={(event) => onChange({ visualization: event.target.value as DashboardWidget['visualization'] })}>{moduleVisualizations[widget.module].map((visualization) => <option key={visualization} value={visualization}>{visualization}</option>)}</select>
        <select value={widget.filter_mode} aria-label="Regulă filtre" onChange={(event) => {
          const filterMode = event.target.value as DashboardWidget['filter_mode'];
          onChange({ filter_mode: filterMode, ...(filterMode === 'inherit' || filterMode === 'ignore' ? { filters: {} } : {}) });
        }}><option value="inherit">Moștenește</option><option value="augment">Completează</option><option value="override">Suprascrie</option><option value="ignore">Ignoră global</option></select>
        <button type="button" className="icon-button" aria-label="Șterge cardul" onClick={onRemove}><Trash2 size={14} /></button>
      </div>
      {localFiltersEnabled ? (
        <div className="widget-local-filters">
          <span>Filtre locale</span>
          {filterFields.filter((field) => field.key !== 'agent' || (widget.module !== 'finance' && widget.module !== 'planning')).map((field) => (
            <label key={field.key}><small>{field.label}</small><input value={widget.filters[field.key] ?? ''} placeholder={field.placeholder} onChange={(event) => {
              const value = event.target.value.trim();
              const filters = { ...widget.filters };
              if (value) filters[field.key] = value;
              else delete filters[field.key];
              onChange({ filters });
            }} /></label>
          ))}
        </div>
      ) : null}
    </article>
  );
}
