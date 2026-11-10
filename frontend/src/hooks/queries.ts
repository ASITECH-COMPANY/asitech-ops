import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, ApiError } from "../lib/api";
import type {
  Inventory,
  MonitoringOverview,
  Operation,
  OperationName,
  Application,
  ApplicationInput,
  AuditEntry,
  Deployment,
  DeploymentLogLine,
  EnvVar,
  CreatedInvitation,
  CreatedServer,
  Enrollment,
  MetricsRange,
  Server,
  ServerMetrics,
  ServerStatus,
  DashboardSummary,
  Invitation,
  Language,
  Member,
  Organization,
  Paginated,
  Role,
  User,
} from "../lib/types";

export const keys = {
  me: ["me"] as const,
  organizations: ["organizations"] as const,
  organization: (slug: string) => ["org", slug] as const,
  dashboard: (slug: string) => ["org", slug, "dashboard"] as const,
  members: (slug: string) => ["org", slug, "members"] as const,
  invitations: (slug: string) => ["org", slug, "invitations"] as const,
  audit: (slug: string) => ["org", slug, "audit"] as const,
  servers: (slug: string) => ["org", slug, "servers"] as const,
  applications: (slug: string) => ["org", slug, "applications"] as const,
  deployments: (slug: string) => ["org", slug, "deployments"] as const,
  inventory: (slug: string) => ["org", slug, "inventory"] as const,
  monitoring: (slug: string) => ["org", slug, "monitoring"] as const,
  server: (slug: string, id: string) => ["org", slug, "servers", id] as const,
};

// ---- Session ----------------------------------------------------------------------

export function useMe() {
  return useQuery({
    queryKey: keys.me,
    queryFn: () => api<User>("/auth/me/"),
    retry: (count, error) => !(error instanceof ApiError && error.status === 403) && count < 2,
    staleTime: 60_000,
  });
}

export function useLogin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { email: string; password: string }) =>
      api<User>("/auth/login/", { method: "POST", body }),
    onSuccess: (user) => {
      qc.clear();
      qc.setQueryData(keys.me, user);
    },
  });
}

export function useLogout() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api<void>("/auth/logout/", { method: "POST" }),
    onSettled: () => qc.clear(),
  });
}

export function useUpdateProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Partial<{ full_name: string; language: Language }>) =>
      api<User>("/auth/me/", { method: "PATCH", body }),
    onSuccess: (user) => qc.setQueryData(keys.me, user),
  });
}

export function useChangePassword() {
  return useMutation({
    mutationFn: (body: { current_password: string; new_password: string }) =>
      api<void>("/auth/password/change/", { method: "POST", body }),
  });
}

// ---- Organizations ------------------------------------------------------------------

export function useOrganizations(enabled = true) {
  return useQuery({
    queryKey: keys.organizations,
    queryFn: () => api<Organization[]>("/organizations/"),
    enabled,
  });
}

export function useOrganization(slug: string, enabled = true) {
  return useQuery({
    queryKey: keys.organization(slug),
    queryFn: () => api<Organization>(`/organizations/${slug}/`),
    enabled: enabled && slug.length > 0,
    retry: (count, error) => !(error instanceof ApiError && error.status === 404) && count < 2,
  });
}

export function useCreateOrganization() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { name: string; slug?: string }) =>
      api<Organization>("/organizations/", { method: "POST", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.organizations }),
  });
}

export function useUpdateOrganization(slug: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { name: string }) =>
      api<Organization>(`/organizations/${slug}/`, { method: "PATCH", body }),
    onSuccess: (org) => {
      qc.setQueryData(keys.organization(slug), org);
      qc.invalidateQueries({ queryKey: keys.organizations });
    },
  });
}

export function useDeleteOrganization(slug: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api<void>(`/organizations/${slug}/`, { method: "DELETE" }),
    onSuccess: () => {
      qc.removeQueries({ queryKey: ["org", slug] });
      qc.invalidateQueries({ queryKey: keys.organizations });
    },
  });
}

export function useDashboard(slug: string) {
  return useQuery({
    queryKey: keys.dashboard(slug),
    queryFn: () => api<DashboardSummary>(`/organizations/${slug}/dashboard/`),
  });
}

// ---- Members & invitations ----------------------------------------------------------

export function useMembers(slug: string, search: string, page: number) {
  return useQuery({
    queryKey: [...keys.members(slug), { search, page }],
    queryFn: () => api<Paginated<Member>>(`/organizations/${slug}/members/`, { query: { search, page } }),
    placeholderData: keepPreviousData,
  });
}

function invalidateOrg(qc: ReturnType<typeof useQueryClient>, slug: string) {
  return qc.invalidateQueries({ queryKey: ["org", slug] });
}

export function useChangeRole(slug: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ memberId, role }: { memberId: string; role: Role }) =>
      api<Member>(`/organizations/${slug}/members/${memberId}/`, { method: "PATCH", body: { role } }),
    onSuccess: () => invalidateOrg(qc, slug),
  });
}

