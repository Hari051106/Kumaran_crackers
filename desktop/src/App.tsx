/**
 * Routing and top-level providers.
 *
 * The redirect below is a convenience, not a security control: every endpoint
 * checks the caller's role server-side regardless of which screen they reach.
 */
import { HashRouter, Navigate, Route, Routes } from 'react-router-dom';

import { AuthProvider, useAuth } from './auth/AuthContext';
import { ToastProvider } from './components/Toast';
import { LoadingState } from './components/ui';
import { AppShell } from './layouts/AppShell';
import { CategoriesPage } from './pages/CategoriesPage';
import { CustomersPage } from './pages/CustomersPage';
import { DashboardPage } from './pages/DashboardPage';
import { InventoryPage } from './pages/InventoryPage';
import { LoginPage } from './pages/LoginPage';
import { OrdersPage } from './pages/OrdersPage';
import { PlaceholderPage } from './pages/PlaceholderPage';
import { ProductsPage } from './pages/ProductsPage';
import { SettingsPage } from './pages/SettingsPage';

function AuthenticatedRoutes() {
  const { user, initialising } = useAuth();

  if (initialising) {
    return (
      <div className="flex h-full items-center justify-center">
        <LoadingState label="Starting Kumaran Crackers Admin…" />
      </div>
    );
  }

  if (!user) return <LoginPage />;

  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/products" element={<ProductsPage />} />
        <Route path="/categories" element={<CategoriesPage />} />
        <Route path="/inventory" element={<InventoryPage />} />
        <Route path="/orders" element={<OrdersPage />} />
        <Route path="/customers" element={<CustomersPage />} />
        <Route
          path="/delivery"
          element={
            <PlaceholderPage
              title="Delivery"
              milestone="Milestone 7"
              summary="Assigning orders to delivery staff and tracking their progress."
              planned={[
                'Assign an order to a delivery person',
                'Delivery status per order',
                'Designed so GPS tracking can be added later',
              ]}
            />
          }
        />
        <Route
          path="/reports"
          element={
            <PlaceholderPage
              title="Reports"
              milestone="Milestone 8"
              summary="Sales and revenue reporting, once there are sales to report on."
              planned={[
                'Daily, weekly, monthly and custom date ranges',
                'Revenue, order count and average order value',
                'Best-selling products and category performance',
                'CSV and PDF export',
              ]}
            />
          }
        />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Route>
    </Routes>
  );
}

export function App() {
  return (
    // HashRouter: the packaged app is loaded from file://, where a history
    // router's path-based URLs do not resolve.
    <HashRouter>
      <ToastProvider>
        <AuthProvider>
          <AuthenticatedRoutes />
        </AuthProvider>
      </ToastProvider>
    </HashRouter>
  );
}
