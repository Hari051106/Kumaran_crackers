/**
 * Customer records.
 *
 * Accounts with what they have actually bought. The order count and spend come
 * from real orders and exclude cancelled ones, so a customer who withdrew an
 * order is not shown as having spent the money.
 */
import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { ApiError } from '../api/client';
import { customersApi, type CustomerQuery } from '../api/endpoints';
import { Pagination } from '../components/Pagination';
import {
  Badge,
  Button,
  EmptyState,
  ErrorState,
  Field,
  LoadingState,
  Panel,
  Select,
  TextInput,
} from '../components/ui';
import { formatDate } from '../lib/dates';
import { formatCount, formatMoney } from '../lib/money';
import type { CustomerSummary, Page } from '../types/api';

const PAGE_SIZE = 20;

export function CustomersPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState<Page<CustomerSummary> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [searchTerm, setSearchTerm] = useState('');
  const [query, setQuery] = useState<CustomerQuery>({ page: 1, page_size: PAGE_SIZE });

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setPage(await customersApi.search(query));
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Could not load customers.');
    } finally {
      setLoading(false);
    }
  }, [query]);

  useEffect(() => {
    void load();
  }, [load]);

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

  return (
    <div className="flex flex-col gap-5" data-testid="customers-page">
      <Panel
        title="Customers"
        description="Shoppers with accounts, and what they have ordered."
        action={
          <Button variant="secondary" onClick={load} disabled={loading}>
            Refresh
          </Button>
        }
      >
        <div className="flex flex-wrap items-end gap-3 border-b border-shell-200 px-5 py-4">
          <div className="w-full max-w-md">
            <Field label="Search" htmlFor="customer-search">
              <TextInput
                id="customer-search"
                data-testid="customer-search"
                placeholder="Name, email or phone"
                value={searchTerm}
                onChange={(event) => setSearchTerm(event.target.value)}
              />
            </Field>
          </div>
          <div className="w-48">
            <Field label="Account" htmlFor="customer-status">
              <Select
                id="customer-status"
                data-testid="customer-status"
                value={query.is_active === undefined ? '' : String(query.is_active)}
                onChange={(event) =>
                  setQuery((current) => ({
                    ...current,
                    is_active: event.target.value === '' ? undefined : event.target.value === 'true',
                    page: 1,
                  }))
                }
              >
                <option value="">All accounts</option>
                <option value="true">Active</option>
                <option value="false">Deactivated</option>
              </Select>
            </Field>
          </div>
        </div>

        {loading && !page ? (
          <LoadingState label="Loading customers…" />
        ) : error ? (
          <ErrorState message={error} onRetry={load} />
        ) : !page || page.items.length === 0 ? (
          <EmptyState
            title="No customers match"
            description={
              query.query
                ? 'Try a different search term.'
                : 'Customers appear here when they register in the mobile app.'
            }
          />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm" data-testid="customers-table">
                <thead>
                  <tr className="border-b border-shell-200 text-left text-xs uppercase tracking-wide text-shell-500">
                    <th className="px-5 py-2.5 font-semibold">Customer</th>
                    <th className="px-4 py-2.5 font-semibold">Contact</th>
                    <th className="px-4 py-2.5 text-right font-semibold">Orders</th>
                    <th className="px-4 py-2.5 text-right font-semibold">Spent</th>
                    <th className="px-4 py-2.5 font-semibold">Last order</th>
                    <th className="px-4 py-2.5 font-semibold">Account</th>
                    <th className="px-5 py-2.5 text-right font-semibold">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-shell-100">
                  {page.items.map((customer) => (
                    <tr
                      key={customer.id}
                      className="hover:bg-shell-50"
                      data-testid={`customer-row-${customer.id}`}
                    >
                      <td className="px-5 py-3">
                        <p className="max-w-[15rem] truncate font-medium text-shell-900">
                          {customer.full_name}
                        </p>
                        <p className="text-xs text-shell-500">
                          Joined {formatDate(customer.created_at)}
                        </p>
                      </td>
                      <td className="px-4 py-3">
                        <p className="max-w-[17rem] truncate text-shell-700">{customer.email}</p>
                        {customer.phone && (
                          <p className="tabular text-xs text-shell-500">{customer.phone}</p>
                        )}
                      </td>
                      <td className="tabular px-4 py-3 text-right text-shell-800">
                        {formatCount(customer.order_count)}
                      </td>
                      <td className="tabular px-4 py-3 text-right font-semibold text-shell-900">
                        {formatMoney(customer.total_spent)}
                      </td>
                      <td className="tabular px-4 py-3 text-shell-600">
                        {formatDate(customer.last_order_at)}
                      </td>
                      <td className="px-4 py-3">
                        {customer.is_active ? (
                          <Badge tone="success">Active</Badge>
                        ) : (
                          <Badge tone="danger">Deactivated</Badge>
                        )}
                      </td>
                      <td className="px-5 py-3 text-right">
                        <Button
                          variant="secondary"
                          disabled={customer.order_count === 0}
                          onClick={() =>
                            navigate(`/orders?query=${encodeURIComponent(customer.email)}`)
                          }
                          data-testid={`customer-orders-${customer.id}`}
                        >
                          Orders
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination
              meta={page.meta}
              itemNoun="customer"
              onPageChange={(next) => setQuery((current) => ({ ...current, page: next }))}
            />
          </>
        )}
      </Panel>

      <p className="text-xs text-shell-500">
        Spend excludes cancelled orders. Changing an account&rsquo;s status or role is an
        administrator action and is not done from this screen.
      </p>
    </div>
  );
}
