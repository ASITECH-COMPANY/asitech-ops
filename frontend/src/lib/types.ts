// Types mirroring the Control Plane API (see /api/docs/ for the OpenAPI schema).

export type Role = "owner" | "admin" | "member" | "viewer";
export const ROLES: Role[] = ["owner", "admin", "member", "viewer"];

export type Permission =
  | "organization.view"
  | "organization.update"
  | "organization.delete"
  | "members.view"
  | "members.manage"
  | "invitations.manage"
  | "audit.view";

export type Language = "en" | "fr";

export interface User {
  id: string;
  email: string;
  full_name: string;
  language: Language;
  is_staff: boolean;
  date_joined: string;
  can_create_organizations: boolean;
}

export interface Organization {
  id: string;
  name: string;
  slug: string;
  created_at: string;
  role: Role;
  permissions: Permission[];
  member_count: number | null;
}

export interface Member {
  id: string;
  user: { id: string; email: string; full_name: string };
  role: Role;
  joined_at: string;
}

export type InvitationStatus = "pending" | "accepted" | "revoked" | "expired";

export interface Invitation {
  id: string;
  email: string;
  role: Role;
  status: InvitationStatus;
  invited_by: string | null;
  created_at: string;
  expires_at: string;
}

export interface CreatedInvitation extends Invitation {
  accept_url: string;
}

export interface InvitationPreview {
  organization: { name: string; slug: string };
  email: string;
  role: Role;
  status: InvitationStatus;
  expires_at: string;
  invited_by: string | null;
  account_exists: boolean;
}

export interface AuditEntry {
  id: string;
  created_at: string;
  action: string;
  actor: { id: string | null; email: string };
  target_type: string;
  target_id: string;
  target_repr: string;
  metadata: Record<string, unknown>;
  ip_address: string | null;
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface DashboardSummary {
  organization: { id: string; name: string; slug: string; role: Role };
  stats: { members: number; pending_invitations: number | null };
  members_by_role: Record<Role, number>;
  recent_activity: AuditEntry[] | null;
}
