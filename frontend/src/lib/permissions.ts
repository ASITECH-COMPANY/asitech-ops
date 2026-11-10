import type { Organization, Permission, Role } from "./types";

export function can(org: Pick<Organization, "permissions"> | undefined, permission: Permission): boolean {
  return !!org && org.permissions.includes(permission);
}

/** Mirrors backend rules: admins manage non-owners; only owners touch the owner role. */
export function canAssignRole(actorRole: Role, targetCurrentRole: Role | null, newRole: Role): boolean {
  if (actorRole === "owner") return true;
  if (actorRole !== "admin") return false;
  if (newRole === "owner") return false;
  return targetCurrentRole !== "owner";
}

export function assignableRoles(actorRole: Role): Role[] {
  if (actorRole === "owner") return ["owner", "admin", "member", "viewer"];
  if (actorRole === "admin") return ["admin", "member", "viewer"];
  return [];
}
