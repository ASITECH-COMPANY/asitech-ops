import { Building2, Check, ChevronsUpDown, Languages, LogOut, Menu as MenuIcon, Monitor, Moon, Plus, Sun, UserRound } from "lucide-react";
import { useNavigate } from "react-router";

import { useLogout, useMe, useOrganizations, useUpdateProfile } from "../../hooks/queries";
import type { LiveStatus } from "../../hooks/useOrgEvents";
import { useT } from "../../i18n";
import { initials } from "../../lib/format";
import type { Language, Organization } from "../../lib/types";
import { usePreferences, type ThemePreference } from "../../stores/preferences";
import { cn } from "../ui/cn";
import { Menu, MenuDivider, MenuItem, MenuLabel } from "../ui/Menu";

function OrgSwitcher({ current }: { current?: Organization }) {
  const t = useT();
  const navigate = useNavigate();
  const { data: orgs } = useOrganizations();
  const { data: me } = useMe();

  return (
    <Menu
      label={t("topbar.switchOrg")}
      align="start"
      triggerClassName="max-w-[14rem] border border-line bg-surface"
      trigger={
        <>
          <Building2 className="size-4 shrink-0 text-muted" aria-hidden />
          <span className="truncate font-medium">{current?.name ?? t("topbar.switchOrg")}</span>
          <ChevronsUpDown className="size-3.5 shrink-0 text-muted" aria-hidden />
        </>
      }
    >
      {(close) => (
        <>
          <MenuLabel>{t("nav.organization")}</MenuLabel>
          {orgs?.map((org) => (
            <MenuItem
              key={org.id}
              active={org.slug === current?.slug}
              icon={org.slug === current?.slug ? <Check className="size-4" /> : <span className="inline-block size-4" />}
              onSelect={() => {
                close();
                navigate(`/orgs/${org.slug}`);
              }}
            >
              {org.name}
            </MenuItem>
          ))}
          {me?.can_create_organizations ? (
            <>
              <MenuDivider />
              <MenuItem
                icon={<Plus className="size-4" />}
                onSelect={() => {
                  close();
                  navigate("/onboarding");
                }}
              >
                {t("topbar.createOrg")}
              </MenuItem>
            </>
          ) : null}
        </>
      )}
    </Menu>
  );
}

const liveStyles: Record<LiveStatus, string> = {
  live: "bg-success",
  connecting: "bg-warning animate-pulse",
  offline: "bg-muted",
};

function LiveIndicator({ status }: { status: LiveStatus }) {
  const t = useT();
  const label = { live: t("live.connected"), connecting: t("live.connecting"), offline: t("live.offline") }[status];
  return (
    <span className="hidden items-center gap-2 rounded-full border border-line px-2.5 py-1 text-xs text-muted sm:inline-flex" title={t("live.tooltip")}>
      <span className={cn("size-2 rounded-full", liveStyles[status])} aria-hidden />
      <span role="status">{label}</span>
    </span>
  );
}

function LanguageSwitch() {
  const t = useT();
  const language = usePreferences((s) => s.language);
  const setLanguage = usePreferences((s) => s.setLanguage);
  const updateProfile = useUpdateProfile();

  const choose = (value: Language) => {
    setLanguage(value);
    updateProfile.mutate({ language: value });
  };

  return (
    <div role="group" aria-label={t("topbar.language")} className="hidden items-center rounded-lg border border-line p-0.5 sm:flex">
      <Languages className="mx-1.5 size-3.5 text-muted" aria-hidden />
      {(["en", "fr"] as const).map((value) => (
        <button
          key={value}
          type="button"
          onClick={() => choose(value)}
          aria-pressed={language === value}
          className={cn(
            "rounded-md px-2 py-1 text-xs font-medium uppercase",
            language === value ? "bg-surface-2 text-fg" : "text-muted hover:text-fg",
          )}
        >
          {value}
        </button>
      ))}
    </div>
  );
}

const themeIcons: Record<ThemePreference, typeof Sun> = { light: Sun, dark: Moon, system: Monitor };

function ThemeMenu() {
  const t = useT();
  const theme = usePreferences((s) => s.theme);
  const setTheme = usePreferences((s) => s.setTheme);
  const Icon = themeIcons[theme];
  return (
    <Menu label={t("topbar.theme")} trigger={<Icon className="size-4 text-muted" aria-hidden />} triggerClassName="h-9 w-9 justify-center">
      {(close) =>
        (["light", "dark", "system"] as const).map((value) => {
          const ItemIcon = themeIcons[value];
          return (
            <MenuItem
              key={value}
              active={theme === value}
              icon={<ItemIcon className="size-4" />}
              onSelect={() => {
                setTheme(value);
                close();
              }}
            >
              {t(`topbar.theme.${value}`)}
            </MenuItem>
          );
        })
      }
    </Menu>
  );
}

function UserMenu() {
  const t = useT();
  const navigate = useNavigate();
  const { data: me } = useMe();
  const logout = useLogout();
  if (!me) return null;
  const name = me.full_name || me.email;

  return (
    <Menu
      label={t("topbar.account")}
      trigger={
        <span className="flex size-8 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-fg">
          {initials(name)}
        </span>
      }
      triggerClassName="p-0.5 rounded-full"
    >
      {(close) => (
        <>
          <div className="px-2.5 py-2">
            <p className="truncate text-sm font-medium text-fg">{name}</p>
            <p className="truncate text-xs text-muted">{me.email}</p>
          </div>
          <MenuDivider />
          <MenuItem
            icon={<UserRound className="size-4" />}
            onSelect={() => {
              close();
              navigate("/account");
            }}
          >
            {t("topbar.account")}
          </MenuItem>
          <MenuItem
            icon={<LogOut className="size-4" />}
            onSelect={() => {
              close();
              logout.mutate(undefined, { onSettled: () => navigate("/login", { replace: true }) });
            }}
          >
            {t("topbar.logout")}
          </MenuItem>
        </>
      )}
    </Menu>
  );
}

export function Topbar({
  org,
  live,
  onOpenMenu,
}: {
  org?: Organization;
  live?: LiveStatus;
  onOpenMenu: () => void;
}) {
  const t = useT();
  return (
    <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-line bg-surface/90 px-4 backdrop-blur sm:px-6">
      <button
        type="button"
        onClick={onOpenMenu}
        className="rounded-lg p-2 text-muted hover:bg-surface-2 hover:text-fg lg:hidden"
        aria-label={t("nav.openMenu")}
      >
        <MenuIcon className="size-5" aria-hidden />
      </button>
      <OrgSwitcher current={org} />
      <div className="ml-auto flex items-center gap-2">
        {live ? <LiveIndicator status={live} /> : null}
        <LanguageSwitch />
        <ThemeMenu />
        <UserMenu />
      </div>
    </header>
  );
}
