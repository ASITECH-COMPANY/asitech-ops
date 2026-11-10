import { useEffect } from "react";
import { Outlet, useParams } from "react-router";

import { AppShell } from "../components/layout/AppShell";
import { ErrorState, Spinner } from "../components/ui/States";
import { useOrganization } from "../hooks/queries";
import { useOrgEvents } from "../hooks/useOrgEvents";
import { ApiError } from "../lib/api";
import type { Organization } from "../lib/types";
import { usePreferences } from "../stores/preferences";
import { NotFoundContent } from "./NotFoundPage";

export interface OrgContext {
  org: Organization;
}

export function OrgLayout() {
  const { slug = "" } = useParams();
  const { data: org, error, isPending, refetch } = useOrganization(slug);
  const setLastOrg = usePreferences((s) => s.setLastOrg);
  const live = useOrgEvents(slug);

  const notFound = error instanceof ApiError && error.status === 404;

  useEffect(() => {
    if (org) setLastOrg(org.slug);
    else if (notFound) setLastOrg(null);
  }, [org, notFound, setLastOrg]);

  if (isPending) {
    return (
      <AppShell>
        <Spinner />
      </AppShell>
    );
  }
  if (error || !org) {
    return <AppShell>{notFound ? <NotFoundContent /> : <ErrorState error={error} onRetry={() => refetch()} />}</AppShell>;
  }

  return (
    <AppShell org={org} live={live}>
      <Outlet context={{ org } satisfies OrgContext} />
    </AppShell>
  );
}
