import type { UserContext } from '../identity/schemas';
import type { DashboardAclEntry, DashboardDocument, DashboardPermission } from './schemas';

export function dashboardCanEdit(document: DashboardDocument, user: UserContext): boolean {
  return (
    document.owner_subject === user.subject ||
    user.capabilities.includes('insight:admin') ||
    document.acl.some(
      (entry) =>
        entry.subject === user.subject &&
        (entry.permission === 'edit' || entry.permission === 'admin'),
    )
  );
}

export function dashboardCanManageSharing(document: DashboardDocument, user: UserContext): boolean {
  return (
    document.owner_subject === user.subject ||
    user.capabilities.includes('insight:admin') ||
    document.acl.some((entry) => entry.subject === user.subject && entry.permission === 'admin')
  );
}

export function dashboardCanDelete(document: DashboardDocument, user: UserContext): boolean {
  return dashboardCanManageSharing(document, user);
}

export function preserveAclOnContentUpdate(
  current: DashboardDocument,
  content: Pick<DashboardDocument, 'name' | 'description' | 'visibility' | 'widgets'>,
): Pick<
  DashboardDocument,
  'name' | 'description' | 'visibility' | 'widgets' | 'acl' | 'scope_ceiling'
> {
  return { ...content, acl: current.acl, scope_ceiling: current.scope_ceiling };
}

export function upsertAclEntry(
  entries: readonly DashboardAclEntry[],
  subject: string,
  permission: DashboardPermission,
): DashboardAclEntry[] {
  const filtered = entries.filter((entry) => entry.subject !== subject);
  return [...filtered, { subject, permission }];
}

export function removeAclEntry(
  entries: readonly DashboardAclEntry[],
  subject: string,
): DashboardAclEntry[] {
  return entries.filter((entry) => entry.subject !== subject);
}
