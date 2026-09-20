/**
 * Order management.
 *
 * The list, the full detail of one order, and the controls that move it
 * through the workflow. Which moves are offered comes from the server's
 * `allowed_transitions`; the server re-checks every one regardless, so the
 * buttons here are a convenience and never the rule.
 */
import { useCallback, useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';

import { ApiError } from '../api/client';
import { ordersApi, type OrderQuery } from '../api/endpoints';
import { Modal } from '../components/Modal';
import { OrderStatusBadge } from '../components/OrderStatusBadge';
import { Pagination } from '../components/Pagination';
import { useToast } from '../components/Toast';
import {
  Button,
  EmptyState,
  ErrorState,
  Field,
  LoadingState,
  Panel,
  Select,
  TextInput,
} from '../components/ui';
import { formatDate, formatDateTime } from '../lib/dates';
import { formatCount, formatMoney } from '../lib/money';
import {
  ORDER_STATUSES,
  type AdminOrderDetail,
  type AdminOrderSummary,
  type OrderStatus,
  type Page,
} from '../types/api';

const STATUS_LABELS: Record<OrderStatus, string> = {
  PLACED: 'Order placed',
  CONFIRMED: 'Confirmed',
  PACKING: 'Packing',
  OUT_FOR_DELIVERY: 'Out for delivery',
  DELIVERED: 'Delivered',
  CANCELLED: 'Cancelled',
};

const PAGE_SIZE = 20;

export function OrdersPage() {
  const toast = useToast();
  // A customer row links here with ?query=<email>, so the filter is in the URL.
  const [searchParams, setSearchParams] = useSearchParams();

  const [page, setPage] = useState<Page<AdminOrderSummary> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [searchTerm, setSearchTerm] = useState(searchParams.get('query') ?? '');
  const [query, setQuery] = useState<OrderQuery>({
    query: searchParams.get('query') ?? undefined,
    status: (searchParams.get('status') as OrderStatus | null) ?? '',
    page: 1,
    page_size: PAGE_SIZE,
  });

  const [openOrder, setOpenOrder] = useState<AdminOrderDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setPage(await ordersApi.search(query));
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Could not load orders.');
    } finally {
      setLoading(false);
    }
  }, [query]);

  useEffect(() => {
    void load();
  }, [load]);

  // Debounced so typing a customer's name does not fire a request per keystroke.
  useEffect(() => {
    const timer = setTimeout(() => {
      setQuery((current) =>
        current.query === (searchTerm || undefined)
          ? current
          : { ...current, query: searchTerm || undefined, page: 1 },
      );
    }, 300);
    return () => clearTimeout(timer);
  }, [searchTerm]);

  function applyStatus(status: OrderStatus | '') {
    setQuery((current) => ({ ...current, status, page: 1 }));
    const next = new URLSearchParams(searchParams);
    if (status) next.set('status', status);
    else next.delete('status');
    setSearchParams(next, { replace: true });
  }

  async function openDetail(orderNumber: string) {
    setDetailLoading(true);
    try {
      setOpenOrder(await ordersApi.get(orderNumber));
    } catch (caught) {
      toast.error(caught instanceof ApiError ? caught.message : 'Could not open that order.');
    } finally {
      setDetailLoading(false);
    }
  }

  function onOrderChanged(updated: AdminOrderDetail) {
    setOpenOrder(updated);
    // The list row now shows a stale status; refresh it from the server.
    void load();
  }

  return (
    <div className="flex flex-col gap-5" data-testid="orders-page">
      <Panel
        title="Orders"
        description="Every order placed, newest first."
        action={
          <Button variant="secondary" onClick={load} disabled={loading}>
            Refresh
          </Button>
        }
      >
        {/* ---- Filters ---- */}
        <div className="flex flex-wrap items-end gap-3 border-b border-shell-200 px-5 py-4">
          <div className="w-full max-w-md">
            <Field label="Search" htmlFor="order-search">
              <TextInput
                id="order-search"
                data-testid="order-search"
                placeholder="Order number, recipient, phone or email"
                value={searchTerm}
                onChange={(event) => setSearchTerm(event.target.value)}
              />
            </Field>
          </div>
          <div className="w-56">
            <Field label="Status" htmlFor="order-status-filter">
              <Select
                id="order-status-filter"
                data-testid="order-status-filter"
                value={query.status ?? ''}
                onChange={(event) => applyStatus(event.target.value as OrderStatus | '')}
              >
                <option value="">All statuses</option>
                {ORDER_STATUSES.map((status) => (
                  <option key={status} value={status}>
                    {STATUS_LABELS[status]}
                  </option>
                ))}
              </Select>
            </Field>
          </div>
        </div>

        {/* ---- Results ---- */}
        {loading && !page ? (
          <LoadingState label="Loading orders…" />
        ) : error ? (
          <ErrorState message={error} onRetry={load} />
        ) : !page || page.items.length === 0 ? (
          <EmptyState
            title="No orders match"
            description={
              query.query || query.status
                ? 'Try a different search term or clear the status filter.'
                : 'Orders placed in the shop appear here as soon as they are made.'
            }
          />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm" data-testid="orders-table">
                <thead>
                  <tr className="border-b border-shell-200 text-left text-xs uppercase tracking-wide text-shell-500">
                    <th className="px-5 py-2.5 font-semibold">Order</th>
                    <th className="px-4 py-2.5 font-semibold">Customer</th>
                    <th className="px-4 py-2.5 font-semibold">Placed</th>
                    <th className="px-4 py-2.5 text-right font-semibold">Total</th>
                    <th className="px-4 py-2.5 font-semibold">Status</th>
                    <th className="px-5 py-2.5 text-right font-semibold">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-shell-100">
                  {page.items.map((order) => (
                    <tr
                      key={order.order_number}
                      className="hover:bg-shell-50"
                      data-testid={`order-row-${order.order_number}`}
                    >
                      <td className="px-5 py-3">
                        <p className="tabular font-semibold text-shell-900">
                          {order.order_number}
                        </p>
                        <p className="text-xs text-shell-500">
                          {formatCount(order.item_count)}{' '}
                          {order.item_count === 1 ? 'item' : 'items'}
                        </p>
                      </td>
                      <td className="px-4 py-3">
                        <p className="max-w-[12rem] truncate text-shell-800">
                          {order.customer_name}
                        </p>
                        <p className="max-w-[12rem] truncate text-xs text-shell-500">
                          {order.customer_phone ?? order.customer_email}
                        </p>
                      </td>
                      <td className="tabular px-4 py-3 text-shell-600">
                        {formatDate(order.placed_at)}
                      </td>
                      <td className="tabular px-4 py-3 text-right font-semibold text-shell-900">
                        {formatMoney(order.total)}
                      </td>
                      <td className="px-4 py-3">
                        <OrderStatusBadge status={order.status} label={order.status_label} />
                      </td>
                      <td className="px-5 py-3 text-right">
                        <Button
                          variant="secondary"
                          onClick={() => openDetail(order.order_number)}
                          disabled={detailLoading}
                          data-testid={`open-order-${order.order_number}`}
                        >
                          Open
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination
              meta={page.meta}
              itemNoun="order"
              onPageChange={(next) => setQuery((current) => ({ ...current, page: next }))}
            />
          </>
        )}
      </Panel>

      <OrderDetailModal
        order={openOrder}
        onClose={() => setOpenOrder(null)}
        onChanged={onOrderChanged}
      />
    </div>
  );
}

/** The full record, plus the controls that move it on. */
function OrderDetailModal({
  order,
  onClose,
  onChanged,
}: {
  order: AdminOrderDetail | null;
  onClose(): void;
  onChanged(updated: AdminOrderDetail): void;
}) {
  const toast = useToast();
  const [target, setTarget] = useState<OrderStatus | ''>('');
  const [note, setNote] = useState('');
  const [saving, setSaving] = useState(false);

  // A newly opened order starts with an empty form.
  useEffect(() => {
    setTarget('');
    setNote('');
  }, [order?.order_number]);

  if (!order) return null;

  async function applyStatus() {
    if (!order || !target) return;
    setSaving(true);
    try {
      const updated = await ordersApi.updateStatus(order.order_number, target, note);
      toast.success(`${order.order_number} is now ${STATUS_LABELS[target].toLowerCase()}.`);
      setTarget('');
      setNote('');
      onChanged(updated);
    } catch (caught) {
      // The server owns the state machine; show exactly why it refused.
      toast.error(
        caught instanceof ApiError ? caught.message : 'Could not update that order.',
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal
      open
      size="lg"
      title={order.order_number}
      description={`Placed ${formatDateTime(order.placed_at)} by ${order.customer_name}`}
      onClose={onClose}
      footer={<Button variant="secondary" onClick={onClose}>Close</Button>}
    >
      <div className="flex flex-col gap-5" data-testid="order-detail">
        {/* ---- Status and next moves ---- */}
        <section className="rounded-lg border border-shell-200 bg-shell-50 px-4 py-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold uppercase tracking-wide text-shell-500">
                Status
              </span>
              <OrderStatusBadge status={order.status} label={order.status_label} />
            </div>
            <p className="tabular text-sm text-shell-600">
              Total <span className="font-semibold text-shell-900">{formatMoney(order.total)}</span>
            </p>
          </div>

          {order.allowed_transitions.length === 0 ? (
            <p className="mt-3 text-sm text-shell-500" data-testid="no-transitions">
              This order is {order.status_label.toLowerCase()} and can no longer be changed.
            </p>
          ) : (
            <div className="mt-4 flex flex-wrap items-end gap-3">
              <div className="w-56">
                <Field label="Move to" htmlFor="order-next-status">
                  <Select
                    id="order-next-status"
                    data-testid="order-next-status"
                    value={target}
                    onChange={(event) => setTarget(event.target.value as OrderStatus | '')}
                  >
                    <option value="">Choose…</option>
                    {order.allowed_transitions.map((status) => (
                      <option key={status} value={status}>
                        {STATUS_LABELS[status]}
                      </option>
                    ))}
                  </Select>
                </Field>
              </div>
              <div className="min-w-[220px] flex-1">
                <Field label="Note" htmlFor="order-status-note">
                  <TextInput
                    id="order-status-note"
                    data-testid="order-status-note"
                    maxLength={300}
                    placeholder={
                      target === 'CANCELLED' ? 'Why is it being cancelled?' : 'Optional'
                    }
                    value={note}
                    onChange={(event) => setNote(event.target.value)}
                  />
                </Field>
              </div>
              <Button
                onClick={applyStatus}
                disabled={!target}
                loading={saving}
                variant={target === 'CANCELLED' ? 'danger' : 'primary'}
                data-testid="apply-status"
              >
                Update
              </Button>
              <p className="w-full text-xs text-shell-500">
                Every change is written to the audit trail with who made it.
              </p>
            </div>
          )}

          {target === 'CANCELLED' && (
            <p className="mt-2 text-xs text-rose-700" data-testid="cancel-warning">
              Cancelling returns every item on this order to stock. It cannot be undone.
            </p>
          )}
        </section>

        {/* ---- Items ---- */}
        <section>
          <h3 className="mb-2 text-sm font-semibold text-shell-900">Items</h3>
          <div className="overflow-hidden rounded-lg border border-shell-200">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-shell-200 bg-shell-50 text-left text-xs uppercase tracking-wide text-shell-500">
                  <th className="px-4 py-2 font-semibold">Product</th>
                  <th className="px-3 py-2 text-right font-semibold">Qty</th>
                  <th className="px-3 py-2 text-right font-semibold">Unit</th>
                  <th className="px-4 py-2 text-right font-semibold">Line total</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-shell-100">
                {order.items.map((item) => (
                  <tr key={item.id}>
                    <td className="px-4 py-2.5">
                      <p className="text-shell-900">{item.product_name}</p>
                      <p className="tabular text-xs text-shell-500">{item.product_sku}</p>
                    </td>
                    <td className="tabular px-3 py-2.5 text-right text-shell-700">
                      {item.quantity}
                    </td>
                    <td className="tabular px-3 py-2.5 text-right text-shell-700">
                      {formatMoney(item.unit_price)}
                    </td>
                    <td className="tabular px-4 py-2.5 text-right font-medium text-shell-900">
                      {formatMoney(item.line_total)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-xs text-shell-500">
            Prices are as they were when the order was placed, not today&rsquo;s catalogue prices.
          </p>
        </section>

        {/* ---- Money and address ---- */}
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <section className="rounded-lg border border-shell-200">
            <h3 className="border-b border-shell-200 px-4 py-2.5 text-sm font-semibold text-shell-900">
              Bill
            </h3>
            <dl className="divide-y divide-shell-100">
              {[
                ['Subtotal', formatMoney(order.totals.subtotal)],
                ['Discount', `- ${formatMoney(order.totals.discount)}`],
                ['Items total', formatMoney(order.totals.items_total)],
                ['Delivery charge', formatMoney(order.totals.delivery_charge)],
              ].map(([term, value]) => (
                <div key={term} className="flex items-center justify-between px-4 py-2">
                  <dt className="text-sm text-shell-600">{term}</dt>
                  <dd className="tabular text-sm text-shell-800">{value}</dd>
                </div>
              ))}
              <div className="flex items-center justify-between bg-shell-50 px-4 py-2.5">
                <dt className="text-sm font-semibold text-shell-900">Total</dt>
                <dd className="tabular text-sm font-semibold text-shell-900">
                  {formatMoney(order.totals.total)}
                </dd>
              </div>
            </dl>
          </section>

          <section className="rounded-lg border border-shell-200">
            <h3 className="border-b border-shell-200 px-4 py-2.5 text-sm font-semibold text-shell-900">
              Delivery address
            </h3>
            <div className="px-4 py-3 text-sm">
              <p className="font-medium text-shell-900">{order.delivery_address.full_name}</p>
              <p className="mt-1 leading-relaxed text-shell-600">
                {order.delivery_address.single_line}
              </p>
              <p className="tabular mt-1 text-shell-600">{order.delivery_address.phone}</p>
              {order.delivery_address.instructions && (
                <p className="mt-2 text-xs text-shell-500">
                  Note: {order.delivery_address.instructions}
                </p>
              )}
              <p className="mt-3 border-t border-shell-100 pt-2 text-xs text-shell-500">
                {order.customer_email}
              </p>
            </div>
          </section>
        </div>

        {/* ---- Audit trail ---- */}
        <section>
          <h3 className="mb-2 text-sm font-semibold text-shell-900">History</h3>
          <ol className="space-y-2" data-testid="order-history">
            {order.status_history.map((event) => (
              <li
                key={event.id}
                className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg border border-shell-200 px-4 py-2.5 text-sm"
              >
                <OrderStatusBadge
                  status={event.to_status}
                  label={STATUS_LABELS[event.to_status] ?? event.to_status}
                />
                <span className="tabular text-xs text-shell-500">
                  {formatDateTime(event.created_at)}
                </span>
                {event.changed_by_name && (
                  <span className="text-xs text-shell-600">by {event.changed_by_name}</span>
                )}
                {event.note && <span className="w-full text-xs text-shell-500">{event.note}</span>}
              </li>
            ))}
          </ol>
        </section>
      </div>
    </Modal>
  );
}
