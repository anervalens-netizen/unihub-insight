import { Save, Trash2, UserRound, X } from 'lucide-react';

import type { ModuleId } from '../modules/schemas';
import type { MetricDefinition } from '../query/schemas';
import { removeAclEntry, upsertAclEntry } from './permissions';
import type {
  DashboardDocument,
  DashboardPermission,
  DashboardSubject,
  DashboardWidget,
} from './schemas';
import { WidgetEditorRow } from './WidgetEditorRow';

export function DashboardEditor({
  draft,
  availableModules,
  metrics,
  pending,
  onDraftChange,
  onAddWidget,
  onUpdateWidget,
  onRemoveWidget,
  onDuplicateWidget,
  onSave,
  onDelete,
  canManageSharing,
  subjects,
  subjectsPending,
}: {
  draft: DashboardDocument;
  availableModules: ModuleId[];
  metrics: MetricDefinition[];
  pending: boolean;
  onDraftChange: (draft: DashboardDocument) => void;
  onAddWidget: (module: ModuleId) => void;
  onUpdateWidget: (id: string, patch: Partial<DashboardWidget>) => void;
  onRemoveWidget: (id: string) => void;
  onDuplicateWidget: (id: string) => void;
  onSave: () => void;
  onDelete?: () => void;
  canManageSharing: boolean;
  subjects: DashboardSubject[];
  subjectsPending: boolean;
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
            disabled={!canManageSharing}
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

      {canManageSharing ? (
        <section className="dashboard-sharing" aria-labelledby="dashboard-sharing-title">
          <div className="dashboard-section-heading">
            <div>
              <span>ACL țintit</span>
              <h3 id="dashboard-sharing-title">Partajare și scope ceiling</h3>
            </div>
            <UserRound size={17} />
          </div>
          <div className="dashboard-sharing-grid">
            <label>
              <span>Subiect autorizat</span>
              <select
                defaultValue=""
                disabled={subjectsPending}
                onChange={(event) => {
                  const subject = event.target.value;
                  if (!subject) return;
                  onDraftChange({
                    ...draft,
                    acl: upsertAclEntry(draft.acl, subject, 'read'),
                  });
                  event.target.value = '';
                }}
              >
                <option value="">Adaugă utilizator…</option>
                {subjects
                  .filter((subject) => subject.subject !== draft.owner_subject)
                  .filter(
                    (subject) => !draft.acl.some((entry) => entry.subject === subject.subject),
                  )
                  .map((subject) => (
                    <option key={subject.subject} value={subject.subject}>
                      {subject.display_name ?? subject.email ?? subject.subject}
                    </option>
                  ))}
              </select>
            </label>
            <label>
              <span>Allow agent în scope</span>
              <input
                type="checkbox"
                checked={draft.scope_ceiling.allow_agent}
                onChange={(event) =>
                  onDraftChange({
                    ...draft,
                    scope_ceiling: { ...draft.scope_ceiling, allow_agent: event.target.checked },
                  })
                }
              />
            </label>
          </div>
          <div className="dashboard-acl-list">
            {draft.acl.length === 0 ? (
              <span className="dashboard-muted">Niciun share explicit.</span>
            ) : null}
            {draft.acl.map((entry) => (
              <div className="dashboard-acl-row" key={entry.subject}>
                <strong>
                  {subjects.find((subject) => subject.subject === entry.subject)?.display_name ??
                    entry.subject}
                </strong>
                <select
                  value={entry.permission}
                  onChange={(event) =>
                    onDraftChange({
                      ...draft,
                      acl: upsertAclEntry(
                        draft.acl,
                        entry.subject,
                        event.target.value as DashboardPermission,
                      ),
                    })
                  }
                >
                  <option value="read">Read</option>
                  <option value="edit">Edit</option>
                  <option value="admin">Admin</option>
                </select>
                <button
                  type="button"
                  className="icon-button"
                  aria-label={`Elimină ${entry.subject} din ACL`}
                  onClick={() =>
                    onDraftChange({ ...draft, acl: removeAclEntry(draft.acl, entry.subject) })
                  }
                >
                  <X size={14} />
                </button>
              </div>
            ))}
          </div>
          <div className="dashboard-ceiling-fields">
            {(['firms', 'regionals', 'asms', 'stores'] as const).map((key) => (
              <label key={key}>
                <span>{key} ceiling</span>
                <input
                  value={draft.scope_ceiling[key].join(',')}
                  placeholder="Gol = fără restricție"
                  onChange={(event) =>
                    onDraftChange({
                      ...draft,
                      scope_ceiling: {
                        ...draft.scope_ceiling,
                        [key]: event.target.value
                          .split(',')
                          .map((value) => value.trim())
                          .filter(Boolean),
                      },
                    })
                  }
                />
              </label>
            ))}
          </div>
        </section>
      ) : (
        <div className="dashboard-readonly-note">
          Permisiunile și scope ceiling sunt păstrate. Doar owner/admin poate reshare sau șterge
          dashboardul.
        </div>
      )}

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
            metrics={metrics}
            onChange={(patch) => onUpdateWidget(widget.id, patch)}
            onRemove={() => onRemoveWidget(widget.id)}
            onDuplicate={() => onDuplicateWidget(widget.id)}
          />
        ))}
      </div>

      <footer>
        {onDelete ? (
          <button type="button" className="button button--secondary" onClick={onDelete}>
            <Trash2 size={14} />
            Șterge dashboard
          </button>
        ) : (
          <span className="dashboard-muted">Ștergerea este rezervată owner/admin.</span>
        )}
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
