import { Link } from '@tanstack/react-router';
import { ChevronsLeft, ChevronsRight, ExternalLink } from 'lucide-react';

import type { Capability } from '../features/identity/schemas';
import { environment } from '../lib/environment';
import { globalSearchSchema } from '../lib/search';
import { navigationItems } from './navigation';

export function Sidebar({
  collapsed,
  onToggle,
  capabilities,
}: {
  collapsed: boolean;
  onToggle: () => void;
  capabilities: readonly Capability[];
}) {
  const visibleItems = navigationItems.filter((item) => capabilities.includes(item.capability));
  return (
    <aside className={`sidebar ${collapsed ? 'sidebar--collapsed' : ''}`}>
      <div className="brand">
        <div className="brand-mark" aria-hidden="true">
          U
        </div>
        <div className="brand-copy">
          <strong>UniHub</strong>
          <span>Insight</span>
        </div>
      </div>
      <nav className="sidebar-nav" aria-label="Navigație principală">
        {visibleItems.map((item) => {
          const Icon = item.icon;
          return (
            <Link
              key={item.to}
              to={item.to}
              search={(previous) => globalSearchSchema.parse(previous)}
              activeOptions={{ exact: item.to === '/' }}
              className="nav-link"
              activeProps={{ className: 'nav-link nav-link--active' }}
              title={collapsed ? item.label : undefined}
            >
              <Icon size={18} strokeWidth={1.9} />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>
      <div className="sidebar-footer">
        <a
          className="retail-link"
          href={environment.retailBaseUrl}
          target="_blank"
          rel="noreferrer"
          title={collapsed ? 'Deschide UniHub Retail' : undefined}
        >
          <ExternalLink size={16} />
          <span>Deschide Retail</span>
        </a>
        <button
          type="button"
          className="sidebar-toggle"
          onClick={onToggle}
          aria-label={collapsed ? 'Extinde meniul' : 'Restrânge meniul'}
        >
          {collapsed ? <ChevronsRight size={17} /> : <ChevronsLeft size={17} />}
          <span>{collapsed ? 'Extinde' : 'Restrânge'}</span>
        </button>
      </div>
    </aside>
  );
}
