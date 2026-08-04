import { CopyPlus, Lock, Plus, Share2 } from 'lucide-react';

import type { DashboardDocument } from './schemas';
import type { DashboardTemplate } from './templates';

export function DashboardLibrary({
  documents,
  selectedId,
  templates,
  onSelect,
  onCreateBlank,
  onCreateTemplate,
}: {
  documents: DashboardDocument[];
  selectedId: string | null;
  templates: DashboardTemplate[];
  onSelect: (id: string) => void;
  onCreateBlank: () => void;
  onCreateTemplate: (template: DashboardTemplate) => void;
}) {
  return (
    <aside className="dashboard-library">
      <header>
        <div>
          <span>Bibliotecă</span>
          <h2>Dashboarduri</h2>
        </div>
        <button
          type="button"
          className="icon-button"
          title="Creează dashboard gol"
          onClick={onCreateBlank}
        >
          <Plus size={16} />
        </button>
      </header>

      <div className="dashboard-list">
        {documents.map((document) => (
          <button
            type="button"
            key={document.id}
            className={
              document.id === selectedId
                ? 'dashboard-list-item is-active'
                : 'dashboard-list-item'
            }
            onClick={() => onSelect(document.id)}
          >
            <strong>{document.name}</strong>
            <span>
              {document.widgets.length} carduri · v{document.version}
            </span>
            <small>
              {document.visibility === 'shared' ? <Share2 size={11} /> : <Lock size={11} />}
              {document.visibility}
            </small>
          </button>
        ))}
      </div>

      <div className="dashboard-templates">
        <h3>Template-uri</h3>
        {templates.map((template) => (
          <button
            type="button"
            key={template.id}
            onClick={() => onCreateTemplate(template)}
          >
            <CopyPlus size={14} />
            <span>
              <strong>{template.name}</strong>
              <small>{template.description}</small>
            </span>
          </button>
        ))}
      </div>
    </aside>
  );
}