export function useRemoveMember(slug: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (memberId: string) =>
      api<void>(`/organizations/${slug}/members/${memberId}/`, { method: "DELETE" }),
    onSuccess: () => {
      invalidateOrg(qc, slug);
      qc.invalidateQueries({ queryKey: keys.organizations });
    },
  });
}

export function useInvitations(slug: string, enabled: boolean) {
  return useQuery({
    queryKey: keys.invitations(slug),
    queryFn: () => api<Paginated<Invitation>>(`/organizations/${slug}/invitations/`),
    enabled,
  });
}

export function useCreateInvitation(slug: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { email: string; role: Role }) =>
      api<CreatedInvitation>(`/organizations/${slug}/invitations/`, { method: "POST", body }),
    onSuccess: () => invalidateOrg(qc, slug),
  });
}

export function useRevokeInvitation(slug: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (invitationId: string) =>
      api<void>(`/organizations/${slug}/invitations/${invitationId}/`, { method: "DELETE" }),
    onSuccess: () => invalidateOrg(qc, slug),
  });
}

// ---- Audit ----------------------------------------------------------------------------

export function useAuditLog(slug: string, filters: { action?: string; page: number }) {
  return useQuery({
    queryKey: [...keys.audit(slug), filters],
    queryFn: () =>
      api<Paginated<AuditEntry>>(`/organizations/${slug}/audit-logs/`, {
        query: { action: filters.action, page: filters.page },
      }),
    placeholderData: keepPreviousData,
  });
}

// ---- Servers ---------------------------------------------------------------------------

export function useServers(slug: string, filters: { search: string; status: ServerStatus | ""; page: number }) {
  return useQuery({
    queryKey: [...keys.servers(slug), "list", filters],
    queryFn: () =>
      api<Paginated<Server>>(`/organizations/${slug}/servers/`, {
        query: { search: filters.search, status: filters.status, page: filters.page },
      }),
    placeholderData: keepPreviousData,
    // Status changes arrive over the WebSocket; this only refreshes "last seen".
    refetchInterval: 60_000,
  });
}

export function useServer(slug: string, id: string) {
  return useQuery({
    queryKey: keys.server(slug, id),
    queryFn: () => api<Server>(`/organizations/${slug}/servers/${id}/`),
    retry: (count, error) => !(error instanceof ApiError && error.status === 404) && count < 2,
    refetchInterval: 30_000,
  });
}

export function useServerMetrics(slug: string, id: string, range: MetricsRange) {
  return useQuery({
    queryKey: [...keys.server(slug, id), "metrics", range],
    queryFn: () => api<ServerMetrics>(`/organizations/${slug}/servers/${id}/metrics/`, { query: { range } }),
    placeholderData: keepPreviousData,
    refetchInterval: 60_000,
  });
}

export function useCreateServer(slug: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { name: string; environment: string; project: string }) =>
      api<CreatedServer>(`/organizations/${slug}/servers/`, { method: "POST", body }),
    onSuccess: () => invalidateOrg(qc, slug),
  });
}

export function useUpdateServer(slug: string, id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Partial<{ name: string; environment: string; project: string }>) =>
      api<Server>(`/organizations/${slug}/servers/${id}/`, { method: "PATCH", body }),
    onSuccess: () => invalidateOrg(qc, slug),
  });
}

export function useServerAction(slug: string, id: string) {
  const qc = useQueryClient();
  const onSuccess = () => invalidateOrg(qc, slug);
  return {
    revoke: useMutation({
      mutationFn: () => api<Server>(`/organizations/${slug}/servers/${id}/revoke/`, { method: "POST" }),
      onSuccess,
    }),
    remove: useMutation({
      mutationFn: () => api<void>(`/organizations/${slug}/servers/${id}/`, { method: "DELETE" }),
      onSuccess,
    }),
    enrollment: useMutation({
      mutationFn: () => api<Enrollment>(`/organizations/${slug}/servers/${id}/enrollment/`, { method: "POST" }),
      onSuccess,
    }),
  };
}

// ---- Applications & deployments ----------------------------------------------------------

export function useApplications(slug: string, search = "") {
  return useQuery({
    queryKey: [...keys.applications(slug), "list", search],
    queryFn: () => api<Paginated<Application>>(`/organizations/${slug}/applications/`, { query: { search } }),
    placeholderData: keepPreviousData,
  });
}

export function useApplication(slug: string, id: string) {
  return useQuery({
    queryKey: [...keys.applications(slug), id],
    queryFn: () => api<Application>(`/organizations/${slug}/applications/${id}/`),
    retry: (count, error) => !(error instanceof ApiError && error.status === 404) && count < 2,
  });
}

export function useSaveApplication(slug: string, id?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ApplicationInput) =>
      id
        ? api<Application>(`/organizations/${slug}/applications/${id}/`, { method: "PATCH", body })
        : api<Application>(`/organizations/${slug}/applications/`, { method: "POST", body }),
    onSuccess: () => invalidateOrg(qc, slug),
  });
}

