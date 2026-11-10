import { Navigate } from "react-router";

import { FullPageSpinner, ErrorState } from "../components/ui/States";
import { useOrganizations } from "../hooks/queries";
import { usePreferences } from "../stores/preferences";

export function HomeRedirect() {
  const { data: orgs, error, refetch } = useOrganizations();
  const lastOrg = usePreferences((s) => s.lastOrg);

  if (error) return <ErrorState error={error} onRetry={() => refetch()} />;
  if (!orgs) return <FullPageSpinner />;
  if (orgs.length === 0) return <Navigate to="/onboarding" replace />;
  const target = orgs.find((org) => org.slug === lastOrg) ?? orgs[0];
  return <Navigate to={`/orgs/${target.slug}`} replace />;
}
