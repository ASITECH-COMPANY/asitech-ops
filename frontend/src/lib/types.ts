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
  | "audit.view"
  | "servers.view"
  | "servers.manage";

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

export type ServerStatus = "pending" | "online" | "offline" | "revoked";

export interface ServerFacts {
  hostname?: string;
  os_name?: string;
  os_version?: string;
  kernel?: string;
  architecture?: string;
  cpu_count?: number;
  memory_total?: number;
  disk_total?: number;
  docker_version?: string;
  agent_version?: string;
}

export interface Server {
  id: string;
  name: string;
  environment: string;
  project: string;
  status: ServerStatus;
  facts: ServerFacts;
  last_seen_at: string | null;
  last_ip: string | null;
  enrolled_at: string | null;
  created_at: string;
}

export interface Enrollment {
  token: string;
  command: string;
  expires_at: string;
  control_plane_url: string;
}

export interface CreatedServer extends Server {
  enrollment: Enrollment;
}

export type MetricsRange = "1h" | "6h" | "24h" | "7d";

export interface MetricPoint {
  ts: string;
  cpu_percent: number | null;
  load1: number | null;
  memory_used: number | null;
  memory_total: number | null;
  disk_used: number | null;
  disk_total: number | null;
  net_rx_rate: number | null;
  net_tx_rate: number | null;
}

export interface ServerMetrics {
  range: MetricsRange;
  step_seconds: number;
  points: MetricPoint[];
}

export interface DashboardSummary {
  organization: { id: string; name: string; slug: string; role: Role };
  stats: { members: number; servers: number; pending_invitations: number | null };
  servers_by_status: Record<ServerStatus, number>;
  members_by_role: Record<Role, number>;
  recent_activity: AuditEntry[] | null;
}
