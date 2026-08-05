import { Save, Trash2 } from 'lucide-react';

import type { ModuleId } from '../modules/schemas';
import type { DashboardDocument, DashboardWidget } from './schemas';
import { WidgetEditorRow } from './WidgetEditorRow';

export function DashboardEditor({
  draft,
  availableModules,
  pending,
  onDraftChange,
  onAddWidget,
  onUpdateWidget,
  onRemoveWidget,
  onSave,
  onDelete,
}: {
  draft: DashboardDocument;
  availableModules: ModuleId[];
  pending: boolean;
  onDraftChange: (draft: DashboardDocument) => void;
  onAddWidget: (module: ModuleId) => void;
  onUpdateWidget: (id: string, patch: Partial<DashboardWidget>) => void;
  onRemoveWidget: (id: string) => void;
  onSave: () => void;
  onDelete: () => void;
}) {
  return (
    <div className="dashboard-editor">
      <div className="dashboard-fields">
        <label>
          <span>Nume</span>
          <input
            value={draft.name}
            onChange={(event) => onDraftChange({ ...draft, name: event.target.value })}
          />
        </label>
        <label>
          <span>Descriere</span>
          <textarea
            value={draft.description}
            onChange={(event) => onDraftChange({ ...draft, description: event.target.value })}
          />
        </label>
        <label>
          <span>Vizibilitate</span>
          <select
            value={draft.visibility}
            onChange={(event) =>
              onDraftChange({
                ...draft,
                visibility: event.target.value as DashboardDocument['visibility'],
              })
            }
          >
            <option value="private">Privat</option>
            <option value="shared">Partajat read-only</option>
          </select>
        </label>
      </div>

      <div className="widget-editor-header">
        <h3>Carduri</h3>
        <select
          defaultValue=""
          onChange={(event) => {
            const module = event.target.value as ModuleId;
            if (module) onAddWidget(module);
            event.target.value = '';
          }}
        >
          <option value="">Adaugă un card…</option>
          {availableModules.map((module) => (
            <option key={module} value={module}>
              {module}
            </option>
          ))}
        </select>
      </div>

      <div className="widget-editor-list">
        {draft.widgets.map((widget) => (
          <WidgetEditorRow
            key={widget.id}
            widget={widget}
            availableModules={availableModules}
            onChange={(patch) => onUpdateWidget(widget.id, patch)}
            onRemove={() => onRemoveWidget(widget.id)}
          />
        ))}
      </div>

      <footer>
        <button type="button" className="button button--secondary" onClick={onDelete}>
          <Trash2 size={14} />
          Șterge dashboard
        </button>
        <button
          type="button"
          className="button button--primary"
          disabled={pending}
          onClick={onSave}
        >
          <Save size={14} />
          Salvează configurația
        </button>
      </footer>
    </div>
  );
}
