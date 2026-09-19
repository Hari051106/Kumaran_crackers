/**
 * The persistent frame around every signed-in screen: brand, navigation,
 * current user, and the routed page itself.
 */
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import { useState } from 'react';

import { useAuth } from '../auth/AuthContext';
import { ConfirmDialog } from '../components/Modal';

interface NavItem {
  to: string;
  label: string;
  icon: JSX.Element;
  /** Screens whose data model arrives in a later milestone. */
  comingSoon?: string;
}

const icon = (path: string) => (
  <svg viewBox="0 0 24 24" fill="none" className="h-[18px] w-[18px]" aria-hidden="true">
    <path d={path} stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const NAV_ITEMS: NavItem[] = [
  { to: '/dashboard', label: 'Dashboard', icon: icon('M4 13h6V4H4v9zm0 7h6v-5H4v5zm10 0h6v-9h-6v9zm0-16v5h6V4h-6z') },
  { to: '/products', label: 'Products', icon: icon('M3 7l9-4 9 4-9 4-9-4zm0 5l9 4 9-4M3 17l9 4 9-4') },
  { to: '/categories', label: 'Categories', icon: icon('M4 5h6v6H4V5zm10 0h6v6h-6V5zM4 15h6v4H4v-4zm10 0h6v4h-6v-4z') },
  { to: '/inventory', label: 'Inventory', icon: icon('M4 7h16M4 12h16M4 17h10') },
  { to: '/orders', label: 'Orders', icon: icon('M6 4h12l1 16H5L6 4zm3 4a3 3 0 006 0'), comingSoon: 'Milestone 6' },
  { to: '/customers', label: 'Customers', icon: icon('M16 19v-2a4 4 0 00-8 0v2M12 11a3 3 0 100-6 3 3 0 000 6z'), comingSoon: 'Milestone 6' },
  { to: '/delivery', label: 'Delivery', icon: icon('M3 16V7h11v9M14 10h4l3 3v3h-7M7 19a2 2 0 100-4 2 2 0 000 4zm10 0a2 2 0 100-4 2 2 0 000 4z'), comingSoon: 'Milestone 7' },
  { to: '/reports', label: 'Reports', icon: icon('M5 20V10M12 20V4M19 20v-6'), comingSoon: 'Milestone 8' },
  { to: '/settings', label: 'Settings', icon: icon('M12 15a3 3 0 100-6 3 3 0 000 6zM4 12h2m12 0h2M12 4v2m0 12v2') },
];

const PAGE_TITLES: Record<string, string> = Object.fromEntries(
  NAV_ITEMS.map((item) => [item.to, item.label]),
);

export function AppShell() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const [confirmingLogout, setConfirmingLogout] = useState(false);

  const initials = (user?.full_name ?? '')
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? '')
    .join('');

  return (
    <div className="flex h-full">
      {/* ---- Sidebar ---- */}
      <aside className="flex w-64 shrink-0 flex-col bg-shell-900 text-shell-300">
        <div className="flex items-center gap-3 px-5 py-5">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand-500 text-base font-bold text-white">
            K
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-white">Kumaran Crackers</p>
            <p className="truncate text-xs text-shell-400">Admin Console</p>
          </div>
        </div>

        <nav className="flex-1 space-y-0.5 overflow-y-auto px-3 py-2" aria-label="Main">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `group flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition ${
                  isActive
                    ? 'bg-brand-500/15 text-brand-300'
                    : 'text-shell-300 hover:bg-white/5 hover:text-white'
                }`
              }
            >
              <span className="shrink-0">{item.icon}</span>
              <span className="flex-1 truncate">{item.label}</span>
              {item.comingSoon && (
                <span
                  title={`Arrives in ${item.comingSoon}`}
                  className="rounded bg-shell-800 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-shell-400"
                >
                  Soon
                </span>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-white/10 p-3">
          <div className="flex items-center gap-3 rounded-lg px-2 py-2">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-shell-700 text-xs font-semibold text-white">
              {initials || '—'}
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-white">{user?.full_name}</p>
              <p className="truncate text-xs text-shell-400">{user?.role.name}</p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setConfirmingLogout(true)}
            data-testid="logout-button"
            className="focus-ring mt-1 flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-shell-300 transition hover:bg-white/5 hover:text-white"
          >
            {icon('M15 16l4-4-4-4M19 12H9M12 19H6a2 2 0 01-2-2V7a2 2 0 012-2h6')}
            Logout
          </button>
        </div>
      </aside>

      {/* ---- Main column ---- */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-16 shrink-0 items-center justify-between border-b border-shell-200 bg-white px-8">
          <h1 className="text-lg font-semibold text-shell-900">
            {PAGE_TITLES[location.pathname] ?? 'Kumaran Crackers Admin'}
          </h1>
          <p className="text-sm text-shell-400">Celebrate Every Moment with Kumaran Crackers</p>
        </header>

        <main className="flex-1 overflow-y-auto px-8 py-6">
          <Outlet />
        </main>
      </div>

      <ConfirmDialog
        open={confirmingLogout}
        title="Log out?"
        message="You will need to sign in again to reach the admin console."
        confirmLabel="Log out"
        onConfirm={() => {
          setConfirmingLogout(false);
          void logout();
        }}
        onCancel={() => setConfirmingLogout(false)}
      />
    </div>
  );
}
