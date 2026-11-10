import { LogOut, Search, Trash2, UserPlus, X } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useNavigate, useOutletContext } from "react-router";

import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card, CardHeader, PageHeader } from "../components/ui/Card";
import { CopyField } from "../components/ui/CopyField";
import { ConfirmDialog, Modal } from "../components/ui/Dialog";
import { Alert, Select, SelectField, TextField } from "../components/ui/Field";
import { Pagination } from "../components/ui/Pagination";
import { EmptyState, ErrorState, Spinner } from "../components/ui/States";
import {
  useChangeRole,
  useCreateInvitation,
  useInvitations,
  useMe,
  useMembers,
  useRemoveMember,
  useRevokeInvitation,
} from "../hooks/queries";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { useLanguage, useT } from "../i18n";
import { ApiError } from "../lib/api";
import { formatDate, formatRelative, initials } from "../lib/format";
import { assignableRoles, can, canAssignRole } from "../lib/permissions";
import type { CreatedInvitation, Invitation, Member, Organization, Role } from "../lib/types";
import type { OrgContext } from "./OrgLayout";

function errorMessage(error: unknown): string | null {
  if (!error) return null;
  return error instanceof ApiError ? error.displayMessage : String(error);
}

function InviteDialog({ org, open, onClose }: { org: Organization; open: boolean; onClose: () => void }) {
  const t = useT();
  const create = useCreateInvitation(org.slug);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<Role>("member");
  const [created, setCreated] = useState<CreatedInvitation | null>(null);
  const roles = assignableRoles(org.role);

  const close = () => {
    setEmail("");
    setRole("member");
    setCreated(null);
    create.reset();
    onClose();
  };

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    create.mutate({ email, role }, { onSuccess: setCreated });
  };
  const error = create.error instanceof ApiError ? create.error : null;

  if (created) {
    return (
      <Modal
        open={open}
        onClose={close}
        title={t("invitations.createdTitle")}
        description={t("invitations.createdHelp", { email: created.email })}
        footer={<Button onClick={close}>{t("common.close")}</Button>}
      >
        <CopyField label={t("invitations.link")} value={created.accept_url} />
      </Modal>
    );
  }

  return (
    <Modal
      open={open}
      onClose={close}
      title={t("invitations.dialogTitle")}
      description={t("invitations.dialogHelp")}
      footer={
        <>
          <Button variant="secondary" onClick={close}>
            {t("common.cancel")}
          </Button>
          <Button type="submit" form="invite-form" loading={create.isPending} disabled={!email}>
            {create.isPending ? t("invitations.sending") : t("invitations.send")}
          </Button>
        </>
      }
    >
      <form id="invite-form" className="space-y-4" onSubmit={onSubmit} noValidate>
        {error && !error.fieldError("email") ? <Alert>{error.displayMessage}</Alert> : null}
        <TextField
          label={t("invitations.email")}
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          error={error?.fieldError("email")}
          required
          data-autofocus
        />
        <SelectField label={t("members.role")} value={role} onChange={(e) => setRole(e.target.value as Role)}>
          {roles.map((value) => (
            <option key={value} value={value}>
              {t(`role.${value}`)}
            </option>
          ))}
        </SelectField>
      </form>
    </Modal>
  );
}

function InvitationsCard({ org }: { org: Organization }) {
  const t = useT();
  const language = useLanguage();
  const { data, error, isPending, refetch } = useInvitations(org.slug, true);
  const revoke = useRevokeInvitation(org.slug);
  const [target, setTarget] = useState<Invitation | null>(null);

  return (
    <Card className="mb-6">
      <CardHeader title={t("invitations.title")} />
      {isPending ? (
        <Spinner />
      ) : error ? (
        <ErrorState error={error} onRetry={() => refetch()} />
      ) : data.results.length === 0 ? (
        <EmptyState title={t("invitations.empty")} />
      ) : (
        <ul className="divide-y divide-line">
          {data.results.map((invitation) => (
            <li key={invitation.id} className="flex flex-wrap items-center gap-3 px-5 py-3">
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-fg">{invitation.email}</p>
                <p className="text-xs text-muted">
                  {t("invitations.invitedBy")} {invitation.invited_by ?? "—"} ·{" "}
                  {t("invitations.expires")} {formatRelative(invitation.expires_at, language)}
                </p>
              </div>
              <Badge tone="primary">{t(`role.${invitation.role}`)}</Badge>
              <Button variant="ghost" size="sm" icon={<X className="size-4" />} onClick={() => setTarget(invitation)}>
                {t("invitations.revoke")}
              </Button>
            </li>
          ))}
        </ul>
      )}
      <ConfirmDialog
        open={target !== null}
        onClose={() => {
          setTarget(null);
          revoke.reset();
        }}
        onConfirm={() => target && revoke.mutate(target.id, { onSuccess: () => setTarget(null) })}
        title={t("invitations.revokeTitle", { email: target?.email ?? "" })}
        description={t("invitations.revokeBody")}
        confirmLabel={t("invitations.revoke")}
        loading={revoke.isPending}
        error={errorMessage(revoke.error)}
      />
    </Card>
  );
}

