import { describe, expect, it } from 'vitest';

import {
  dashboardCanDelete,
  dashboardCanEdit,
  dashboardCanManageSharing,
  preserveAclOnContentUpdate,
} from '../src/features/dashboards/permissions';
import type { DashboardDocument } from '../src/features/dashboards/schemas';
import type { UserContext } from '../src/features/identity/schemas';

const document = {
  id: 'dash-1',
  name: 'Dash',
  description: '',
  owner_subject: 'owner',
  visibility: 'shared',
  version: 2,
  widgets: [],
  acl: [
    { subject: 'editor', permission: 'edit' },
    { subject: 'admin', permission: 'admin' },
  ],
  scope_ceiling: { firms: ['MOBIUP'], regionals: [], asms: [], stores: [], allow_agent: true },
  query_contract_version: 1,
  created_at: '2026-08-05T00:00:00Z',
  updated_at: '2026-08-05T00:00:00Z',
} satisfies DashboardDocument;

const user = (subject: string, capabilities: UserContext['capabilities'] = []) =>
  ({ subject, capabilities, groups: [], is_demo: false }) satisfies UserContext;

describe('dashboard ACL permissions', () => {
  it('allows edit without allowing non-admin reshare/delete', () => {
    expect(dashboardCanEdit(document, user('editor'))).toBe(true);
    expect(dashboardCanManageSharing(document, user('editor'))).toBe(false);
    expect(dashboardCanDelete(document, user('editor'))).toBe(false);
    expect(dashboardCanManageSharing(document, user('admin'))).toBe(true);
  });

  it('preserves ACL and ceiling during content-only updates', () => {
    const next = preserveAclOnContentUpdate(document, {
      name: 'Renamed',
      description: 'Updated',
      visibility: document.visibility,
      widgets: [],
    });
    expect(next.acl).toEqual(document.acl);
    expect(next.scope_ceiling).toEqual(document.scope_ceiling);
  });
});
