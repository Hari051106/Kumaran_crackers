/**
 * Inventory: stock levels, reorder flags and adjustments.
 *
 * Stock edits go through the backend's atomic adjustment endpoint, so two
 * staff members editing the same product cannot silently overwrite one
 * another's change.
 */
import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react';

import { ApiError } from '../api/client';
import { productsApi } from '../api/endpoints';
import { Modal } from '../components/Modal';
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
import { StockBadge } from './DashboardPage';
import { formatCount } from '../lib/money';
import type { Page, ProductListItem, StockStatus } from '../types/api';

const PAGE_SIZE = 12;

type StockFilter = 'all' | 'low' | 'out';

export function InventoryPage() {
  const toast = useToast();

  const [page, setPage] = useState<Page<ProductListItem> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [stockFilter, setStockFilter] = useState<StockFilter>('all');
  const [currentPage, setCurrentPage] = useState(1);

  // ---- Adjustment dialog ----
  const [adjusting, setAdjusting] = useState<ProductListItem | null>(null);
  const [mode, setMode] = useState<'set' | 'delta'>('delta');
  const [amount, setAmount] = useState('');
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [adjustError, setAdjustError] = useState<string | null>(null);
  const [currentStock, setCurrentStock] = useState<number | null>(null);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(search);
      setCurrentPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setPage(
        await productsApi.search({
          query: debouncedSearch || undefined,
          page: currentPage,
          page_size: PAGE_SIZE,
          sort: 'name_asc',
          include_inactive: true,
        }),
      );
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Could not load inventory.');
    } finally {
      setLoading(false);
    }
  }, [debouncedSearch, currentPage]);

  useEffect(() => {
    void load();
  }, [load]);

  // The stock filter narrows the page already fetched. It is applied here
  // rather than server-side because status is derived, not a column.
  const rows = useMemo(() => {
    const items = page?.items ?? [];
    if (stockFilter === 'low') return items.filter((i) => i.stock_status === 'LOW_STOCK');
    if (stockFilter === 'out') return items.filter((i) => i.stock_status === 'OUT_OF_STOCK');
    return items;
  }, [page, stockFilter]);

  async function openAdjust(item: ProductListItem) {
    setAdjusting(item);
    setMode('delta');
    setAmount('');
    setReason('');
    setAdjustError(null);
    setCurrentStock(null);
    try {
      const full = await productsApi.getById(item.id);
      setCurrentStock(full.stock_quantity);
    } catch {
      // The exact level is a nicety; the adjustment still works without it.
    }
  }

  async function submitAdjustment(event: FormEvent) {
    event.preventDefault();
    if (!adjusting) return;

    const parsed = Number(amount);
    if (!amount.trim() || Number.isNaN(parsed)) {
      setAdjustError('Enter a whole number.');
      return;
    }
    if (mode === 'set' && parsed < 0) {
      setAdjustError('Stock cannot be negative.');
      return;
    }
    if (mode === 'delta' && parsed === 0) {
      setAdjustError('Enter a non-zero change.');
      return;
    }

    setBusy(true);
    setAdjustError(null);
    try {
      const updated = await productsApi.adjustStock(adjusting.id, {
        ...(mode === 'set' ? { set_to: parsed } : { delta: parsed }),
        ...(reason.trim() ? { reason: reason.trim() } : {}),
      });
      toast.success(`${adjusting.name}: stock is now ${formatCount(updated.stock_quantity)}.`);
      setAdjusting(null);
      await load();
    } catch (caught) {
      // The server refuses a reduction that would drive stock below zero.
      setAdjustError(
        caught instanceof ApiError ? caught.message : 'Could not adjust the stock level.',
      );
    } finally {
      setBusy(false);
    }
  }

  const counts = useMemo(() => {
    const items = page?.items ?? [];
    const tally = (status: StockStatus) => items.filter((i) => i.stock_status === status).length;
    return {
      low: tally('LOW_STOCK'),
      out: tally('OUT_OF_STOCK'),
    };
  }, [page]);

  return (
    <div className="flex flex-col gap-6" data-testid="inventory-page">
      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-[260px] flex-1">
          <Field label="Search" htmlFor="inv-search">
            <TextInput
              id="inv-search"
              data-testid="inventory-search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Product name or SKU…"
            />
          </Field>
        </div>
        <div className="w-56">
          <Field label="Stock status" htmlFor="inv-filter">
            <Select
              id="inv-filter"
              value={stockFilter}
              onChange={(event) => setStockFilter(event.target.value as StockFilter)}
            >
              <option value="all">All products</option>
              <option value="low">Low stock ({counts.low} on this page)</option>
              <option value="out">Out of stock ({counts.out} on this page)</option>
            </Select>
          </Field>
        </div>
      </div>

      <Panel
        title="Stock levels"
        description="Adjustments are applied atomically, so concurrent edits cannot be lost."
      >
        {loading ? (
          <LoadingState label="Loading inventory…" />
        ) : error ? (
          <ErrorState message={error} onRetry={load} />
        ) : rows.length === 0 ? (
          <EmptyState
            title={
              stockFilter === 'low'
                ? 'Nothing is running low on this page'
                : stockFilter === 'out'
                  ? 'Nothing is out of stock on this page'
                  : 'No products found'
            }
            description={
              stockFilter === 'all'
                ? 'Add products to start tracking stock.'
                : 'Try another page or clear the filter.'
            }
          />
        ) : (
          <>
            <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-shell-200 text-left text-xs uppercase tracking-wide text-shell-500">
                  <th className="px-5 py-2.5 font-semibold">Product</th>
                  <th className="px-5 py-2.5 font-semibold">SKU</th>
                  <th className="px-5 py-2.5 font-semibold">Category</th>
                  <th className="px-5 py-2.5 font-semibold">Status</th>
                  <th className="px-5 py-2.5 text-right font-semibold">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-shell-100">
                {rows.map((item) => (
                  <tr key={item.id} className="hover:bg-shell-50" data-testid="inventory-row">
                    <td className="px-5 py-3 font-medium text-shell-900">{item.name}</td>
                    <td className="tabular px-5 py-3 text-shell-500">{item.sku}</td>
                    <td className="px-5 py-3 text-shell-600">{item.category.name}</td>
                    <td className="px-5 py-3">
                      <StockBadge status={item.stock_status} />
                    </td>
                    <td className="px-5 py-3 text-right">
                      <Button
                        variant="secondary"
                        onClick={() => void openAdjust(item)}
                        data-testid="adjust-stock"
                      >
                        Adjust stock
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>
            {page && (
              <Pagination meta={page.meta} onPageChange={setCurrentPage} itemNoun="product" />
            )}
          </>
        )}
      </Panel>

      <Modal
        open={adjusting !== null}
        title="Adjust stock"
        description={adjusting?.name}
        onClose={() => setAdjusting(null)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setAdjusting(null)} disabled={busy}>
              Cancel
            </Button>
            <Button type="submit" form="stock-form" loading={busy} data-testid="save-stock">
              Apply
            </Button>
          </>
        }
      >
        <form id="stock-form" onSubmit={submitAdjustment} className="flex flex-col gap-4" noValidate>
          {currentStock !== null && (
            <p className="tabular rounded-lg bg-shell-100 px-4 py-2.5 text-sm text-shell-700">
              Currently in stock: <span className="font-semibold">{formatCount(currentStock)}</span>
            </p>
          )}

          {adjustError && (
            <div
              role="alert"
              data-testid="stock-error"
              className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-medium text-rose-800"
            >
              {adjustError}
            </div>
          )}

          <Field label="How would you like to change it?" htmlFor="stock-mode">
            <Select
              id="stock-mode"
              value={mode}
              onChange={(event) => setMode(event.target.value as 'set' | 'delta')}
            >
              <option value="delta">Add or remove a quantity</option>
              <option value="set">Set an exact quantity</option>
            </Select>
          </Field>

          <Field
            label={mode === 'set' ? 'New stock level' : 'Change by'}
            htmlFor="stock-amount"
            required
            hint={
              mode === 'delta'
                ? 'Use a negative number to remove stock, e.g. -5'
                : 'The stock level will be set to exactly this number.'
            }
          >
            <TextInput
              id="stock-amount"
              data-testid="stock-amount"
              type="number"
              value={amount}
              onChange={(event) => setAmount(event.target.value)}
              placeholder={mode === 'delta' ? '+25' : '100'}
            />
          </Field>

          <Field label="Reason" htmlFor="stock-reason" hint="Optional, for your own records.">
            <TextInput
              id="stock-reason"
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              placeholder="e.g. New delivery received"
            />
          </Field>
        </form>
      </Modal>
    </div>
  );
}
