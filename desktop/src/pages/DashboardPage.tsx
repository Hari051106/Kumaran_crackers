/**
 * Admin dashboard.
 *
 * Shows only figures the system can actually compute. Sales and order figures
 * appear once there are orders to measure; before the first one the page says
 * so plainly rather than rendering a zero that reads like a quiet trading day.
 */
import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import { ApiError } from '../api/client';
import { dashboardApi } from '../api/endpoints';
import { Badge, ErrorState, LoadingState, Panel } from '../components/ui';
import { StatCard } from '../components/StatCard';
import { OrderStatusBadge } from '../components/OrderStatusBadge';
import { formatDate } from '../lib/dates';
import { formatCount, formatMoneyShort, formatMoney } from '../lib/money';
import type { DashboardStats } from '../types/api';

// Validated against the white panel surface: L in band, chroma over floor,
// contrast 4.4:1. A single series needs no legend - the panel title names it.
const SERIES_BLUE = '#2a78d6';

const ICONS = {
  box: (
    <svg viewBox="0 0 24 24" fill="none" className="h-[18px] w-[18px]">
      <path d="M3 7l9-4 9 4-9 4-9-4zm0 5l9 4 9-4M3 17l9 4 9-4" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  warning: (
    <svg viewBox="0 0 24 24" fill="none" className="h-[18px] w-[18px]">
      <path d="M12 9v4m0 4h.01M10.3 4.3L2.6 18a2 2 0 001.7 3h15.4a2 2 0 001.7-3L13.7 4.3a2 2 0 00-3.4 0z" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  critical: (
    <svg viewBox="0 0 24 24" fill="none" className="h-[18px] w-[18px]">
      <path d="M12 22a10 10 0 100-20 10 10 0 000 20zM15 9l-6 6m0-6l6 6" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  users: (
    <svg viewBox="0 0 24 24" fill="none" className="h-[18px] w-[18px]">
      <path d="M16 19v-2a4 4 0 00-8 0v2M12 11a3 3 0 100-6 3 3 0 000 6z" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  rupee: (
    <svg viewBox="0 0 24 24" fill="none" className="h-[18px] w-[18px]">
      <path d="M6 4h12M6 9h12M15 4c0 5-3.5 5-9 5l9 10" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  bag: (
    <svg viewBox="0 0 24 24" fill="none" className="h-[18px] w-[18px]">
      <path d="M6 4h12l1 16H5L6 4zm3 4a3 3 0 006 0" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
};

function ChartTooltip({ active, payload }: { active?: boolean; payload?: { payload: { category: string; product_count: number } }[] }) {
  if (!active || !payload?.length) return null;
  const row = payload[0]?.payload;
  if (!row) return null;
  return (
    <div className="rounded-lg border border-shell-200 bg-white px-3 py-2 shadow-panel">
      <p className="text-xs font-semibold text-shell-900">{row.category}</p>
      <p className="tabular text-xs text-shell-500">
        {formatCount(row.product_count)} active {row.product_count === 1 ? 'product' : 'products'}
      </p>
    </div>
  );
}

export function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setStats(await dashboardApi.stats());
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Could not load the dashboard.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) return <LoadingState label="Loading dashboard…" />;
  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!stats) return null;

  const {
    catalogue,
    inventory,
    customers,
    products_per_category: perCategory,
    sales,
    orders_by_status: byStatus,
    best_sellers: bestSellers,
    recent_orders: recentOrders,
  } = stats;
  const chartHeight = Math.max(200, perCategory.length * 38 + 40);

  return (
    <div className="flex flex-col gap-6" data-testid="dashboard">
      {/* ---- Trading ---- */}
      {stats.sales_metrics_available ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard
            testId="stat-revenue-today"
            label="Revenue today"
            value={formatMoneyShort(sales.revenue_today)}
            sublabel={`${formatCount(sales.orders_today)} ${sales.orders_today === 1 ? 'order' : 'orders'} today`}
            icon={ICONS.rupee}
          />
          <StatCard
            testId="stat-pending-orders"
            label="Orders to action"
            value={formatCount(stats.pending_orders)}
            sublabel="Placed or confirmed, waiting on us"
            tone={stats.pending_orders > 0 ? 'warning' : 'neutral'}
            icon={ICONS.bag}
          />
          <StatCard
            testId="stat-revenue-month"
            label="Revenue, 30 days"
            value={formatMoneyShort(sales.revenue_this_month)}
            sublabel={`${formatCount(sales.orders_this_month)} orders in the last 30 days`}
            icon={ICONS.rupee}
          />
          <StatCard
            testId="stat-average-order"
            label="Average order"
            value={formatMoney(sales.average_order_value)}
            sublabel={`Across ${formatCount(sales.total_orders)} orders, ${formatMoneyShort(sales.lifetime_revenue)} lifetime`}
            icon={ICONS.rupee}
          />
        </div>
      ) : (
        <div
          data-testid="sales-unavailable"
          className="flex items-start gap-3 rounded-xl border border-shell-200 bg-shell-100/60 px-5 py-4"
        >
          <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-white text-shell-500">
            <svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
              <path fillRule="evenodd" d="M18 10A8 8 0 112 10a8 8 0 0116 0zm-9-3.75A.75.75 0 119 4.75a.75.75 0 010 1.5zM10 9a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 9z" clipRule="evenodd" />
            </svg>
          </span>
          <div>
            <p className="text-sm font-semibold text-shell-800">
              No orders have been placed yet
            </p>
            <p className="mt-0.5 text-sm text-shell-600">
              Revenue, pending orders and best sellers appear here as soon as the first order
              arrives. Nothing is shown rather than a zero that could be mistaken for a quiet
              trading day.
            </p>
          </div>
        </div>
      )}

      {/* ---- Headline figures ---- */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          testId="stat-products"
          label="Active products"
          value={formatCount(catalogue.active_products)}
          sublabel={`${formatCount(catalogue.total_products)} in the catalogue, ${formatCount(catalogue.inactive_products)} deactivated`}
          icon={ICONS.box}
        />
        <StatCard
          testId="stat-low-stock"
          label="Low stock"
          value={formatCount(inventory.low_stock_count)}
          sublabel="At or below the reorder threshold"
          tone={inventory.low_stock_count > 0 ? 'warning' : 'neutral'}
          icon={ICONS.warning}
        />
        <StatCard
          testId="stat-out-of-stock"
          label="Out of stock"
          value={formatCount(inventory.out_of_stock_count)}
          sublabel="Nothing left to sell"
          tone={inventory.out_of_stock_count > 0 ? 'critical' : 'neutral'}
          icon={ICONS.critical}
        />
        <StatCard
          testId="stat-customers"
          label="Customers"
          value={formatCount(customers.total_customers)}
          sublabel={`${formatCount(customers.active_customers)} active`}
          icon={ICONS.users}
        />
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        {/* ---- Category distribution ---- */}
        <Panel
          title="Active products by category"
          description="How the live catalogue is spread across categories."
          className="xl:col-span-2"
        >
          {perCategory.length === 0 ? (
            <div className="px-5 py-12 text-center text-sm text-shell-500">
              No active products yet. Add one to see the distribution.
            </div>
          ) : (
            <div className="px-3 py-4" data-testid="category-chart">
              <ResponsiveContainer width="100%" height={chartHeight}>
                <BarChart
                  data={perCategory}
                  layout="vertical"
                  margin={{ top: 4, right: 44, bottom: 4, left: 8 }}
                  barCategoryGap={8}
                >
                  {/* Recessive grid: vertical rules only, so bars stay dominant. */}
                  <CartesianGrid horizontal={false} stroke="#eceef2" />
                  <XAxis
                    type="number"
                    allowDecimals={false}
                    tick={{ fontSize: 12, fill: '#667391' }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    type="category"
                    dataKey="category"
                    width={130}
                    tick={{ fontSize: 12, fill: '#424a61' }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip
                    content={<ChartTooltip />}
                    cursor={{ fill: '#f6f7f9' }}
                  />
                  {/* Rounded data-end, anchored square to the baseline. */}
                  <Bar dataKey="product_count" radius={[0, 4, 4, 0]} maxBarSize={22}>
                    {perCategory.map((row) => (
                      <Cell key={row.category} fill={SERIES_BLUE} />
                    ))}
                    {/* Direct labels: the value is readable without the axis,
                        and without relying on colour. */}
                    <LabelList
                      dataKey="product_count"
                      position="right"
                      offset={8}
                      style={{ fontSize: 12, fill: '#424a61', fontWeight: 600 }}
                    />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </Panel>

        {/* ---- Inventory value + catalogue shape ---- */}
        <div className="flex flex-col gap-6">
          <Panel title="Inventory value" description="Retail value of active stock on hand.">
            <div className="px-5 py-6">
              <p className="tabular text-3xl font-semibold tracking-tight text-shell-900">
                {formatMoneyShort(inventory.inventory_retail_value)}
              </p>
              <p className="mt-1 text-xs text-shell-500">
                Exactly {formatMoney(inventory.inventory_retail_value)} across all active products.
              </p>
              <div className="mt-4 flex items-center gap-2 text-shell-500">
                <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-shell-100">
                  {ICONS.rupee}
                </span>
                <span className="text-xs">Stock quantity × selling price</span>
              </div>
            </div>
          </Panel>

          <Panel title="Catalogue">
            <dl className="divide-y divide-shell-200">
              {[
                ['Categories', formatCount(catalogue.total_categories)],
                ['Active categories', formatCount(catalogue.active_categories)],
                ['Deactivated products', formatCount(catalogue.inactive_products)],
              ].map(([term, value]) => (
                <div key={term} className="flex items-center justify-between px-5 py-3">
                  <dt className="text-sm text-shell-600">{term}</dt>
                  <dd className="tabular text-sm font-semibold text-shell-900">{value}</dd>
                </div>
              ))}
            </dl>
          </Panel>
        </div>
      </div>

      {/* ---- Where the orders are ---- */}
      {stats.sales_metrics_available && (
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
          <Panel
            title="Orders by status"
            description="Every stage is listed, including the empty ones."
            action={
              <Link to="/orders" className="text-sm font-semibold text-brand-600 hover:text-brand-700">
                Manage
              </Link>
            }
          >
            <ul className="divide-y divide-shell-100" data-testid="orders-by-status">
              {byStatus.map((row) => (
                <li key={row.status} className="flex items-center justify-between px-5 py-2.5">
                  <OrderStatusBadge status={row.status} label={row.label} />
                  <span className="tabular text-sm font-semibold text-shell-900">
                    {formatCount(row.count)}
                  </span>
                </li>
              ))}
            </ul>
          </Panel>

          <Panel title="Best sellers" description="By units sold, cancelled orders excluded.">
            {bestSellers.length === 0 ? (
              <div className="px-5 py-10 text-center text-sm text-shell-500">
                Nothing has sold yet.
              </div>
            ) : (
              <ol className="divide-y divide-shell-100" data-testid="best-sellers">
                {bestSellers.map((row, index) => (
                  <li
                    key={row.product_name}
                    className="flex items-center justify-between gap-3 px-5 py-2.5"
                  >
                    <span className="flex min-w-0 items-center gap-3">
                      <span className="tabular w-4 shrink-0 text-xs font-semibold text-shell-400">
                        {index + 1}
                      </span>
                      <span className="truncate text-sm text-shell-800">{row.product_name}</span>
                    </span>
                    <span className="shrink-0 text-right">
                      <span className="tabular block text-sm font-semibold text-shell-900">
                        {formatCount(row.units_sold)} sold
                      </span>
                      <span className="tabular block text-xs text-shell-500">
                        {formatMoney(row.revenue)}
                      </span>
                    </span>
                  </li>
                ))}
              </ol>
            )}
          </Panel>

          <Panel
            title="Latest orders"
            action={
              <Link to="/orders" className="text-sm font-semibold text-brand-600 hover:text-brand-700">
                View all
              </Link>
            }
          >
            <ul className="divide-y divide-shell-100" data-testid="recent-orders">
              {recentOrders.map((order) => (
                <li key={order.order_number} className="px-5 py-2.5">
                  <div className="flex items-center justify-between gap-3">
                    <span className="tabular text-sm font-semibold text-shell-900">
                      {order.order_number}
                    </span>
                    <span className="tabular text-sm text-shell-900">
                      {formatMoney(order.total)}
                    </span>
                  </div>
                  <div className="mt-1 flex items-center justify-between gap-3">
                    <OrderStatusBadge status={order.status} label={order.status_label} />
                    <span className="tabular text-xs text-shell-500">
                      {formatDate(order.placed_at)}
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          </Panel>
        </div>
      )}

      {/* ---- Recently added ---- */}
      <Panel
        title="Recently added products"
        action={
          <Link to="/products" className="text-sm font-semibold text-brand-600 hover:text-brand-700">
            View all
          </Link>
        }
      >
        {stats.recent_products.length === 0 ? (
          <div className="px-5 py-12 text-center text-sm text-shell-500">
            Nothing added yet.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-shell-200 text-left text-xs uppercase tracking-wide text-shell-500">
                <th className="px-5 py-2.5 font-semibold">Product</th>
                <th className="px-5 py-2.5 font-semibold">Category</th>
                <th className="px-5 py-2.5 text-right font-semibold">Price</th>
                <th className="px-5 py-2.5 font-semibold">Stock</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-shell-100">
              {stats.recent_products.map((product) => (
                <tr key={product.id} className="hover:bg-shell-50">
                  <td className="px-5 py-3">
                    <p className="font-medium text-shell-900">{product.name}</p>
                    <p className="tabular text-xs text-shell-500">{product.sku}</p>
                  </td>
                  <td className="px-5 py-3 text-shell-600">{product.category.name}</td>
                  <td className="tabular px-5 py-3 text-right font-medium text-shell-900">
                    {formatMoney(product.selling_price)}
                  </td>
                  <td className="px-5 py-3">
                    <StockBadge status={product.stock_status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
            </div>
        )}
      </Panel>

    </div>
  );
}

/** Stock state as icon + word + colour - never colour alone. */
export function StockBadge({ status }: { status: 'IN_STOCK' | 'LOW_STOCK' | 'OUT_OF_STOCK' }) {
  if (status === 'OUT_OF_STOCK') return <Badge tone="danger">Out of stock</Badge>;
  if (status === 'LOW_STOCK') return <Badge tone="warning">Low stock</Badge>;
  return <Badge tone="success">In stock</Badge>;
}
