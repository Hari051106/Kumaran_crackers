/**
 * Category management.
 *
 * Categories are data the mobile app reads at runtime, so nothing here is
 * hardcoded in either client.
 */
import { useCallback, useEffect, useState, type FormEvent } from 'react';

import { ApiError } from '../api/client';
import { categoriesApi, type CategoryInput } from '../api/endpoints';
import { ConfirmDialog, Modal } from '../components/Modal';
import { useToast } from '../components/Toast';
import {
  Badge,
  Button,
  EmptyState,
  ErrorState,
  Field,
  LoadingState,
  Panel,
  TextArea,
  TextInput,
} from '../components/ui';
import { formatCount } from '../lib/money';
import type { CategoryWithCount } from '../types/api';

const BLANK: CategoryInput = {
  name: '',
  description: '',
  display_order: 0,
  is_active: true,
};

export function CategoriesPage() {
  const toast = useToast();
  const [categories, setCategories] = useState<CategoryWithCount[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [editorOpen, setEditorOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState<CategoryInput>(BLANK);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);

  const [deleting, setDeleting] = useState<CategoryWithCount | null>(null);
  const [deleteBusy, setDeleteBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // Staff see deactivated categories too, so they can reactivate them.
      setCategories(await categoriesApi.list(true));
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Could not load categories.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  function openCreate() {
    setEditingId(null);
    setForm(BLANK);
    setFieldErrors({});
    setEditorOpen(true);
  }

  function openEdit(category: CategoryWithCount) {
    setEditingId(category.id);
    setForm({
      name: category.name,
      description: category.description ?? '',
      display_order: category.display_order,
      is_active: category.is_active,
    });
    setFieldErrors({});
    setEditorOpen(true);
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!form.name.trim()) {
      setFieldErrors({ name: 'Enter a category name.' });
      return;
    }

    setSaving(true);
    setFieldErrors({});
    try {
      if (editingId === null) {
        await categoriesApi.create(form);
        toast.success(`Category "${form.name}" created.`);
      } else {
        await categoriesApi.update(editingId, form);
        toast.success(`Category "${form.name}" updated.`);
      }
      setEditorOpen(false);
      await load();
    } catch (caught) {
      if (caught instanceof ApiError) {
        // Surface per-field validation messages next to their inputs.
        if (Object.keys(caught.details).length) setFieldErrors(caught.details);
        else toast.error(caught.message);
      } else {
        toast.error('Could not save the category.');
      }
    } finally {
      setSaving(false);
    }
  }

  async function confirmDelete() {
    if (!deleting) return;
    setDeleteBusy(true);
    try {
      await categoriesApi.remove(deleting.id);
      toast.success(`Category "${deleting.name}" deleted.`);
      setDeleting(null);
      await load();
    } catch (caught) {
      // The backend refuses to delete a category that still holds products.
      toast.error(caught instanceof ApiError ? caught.message : 'Could not delete the category.');
      setDeleting(null);
    } finally {
      setDeleteBusy(false);
    }
  }

  if (loading) return <LoadingState label="Loading categories…" />;
  if (error) return <ErrorState message={error} onRetry={load} />;

  return (
    <div className="flex flex-col gap-6" data-testid="categories-page">
      <Panel
        title="Categories"
        description="Shown on the customer app home screen, in display order."
        action={
          <Button onClick={openCreate} data-testid="new-category">
            New category
          </Button>
        }
      >
        {categories.length === 0 ? (
          <EmptyState
            title="No categories yet"
            description="Create your first category to start building the catalogue."
            action={<Button onClick={openCreate}>New category</Button>}
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-shell-200 text-left text-xs uppercase tracking-wide text-shell-500">
                <th className="px-5 py-2.5 font-semibold">Order</th>
                <th className="px-5 py-2.5 font-semibold">Name</th>
                <th className="px-5 py-2.5 font-semibold">Slug</th>
                <th className="px-5 py-2.5 text-right font-semibold">Products</th>
                <th className="px-5 py-2.5 font-semibold">Status</th>
                <th className="px-5 py-2.5 text-right font-semibold">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-shell-100">
              {categories.map((category) => (
                <tr key={category.id} className="hover:bg-shell-50" data-testid="category-row">
                  <td className="tabular px-5 py-3 text-shell-500">{category.display_order}</td>
                  <td className="px-5 py-3">
                    <p className="font-medium text-shell-900">{category.name}</p>
                    {category.description && (
                      <p className="max-w-md truncate text-xs text-shell-500">
                        {category.description}
                      </p>
                    )}
                  </td>
                  <td className="px-5 py-3 font-mono text-xs text-shell-500">{category.slug}</td>
                  <td className="tabular px-5 py-3 text-right font-medium text-shell-700">
                    {formatCount(category.product_count)}
                  </td>
                  <td className="px-5 py-3">
                    {category.is_active ? (
                      <Badge tone="success">Active</Badge>
                    ) : (
                      <Badge tone="neutral">Hidden</Badge>
                    )}
                  </td>
                  <td className="px-5 py-3">
                    <div className="flex justify-end gap-1">
                      <Button variant="ghost" onClick={() => openEdit(category)}>
                        Edit
                      </Button>
                      <Button
                        variant="ghost"
                        className="text-rose-600 hover:bg-rose-50"
                        onClick={() => setDeleting(category)}
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
        )}
      </Panel>

      {/* ---- Create / edit ---- */}
      <Modal
        open={editorOpen}
        title={editingId === null ? 'New category' : 'Edit category'}
        description="The URL slug is generated from the name automatically."
        onClose={() => setEditorOpen(false)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setEditorOpen(false)} disabled={saving}>
              Cancel
            </Button>
            <Button type="submit" form="category-form" loading={saving} data-testid="save-category">
              {editingId === null ? 'Create category' : 'Save changes'}
            </Button>
          </>
        }
      >
        <form id="category-form" onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
          <Field label="Name" htmlFor="name" required error={fieldErrors.name}>
            <TextInput
              id="name"
              value={form.name}
              autoFocus
              invalid={!!fieldErrors.name}
              onChange={(event) => setForm({ ...form, name: event.target.value })}
              placeholder="e.g. Flower Pots"
            />
          </Field>

          <Field label="Description" htmlFor="description" error={fieldErrors.description}>
            <TextArea
              id="description"
              value={form.description ?? ''}
              onChange={(event) => setForm({ ...form, description: event.target.value })}
              placeholder="A short line shown under the category name."
            />
          </Field>

          <Field
            label="Display order"
            htmlFor="display_order"
            hint="Lower numbers appear first on the customer home screen."
            error={fieldErrors.display_order}
          >
            <TextInput
              id="display_order"
              type="number"
              min={0}
              value={form.display_order ?? 0}
              onChange={(event) =>
                setForm({ ...form, display_order: Number(event.target.value) || 0 })
              }
            />
          </Field>

          <label className="flex items-center gap-2.5">
            <input
              type="checkbox"
              checked={form.is_active ?? true}
              onChange={(event) => setForm({ ...form, is_active: event.target.checked })}
              className="h-4 w-4 rounded border-shell-300 text-brand-600 focus:ring-brand-500"
            />
            <span className="text-sm text-shell-700">
              Visible in the customer app
              <span className="block text-xs text-shell-500">
                Hiding a category also hides its products from shoppers.
              </span>
            </span>
          </label>
        </form>
      </Modal>

      <ConfirmDialog
        open={deleting !== null}
        title="Delete category?"
        message={
          deleting?.product_count
            ? `"${deleting.name}" still holds ${deleting.product_count} product(s). The server will refuse to delete it — move or delete those products first, or hide the category instead.`
            : `"${deleting?.name}" will be permanently removed. This cannot be undone.`
        }
        confirmLabel="Delete category"
        destructive
        busy={deleteBusy}
        onConfirm={confirmDelete}
        onCancel={() => setDeleting(null)}
      />
    </div>
  );
}
