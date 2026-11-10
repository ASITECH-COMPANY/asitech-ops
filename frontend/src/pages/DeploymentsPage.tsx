import { useState } from "react";
import { useOutletContext } from "react-router";

import { DeploymentsTable } from "../components/apps/DeploymentsTable";
import { Card, PageHeader } from "../components/ui/Card";
import { Pagination } from "../components/ui/Pagination";
import { EmptyState, ErrorState, Spinner } from "../components/ui/States";
import { useDeployments } from "../hooks/queries";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { useT } from "../i18n";
import { can } from "../lib/permissions";
import type { OrgContext } from "./OrgLayout";

export function DeploymentsPage() {
  const t = useT();
  const { org } = useOutletContext<OrgContext>();
  useDocumentTitle(t("deployments.title"), org.name);
  const [page, setPage] = useState(1);
  const deployments = useDeployments(org.slug, page);
  return (
    <>
      <PageHeader title={t("deployments.title")} description={t("deployments.subtitle", { org: org.name })} />
      <Card>
        {deployments.isPending ? (
          <Spinner />
        ) : deployments.error ? (
          <ErrorState error={deployments.error} onRetry={() => deployments.refetch()} />
        ) : deployments.data.results.length === 0 ? (
          <EmptyState title={t("deployments.empty")} />
        ) : (
          <>
            <DeploymentsTable
              slug={org.slug}
              deployments={deployments.data.results}
              showApplication
              canDeploy={can(org, "applications.deploy")}
            />
            <Pagination page={page} count={deployments.data.count} onPage={setPage} />
          </>
        )}
      </Card>
    </>
  );
}
