import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createBrowserRouter, Navigate, Outlet, RouterProvider, useLocation } from "react-router";

import { ErrorState, FullPageSpinner } from "./components/ui/States";
import { useMe } from "./hooks/queries";
import { useAppearance } from "./hooks/useAppearance";
import { isUnauthenticated } from "./lib/api";
import { AcceptInvitePage } from "./pages/AcceptInvitePage";
import { AccountPage } from "./pages/AccountPage";
import { AuditPage } from "./pages/AuditPage";
import { ComingSoonPage } from "./pages/ComingSoonPage";
import { DashboardPage } from "./pages/DashboardPage";
import { HomeRedirect } from "./pages/HomeRedirect";
import { LoginPage } from "./pages/LoginPage";
import { MembersPage } from "./pages/MembersPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { OnboardingPage } from "./pages/OnboardingPage";
import { OrgLayout } from "./pages/OrgLayout";
import { OrgSettingsPage } from "./pages/OrgSettingsPage";
import { ApplicationDetailPage } from "./pages/ApplicationDetailPage";
import { ApplicationsPage } from "./pages/ApplicationsPage";
import { DeploymentDetailPage } from "./pages/DeploymentDetailPage";
import { DeploymentsPage } from "./pages/DeploymentsPage";
import { ServerDetailPage } from "./pages/ServerDetailPage";
import { ServersPage } from "./pages/ServersPage";

function Root() {
  useAppearance();
  return <Outlet />;
}

function RequireAuth() {
  const location = useLocation();
  const { data, error, isPending, refetch } = useMe();
  if (isPending) return <FullPageSpinner />;
  if (isUnauthenticated(error)) {
    const next = `${location.pathname}${location.search}${location.hash}`;
    return <Navigate to={`/login?next=${encodeURIComponent(next)}`} replace />;
  }
  if (error || !data) return <ErrorState error={error} onRetry={() => refetch()} />;
  return <Outlet />;
}

function RedirectIfAuthenticated() {
  const { data } = useMe();
  return data ? <Navigate to="/" replace /> : <LoginPage />;
}

export const routes = [
  {
    element: <Root />,
    children: [
      { path: "/login", element: <RedirectIfAuthenticated /> },
      { path: "/invite", element: <AcceptInvitePage /> },
      {
        element: <RequireAuth />,
        children: [
          { path: "/", element: <HomeRedirect /> },
          { path: "/onboarding", element: <OnboardingPage /> },
          { path: "/account", element: <AccountPage /> },
          {
            path: "/orgs/:slug",
            element: <OrgLayout />,
            children: [
              { index: true, element: <DashboardPage /> },
              { path: "members", element: <MembersPage /> },
              { path: "audit", element: <AuditPage /> },
              { path: "settings", element: <OrgSettingsPage /> },
              { path: "servers", element: <ServersPage /> },
              { path: "servers/:serverId", element: <ServerDetailPage /> },
              { path: "applications", element: <ApplicationsPage /> },
              { path: "applications/:appId", element: <ApplicationDetailPage /> },
              { path: "deployments", element: <DeploymentsPage /> },
              { path: "deployments/:deploymentId", element: <DeploymentDetailPage /> },
              { path: "monitoring", element: <ComingSoonPage module="monitoring" /> },
            ],
          },
        ],
      },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
];

const router = createBrowserRouter(routes);

export function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { refetchOnWindowFocus: true, staleTime: 15_000 },
      mutations: { retry: false },
    },
  });
}

const queryClient = createQueryClient();

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  );
}
