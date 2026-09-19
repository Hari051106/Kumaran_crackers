/**
 * Product management: search, filter, paginate, and full CRUD.
 *
 * Prices are kept as strings from input to request. Converting to a number for
 * "convenience" would reintroduce the floating-point error the backend's
 * Decimal columns exist to prevent.
 */
import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react';

import { ApiError } from '../api/client';
import {
  categoriesApi,
  productsApi,
  type ProductInput,
  type ProductQuery,
} from '../api/endpoints';
import { ConfirmDialog, Modal } from '../components/Modal';
import { Pagination } from '../components/Pagination';
import { useToast } from '../components/Toast';
import {
  Badge,
  Button,
  EmptyState,
  ErrorState,
  Field,
  LoadingState,
  Panel,
  Select,
  TextArea,
  TextInput,
} from '../components/ui';
import { StockBadge } from './DashboardPage';
import { formatMoney, formatPercent, isValidMoney } from '../lib/money';
import type { CategoryWithCount, Page, ProductListItem, ProductSort } from '../types/api';

const PAGE_SIZE = 10;

const SORTS: { value: ProductSort; label: string }[] = [
  { value: 'newest', label: 'Newest first' },
  { value: 'name_asc', label: 'Name A–Z' },
  { value: 'price_asc', label: 'Price low to high' },
  { value: 'price_desc', label: 'Price high to low' },
  { value: 'discount', label: 'Biggest discount' },
  { value: 'popularity', label: 'Best selling' },
];

interface ProductForm {
  name: string;
  sku: string;
  description: string;
  category_id: string;
  mrp: string;
  selling_price: string;
  stock_quantity: string;
  low_stock_threshold: string;
  is_active: boolean;
  is_featured: boolean;
  image_url: string;
}

const BLANK_FORM: ProductForm = {
  name: '',
  sku: '',
  description: '',
  category_id: '',
  mrp: '',
  selling_price: '',
  stock_quantity: '0',
  low_stock_threshold: '10',
  is_active: true,
  is_featured: false,
  image_url: '',
};

