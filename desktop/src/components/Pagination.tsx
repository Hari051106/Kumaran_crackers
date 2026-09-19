/** Pagination control driven by the backend's `PaginationMeta`. */
import type { PaginationMeta } from '../types/api';
import { formatCount } from '../lib/money';
import { Button } from './ui';

interface PaginationProps {
  meta: PaginationMeta;
  onPageChange(page: number): void;
  itemNoun?: string;
}

export function Pagination({ meta, onPageChange, itemNoun = 'item' }: PaginationProps) {
  if (meta.total === 0) return null;

  const firstOnPage = (meta.page - 1) * meta.page_size + 1;
  const lastOnPage = Math.min(meta.page * meta.page_size, meta.total);
  const plural = meta.total === 1 ? itemNoun : `${itemNoun}s`;

  return (
    <div className="flex items-center justify-between gap-4 border-t border-shell-200 px-5 py-3">
      <p className="tabular text-sm text-shell-500">
        Showing <span className="font-medium text-shell-700">{formatCount(firstOnPage)}</span>–
        <span className="font-medium text-shell-700">{formatCount(lastOnPage)}</span> of{' '}
        <span className="font-medium text-shell-700">{formatCount(meta.total)}</span> {plural}
      </p>

      <div className="flex items-center gap-2">
        <Button
          variant="secondary"
          onClick={() => onPageChange(meta.page - 1)}
          disabled={!meta.has_previous}
        >
          Previous
        </Button>
        <span className="tabular px-2 text-sm text-shell-600">
          Page {meta.page} of {Math.max(meta.total_pages, 1)}
        </span>
        <Button
          variant="secondary"
          onClick={() => onPageChange(meta.page + 1)}
          disabled={!meta.has_next}
          data-testid="next-page"
        >
          Next
        </Button>
      </div>
    </div>
  );
}