export function useDeleteApplication(slug: string, id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      api<{ containers_removal_sent: boolean }>(`/organizations/${slug}/applications/${id}/`, { method: "DELETE" }),
    onSuccess: () => invalidateOrg(qc, slug),
  });
}

export function useEnvironment(slug: string, id: string, enabled = true) {
  return useQuery({
    queryKey: [...keys.applications(slug), id, "env"],
    queryFn: () => api<EnvVar[]>(`/organizations/${slug}/applications/${id}/environment/`),
    enabled,
  });
}

export function useSetEnvironment(slug: string, id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (variables: { key: string; value?: string | null; is_secret: boolean }[]) =>
      api<EnvVar[]>(`/organizations/${slug}/applications/${id}/environment/`, {
        method: "PUT",
        body: { variables },
      }),
    onSuccess: (data) => qc.setQueryData([...keys.applications(slug), id, "env"], data),
  });
}

export function useAppDeployments(slug: string, id: string, page: number) {
  return useQuery({
    queryKey: [...keys.deployments(slug), "app", id, page],
    queryFn: () =>
      api<Paginated<Deployment>>(`/organizations/${slug}/applications/${id}/deployments/`, { query: { page } }),
    placeholderData: keepPreviousData,
  });
}

export function useDeployments(slug: string, page: number) {
  return useQuery({
    queryKey: [...keys.deployments(slug), "all", page],
    queryFn: () => api<Paginated<Deployment>>(`/organizations/${slug}/deployments/`, { query: { page } }),
    placeholderData: keepPreviousData,
  });
}

export function useDeployment(slug: string, id: string) {
  return useQuery({
    queryKey: [...keys.deployments(slug), id],
    queryFn: () => api<Deployment>(`/organizations/${slug}/deployments/${id}/`),
    retry: (count, error) => !(error instanceof ApiError && error.status === 404) && count < 2,
    refetchInterval: (query) =>
      query.state.data && ["queued", "running"].includes(query.state.data.status) ? 3_000 : false,
  });
}

export function deploymentLogs(slug: string, id: string, after: number) {
  return api<{ status: Deployment["status"]; lines: DeploymentLogLine[] }>(
    `/organizations/${slug}/deployments/${id}/logs/`,
    { query: { after } },
  );
}

export function useDeploy(slug: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (appId: string) =>
      api<Deployment>(`/organizations/${slug}/applications/${appId}/deployments/`, { method: "POST" }),
    onSuccess: () => invalidateOrg(qc, slug),
  });
}

export function useRollback(slug: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (deploymentId: string) =>
      api<Deployment>(`/organizations/${slug}/deployments/${deploymentId}/rollback/`, { method: "POST" }),
    onSuccess: () => invalidateOrg(qc, slug),
  });
}

// ---- Infrastructure (Phase 4) ---------------------------------------------------------------

export function useInventory(slug: string, serverId: string) {
  return useQuery({
    queryKey: [...keys.inventory(slug), serverId],
    queryFn: () => api<Inventory>(`/organizations/${slug}/servers/${serverId}/inventory/`),
    // The agent pushes a fresh inventory every minute (WebSocket event); this is a fallback.
    refetchInterval: 90_000,
  });
}

export function useMonitoring(slug: string) {
  return useQuery({
    queryKey: keys.monitoring(slug),
    queryFn: () => api<MonitoringOverview>(`/organizations/${slug}/monitoring/`),
    refetchInterval: 60_000,
  });
}

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

/** Request a Docker operation and wait for the agent's answer (polling, ~65 s max). */
export async function runOperation(
  slug: string,
  serverId: string,
  op: OperationName,
  target = "",
  params: Record<string, unknown> = {},
): Promise<Operation> {
  const base = `/organizations/${slug}/servers/${serverId}/operations/`;
  let operation = await api<Operation>(base, { method: "POST", body: { op, target, params } });
  for (let attempt = 0; operation.status === "pending" && attempt < 130; attempt += 1) {
    await sleep(attempt < 10 ? 300 : 1000);
    operation = await api<Operation>(`${base}${operation.id}/`);
  }
  if (operation.status !== "succeeded") {
    throw new ApiError(502, "operation_failed", operation.error || "The operation failed.");
  }
  return operation;
}

export function useOperation(slug: string, serverId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ op, target, params }: { op: OperationName; target?: string; params?: Record<string, unknown> }) =>
      runOperation(slug, serverId, op, target, params),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.inventory(slug) });
      qc.invalidateQueries({ queryKey: keys.monitoring(slug) });
    },
  });
}

export function useContainerPolicy(slug: string, serverId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (manage_all_containers: boolean) =>
      api<Server>(`/organizations/${slug}/servers/${serverId}/container-policy/`, {
        method: "PUT",
        body: { manage_all_containers },
      }),
    onSuccess: () => invalidateOrg(qc, slug),
  });
}