export function ProductsPage() {
  const toast = useToast();

  const [page, setPage] = useState<Page<ProductListItem> | null>(null);
  const [categories, setCategories] = useState<CategoryWithCount[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // ---- Filters ----
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [sort, setSort] = useState<ProductSort>('newest');
  const [currentPage, setCurrentPage] = useState(1);

  // ---- Editor ----
  const [editorOpen, setEditorOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState<ProductForm>(BLANK_FORM);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);

  const [deleting, setDeleting] = useState<ProductListItem | null>(null);
  const [deleteBusy, setDeleteBusy] = useState(false);

  // Debounce typing so a search does not fire a request per keystroke.
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(search);
      setCurrentPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  const query = useMemo<ProductQuery>(
    () => ({
      query: debouncedSearch || undefined,
      category_id: categoryFilter ? Number(categoryFilter) : undefined,
      sort,
      page: currentPage,
      page_size: PAGE_SIZE,
      // Staff view: deactivated products must remain manageable.
      include_inactive: true,
    }),
    [debouncedSearch, categoryFilter, sort, currentPage],
  );

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [products, cats] = await Promise.all([
        productsApi.search(query),
        categoriesApi.list(true),
      ]);
      setPage(products);
      setCategories(cats);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Could not load products.');
    } finally {
      setLoading(false);
    }
  }, [query]);

  useEffect(() => {
    void load();
  }, [load]);

  function openCreate() {
    setEditingId(null);
    setForm({ ...BLANK_FORM, category_id: categories[0] ? String(categories[0].id) : '' });
    setFieldErrors({});
    setEditorOpen(true);
  }

  async function openEdit(item: ProductListItem) {
    setFieldErrors({});
    try {
      const full = await productsApi.getById(item.id);
      setEditingId(full.id);
      setForm({
        name: full.name,
        sku: full.sku,
        description: full.description ?? '',
        category_id: String(full.category.id),
        mrp: full.mrp,
        selling_price: full.selling_price,
        stock_quantity: String(full.stock_quantity),
        low_stock_threshold: String(full.low_stock_threshold),
        is_active: full.is_active,
        is_featured: full.is_featured,
        image_url: full.images[0]?.image_url ?? '',
      });
      setEditorOpen(true);
    } catch (caught) {
      toast.error(caught instanceof ApiError ? caught.message : 'Could not open that product.');
    }
  }

  /** Client-side checks that mirror the server's, for immediate feedback. */
  function validate(): Record<string, string> {
    const errors: Record<string, string> = {};
    if (!form.name.trim()) errors.name = 'Enter a product name.';
    if (!form.category_id) errors.category_id = 'Choose a category.';
    if (!isValidMoney(form.mrp)) errors.mrp = 'Enter an amount such as 250.00';
    if (!isValidMoney(form.selling_price)) {
      errors.selling_price = 'Enter an amount such as 199.00';
    }
    // The server is the authority on this rule; checking here just saves a round trip.
    if (isValidMoney(form.mrp) && isValidMoney(form.selling_price)) {
      if (Number(form.selling_price) > Number(form.mrp)) {
        errors.selling_price = 'Selling price cannot be greater than the MRP.';
      }
    }
    return errors;
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    const errors = validate();
    if (Object.keys(errors).length) {
      setFieldErrors(errors);
      return;
    }

    const payload: ProductInput = {
      name: form.name.trim(),
      description: form.description.trim() || null,
      category_id: Number(form.category_id),
      // Sent as strings, exactly as typed.
      mrp: form.mrp.trim(),
      selling_price: form.selling_price.trim(),
      stock_quantity: Number(form.stock_quantity) || 0,
      low_stock_threshold: Number(form.low_stock_threshold) || 0,
      is_active: form.is_active,
      is_featured: form.is_featured,
    };
    if (form.sku.trim()) payload.sku = form.sku.trim();
    if (form.image_url.trim() && editingId === null) {
      payload.images = [{ image_url: form.image_url.trim(), is_primary: true }];
    }

    setSaving(true);
    setFieldErrors({});
    try {
      if (editingId === null) {
        await productsApi.create(payload);
        toast.success(`"${payload.name}" added to the catalogue.`);
      } else {
        await productsApi.update(editingId, payload);
        toast.success(`"${payload.name}" updated.`);
      }
      setEditorOpen(false);
      await load();
    } catch (caught) {
      if (caught instanceof ApiError) {
        if (Object.keys(caught.details).length) setFieldErrors(caught.details);
        else toast.error(caught.message);
      } else {
        toast.error('Could not save the product.');
      }
    } finally {
      setSaving(false);
    }
  }

  async function toggleActive(item: ProductListItem) {
    try {
      await productsApi.setActive(item.id, !item.is_active);
      toast.success(`"${item.name}" ${item.is_active ? 'hidden from' : 'visible in'} the shop.`);
      await load();
    } catch (caught) {
      toast.error(caught instanceof ApiError ? caught.message : 'Could not update the product.');
    }
  }

  async function confirmDelete() {
    if (!deleting) return;
    setDeleteBusy(true);
    try {
      await productsApi.remove(deleting.id);
      toast.success(`"${deleting.name}" deleted.`);
      setDeleting(null);
      await load();
    } catch (caught) {
      toast.error(caught instanceof ApiError ? caught.message : 'Could not delete the product.');
      setDeleting(null);
    } finally {
      setDeleteBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-6" data-testid="products-page">
      {/* ---- Filter bar: one row above the table ---- */}
      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-[260px] flex-1">
          <Field label="Search" htmlFor="product-search">
            <TextInput
              id="product-search"
              data-testid="product-search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Name, SKU or description…"
            />
          </Field>
        </div>

        <div className="w-56">
          <Field label="Category" htmlFor="category-filter">
            <Select
              id="category-filter"
              value={categoryFilter}
              onChange={(event) => {
                setCategoryFilter(event.target.value);
                setCurrentPage(1);
              }}
            >
              <option value="">All categories</option>
              {categories.map((category) => (
                <option key={category.id} value={category.id}>
                  {category.name}
                </option>
              ))}
            </Select>
          </Field>
        </div>

        <div className="w-52">
          <Field label="Sort by" htmlFor="sort">
            <Select
              id="sort"
              value={sort}
              onChange={(event) => {
                setSort(event.target.value as ProductSort);
                setCurrentPage(1);
              }}
            >
              {SORTS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>
          </Field>
        </div>

        <Button onClick={openCreate} data-testid="new-product" className="mb-[1px]">
          New product
        </Button>
      </div>

      <Panel>
        {loading ? (
          <LoadingState label="Loading products…" />
        ) : error ? (
          <ErrorState message={error} onRetry={load} />
        ) : !page || page.items.length === 0 ? (
          <EmptyState
            title={debouncedSearch ? 'No products match your search' : 'No products yet'}
            description={
              debouncedSearch
                ? 'Try a different name, SKU or category.'
                : 'Add your first product to start selling.'
            }
            action={!debouncedSearch ? <Button onClick={openCreate}>New product</Button> : undefined}
          />
        ) : (
          <>
            <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-shell-200 text-left text-xs uppercase tracking-wide text-shell-500">
                  <th className="px-5 py-2.5 font-semibold">Product</th>
                  <th className="px-4 py-2.5 font-semibold">Category</th>
                  <th className="px-4 py-2.5 text-right font-semibold">Price</th>
                  <th className="px-4 py-2.5 font-semibold">Stock</th>
                  <th className="px-4 py-2.5 font-semibold">Visibility</th>
                  <th className="px-5 py-2.5 text-right font-semibold">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-shell-100">
                {page.items.map((item) => (
                  <tr key={item.id} className="hover:bg-shell-50" data-testid="product-row">
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-3">
                        {item.primary_image_url ? (
                          <img
                            src={item.primary_image_url}
                            alt=""
                            className="h-9 w-9 shrink-0 rounded-lg object-cover ring-1 ring-shell-200"
                            onError={(event) => {
                              event.currentTarget.style.visibility = 'hidden';
                            }}
                          />
                        ) : (
                          <div className="h-9 w-9 shrink-0 rounded-lg bg-shell-100" />
                        )}
                        <div className="min-w-0">
                          <p className="truncate font-medium text-shell-900">{item.name}</p>
                          <p className="tabular truncate text-xs text-shell-500">{item.sku}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-shell-600">
                      <span className="block max-w-[9rem] truncate">{item.category.name}</span>
                    </td>
                    {/* Price, MRP and discount read as one fact, so they share
                        a cell rather than spreading across three columns. */}
                    <td className="tabular whitespace-nowrap px-4 py-3 text-right">
                      <p className="font-semibold text-shell-900">
                        {formatMoney(item.selling_price)}
                      </p>
                      {item.discount_percentage === '0.0' ? (
                        <p className="text-xs text-shell-400">at MRP</p>
                      ) : (
                        <p className="text-xs text-shell-500">
                          <span className="line-through">{formatMoney(item.mrp)}</span>
                          <span className="ml-1.5 font-semibold text-brand-600">
                            {formatPercent(item.discount_percentage)} off
                          </span>
                        </p>
                      )}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3">
                      <StockBadge status={item.stock_status} />
                    </td>
                    <td className="px-4 py-3">
                      {item.is_active ? (
                        <Badge tone="success">Live</Badge>
                      ) : (
                        <Badge tone="neutral">Hidden</Badge>
                      )}
                    </td>
                    <td className="px-5 py-3">
                      <div className="flex justify-end gap-0.5 whitespace-nowrap">
                        <Button
                          variant="ghost"
                          className="px-2"
                          onClick={() => void openEdit(item)}
                        >
                          Edit
                        </Button>
                        <Button
                          variant="ghost"
                          className="px-2"
                          onClick={() => void toggleActive(item)}
                        >
                          {item.is_active ? 'Hide' : 'Show'}
                        </Button>
                        <Button
                          variant="ghost"
                          className="px-2 text-rose-600 hover:bg-rose-50"
                          onClick={() => setDeleting(item)}
                        >
                          Delete
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>
            <Pagination meta={page.meta} onPageChange={setCurrentPage} itemNoun="product" />
          </>
        )}
      </Panel>

      {/* ---- Create / edit ---- */}
      <Modal
        open={editorOpen}
        size="lg"
        title={editingId === null ? 'New product' : 'Edit product'}
        description="Discount is calculated from the MRP and selling price automatically."
        onClose={() => setEditorOpen(false)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setEditorOpen(false)} disabled={saving}>
              Cancel
            </Button>
            <Button type="submit" form="product-form" loading={saving} data-testid="save-product">
              {editingId === null ? 'Add product' : 'Save changes'}
            </Button>
          </>
        }
      >
        <form id="product-form" onSubmit={onSubmit} className="grid grid-cols-2 gap-4" noValidate>
          <div className="col-span-2">
            <Field label="Product name" htmlFor="p-name" required error={fieldErrors.name}>
              <TextInput
                id="p-name"
                data-testid="product-name"
                value={form.name}
                autoFocus
                invalid={!!fieldErrors.name}
                onChange={(event) => setForm({ ...form, name: event.target.value })}
                placeholder="e.g. Colour Sparkler 30cm"
              />
            </Field>
          </div>

          <Field
            label="SKU"
            htmlFor="p-sku"
            hint={editingId === null ? 'Left blank, one is generated for you.' : undefined}
            error={fieldErrors.sku}
          >
            <TextInput
              id="p-sku"
              value={form.sku}
              invalid={!!fieldErrors.sku}
              onChange={(event) => setForm({ ...form, sku: event.target.value })}
              placeholder="SPK-001"
            />
          </Field>

          <Field label="Category" htmlFor="p-category" required error={fieldErrors.category_id}>
            <Select
              id="p-category"
              data-testid="product-category"
              value={form.category_id}
              invalid={!!fieldErrors.category_id}
              onChange={(event) => setForm({ ...form, category_id: event.target.value })}
            >
              <option value="">Choose a category…</option>
              {categories.map((category) => (
                <option key={category.id} value={category.id}>
                  {category.name}
                </option>
              ))}
            </Select>
          </Field>

          <Field label="MRP" htmlFor="p-mrp" required hint="In rupees" error={fieldErrors.mrp}>
            <TextInput
              id="p-mrp"
              data-testid="product-mrp"
              inputMode="decimal"
              value={form.mrp}
              invalid={!!fieldErrors.mrp}
              onChange={(event) => setForm({ ...form, mrp: event.target.value })}
              placeholder="250.00"
            />
          </Field>

          <Field
            label="Selling price"
            htmlFor="p-price"
            required
            hint="Must not exceed the MRP"
            error={fieldErrors.selling_price}
          >
            <TextInput
              id="p-price"
              data-testid="product-price"
              inputMode="decimal"
              value={form.selling_price}
              invalid={!!fieldErrors.selling_price}
              onChange={(event) => setForm({ ...form, selling_price: event.target.value })}
              placeholder="199.00"
            />
          </Field>

          <Field label="Stock quantity" htmlFor="p-stock" error={fieldErrors.stock_quantity}>
            <TextInput
              id="p-stock"
              data-testid="product-stock"
              type="number"
              min={0}
              value={form.stock_quantity}
              onChange={(event) => setForm({ ...form, stock_quantity: event.target.value })}
            />
          </Field>

          <Field
            label="Low-stock threshold"
            htmlFor="p-threshold"
            hint="Flags the product for reordering"
            error={fieldErrors.low_stock_threshold}
          >
            <TextInput
              id="p-threshold"
              type="number"
              min={0}
              value={form.low_stock_threshold}
              onChange={(event) => setForm({ ...form, low_stock_threshold: event.target.value })}
            />
          </Field>

          <div className="col-span-2">
            <Field label="Description" htmlFor="p-description" error={fieldErrors.description}>
              <TextArea
                id="p-description"
                value={form.description}
                onChange={(event) => setForm({ ...form, description: event.target.value })}
                placeholder="What makes this product worth buying?"
              />
            </Field>
          </div>

          {editingId === null && (
            <div className="col-span-2">
              <Field label="Image URL" htmlFor="p-image" hint="Optional. Shown on the product card.">
                <TextInput
                  id="p-image"
                  value={form.image_url}
                  onChange={(event) => setForm({ ...form, image_url: event.target.value })}
                  placeholder="https://…"
                />
              </Field>
            </div>
          )}

          <div className="col-span-2 flex gap-6 border-t border-shell-200 pt-4">
            <label className="flex items-center gap-2.5">
              <input
                type="checkbox"
                checked={form.is_active}
                onChange={(event) => setForm({ ...form, is_active: event.target.checked })}
                className="h-4 w-4 rounded border-shell-300 text-brand-600 focus:ring-brand-500"
              />
              <span className="text-sm text-shell-700">Visible in the shop</span>
            </label>
            <label className="flex items-center gap-2.5">
              <input
                type="checkbox"
                checked={form.is_featured}
                onChange={(event) => setForm({ ...form, is_featured: event.target.checked })}
                className="h-4 w-4 rounded border-shell-300 text-brand-600 focus:ring-brand-500"
              />
              <span className="text-sm text-shell-700">Feature on the home screen</span>
            </label>
          </div>
        </form>
      </Modal>

      <ConfirmDialog
        open={deleting !== null}
        title="Delete product?"
        message={`"${deleting?.name}" and its images will be permanently removed. To keep it for the record but take it off sale, hide it instead.`}
        confirmLabel="Delete product"
        destructive
        busy={deleteBusy}
        onConfirm={confirmDelete}
        onCancel={() => setDeleting(null)}
      />
    </div>
  );
}