function MemberRow({
  member,
  org,
  isSelf,
  onRemove,
}: {
  member: Member;
  org: Organization;
  isSelf: boolean;
  onRemove: (member: Member) => void;
}) {
  const t = useT();
  const language = useLanguage();
  const changeRole = useChangeRole(org.slug);
  const canManage = can(org, "members.manage");
  const options = assignableRoles(org.role).filter((role) => canAssignRole(org.role, member.role, role));
  const editable = canManage && canAssignRole(org.role, member.role, member.role) && options.length > 0;
  const name = member.user.full_name || member.user.email;

  return (
    <tr className="align-middle">
      <td className="px-5 py-3">
        <div className="flex items-center gap-3">
          <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-surface-2 text-xs font-semibold text-muted">
            {initials(name)}
          </span>
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-fg">
              {name} {isSelf ? <span className="font-normal text-muted">({t("common.you")})</span> : null}
            </p>
            <p className="truncate text-xs text-muted">{member.user.email}</p>
          </div>
        </div>
      </td>
      <td className="px-5 py-3">
        {editable ? (
          <div>
            <Select
              aria-label={`${t("members.role")}: ${name}`}
              value={member.role}
              disabled={changeRole.isPending}
              onChange={(e) => changeRole.mutate({ memberId: member.id, role: e.target.value as Role })}
            >
              {options.map((role) => (
                <option key={role} value={role}>
                  {t(`role.${role}`)}
                </option>
              ))}
            </Select>
            {changeRole.error ? <p className="mt-1 text-xs text-danger">{errorMessage(changeRole.error)}</p> : null}
          </div>
        ) : (
          <Badge tone={member.role === "owner" ? "accent" : member.role === "admin" ? "primary" : "neutral"}>
            {t(`role.${member.role}`)}
          </Badge>
        )}
      </td>
      <td className="hidden px-5 py-3 text-sm text-muted md:table-cell">{formatDate(member.joined_at, language)}</td>
      <td className="px-5 py-3 text-right">
        {isSelf ? (
          <Button variant="ghost" size="sm" icon={<LogOut className="size-4" />} onClick={() => onRemove(member)}>
            {t("members.leave")}
          </Button>
        ) : editable ? (
          <Button variant="ghost" size="sm" icon={<Trash2 className="size-4" />} onClick={() => onRemove(member)}>
            {t("members.remove")}
          </Button>
        ) : null}
      </td>
    </tr>
  );
}

export function MembersPage() {
  const t = useT();
  const navigate = useNavigate();
  const { org } = useOutletContext<OrgContext>();
  useDocumentTitle(t("members.title"), org.name);
  const { data: me } = useMe();
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [inviteOpen, setInviteOpen] = useState(false);
  const [removing, setRemoving] = useState<Member | null>(null);
  const members = useMembers(org.slug, search, page);
  const remove = useRemoveMember(org.slug);
  const canInvite = can(org, "invitations.manage");
  const removingSelf = removing?.user.id === me?.id;
  const removingName = removing ? removing.user.full_name || removing.user.email : "";

  return (
    <>
      <PageHeader
        title={t("members.title")}
        description={t("members.subtitle", { org: org.name })}
        actions={
          canInvite ? (
            <Button icon={<UserPlus className="size-4" />} onClick={() => setInviteOpen(true)}>
              {t("members.invite")}
            </Button>
          ) : null
        }
      />

      {canInvite ? <InvitationsCard org={org} /> : null}

      <Card>
        <div className="border-b border-line px-5 py-3">
          <label className="relative block max-w-sm">
            <span className="sr-only">{t("common.search")}</span>
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" aria-hidden />
            <input
              type="search"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              placeholder={t("members.search")}
              className="h-9 w-full rounded-lg border border-line bg-surface pl-9 pr-3 text-sm text-fg placeholder:text-muted focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/25"
            />
          </label>
        </div>
        {members.isPending ? (
          <Spinner />
        ) : members.error ? (
          <ErrorState error={members.error} onRetry={() => members.refetch()} />
        ) : members.data.results.length === 0 ? (
          <EmptyState title={t("members.empty")} />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[36rem] text-left">
              <thead className="border-b border-line text-xs uppercase tracking-wide text-muted">
                <tr>
                  <th scope="col" className="px-5 py-2.5 font-medium">{t("members.name")}</th>
                  <th scope="col" className="px-5 py-2.5 font-medium">{t("members.role")}</th>
                  <th scope="col" className="hidden px-5 py-2.5 font-medium md:table-cell">{t("members.joined")}</th>
                  <th scope="col" className="px-5 py-2.5 text-right font-medium">
                    <span className="sr-only">{t("members.actions")}</span>
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {members.data.results.map((member) => (
                  <MemberRow
                    key={member.id}
                    member={member}
                    org={org}
                    isSelf={member.user.id === me?.id}
                    onRemove={setRemoving}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
        {members.data ? <Pagination page={page} count={members.data.count} onPage={setPage} /> : null}
      </Card>

      <InviteDialog org={org} open={inviteOpen} onClose={() => setInviteOpen(false)} />

      <ConfirmDialog
        open={removing !== null}
        onClose={() => {
          setRemoving(null);
          remove.reset();
        }}
        onConfirm={() =>
          removing &&
          remove.mutate(removing.id, {
            onSuccess: () => {
              setRemoving(null);
              if (removingSelf) navigate("/", { replace: true });
            },
          })
        }
        title={
          removingSelf ? t("members.leaveTitle", { org: org.name }) : t("members.removeTitle", { name: removingName })
        }
        description={
          removingSelf ? t("members.leaveBody") : t("members.removeBody", { name: removingName, org: org.name })
        }
        confirmLabel={removingSelf ? t("members.leave") : t("members.remove")}
        loading={remove.isPending}
        error={errorMessage(remove.error)}
      />
    </>
  );
}
