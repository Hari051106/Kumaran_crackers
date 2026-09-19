/**
 * Modal dialog and a confirmation variant.
 *
 * Handles the things that make a dialog usable rather than merely visible:
 * Escape to close, a scroll lock on the page behind, focus moved into the
 * dialog on open, and a click on the backdrop dismissing it.
 */
import { useEffect, useRef, type ReactNode } from 'react';

import { Button } from './ui';

interface ModalProps {
  open: boolean;
  title: string;
  description?: string;
  onClose(): void;
  children: ReactNode;
  footer?: ReactNode;
  size?: 'md' | 'lg';
}

export function Modal({
  open,
  title,
  description,
  onClose,
  children,
  footer,
  size = 'md',
}: ModalProps) {
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKeyDown);

    // Stop the page behind the dialog from scrolling.
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    panelRef.current?.focus();

    return () => {
      document.removeEventListener('keydown', onKeyDown);
      document.body.style.overflow = previousOverflow;
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-40 flex items-start justify-center overflow-y-auto bg-shell-950/50 p-6 backdrop-blur-[2px]"
      onMouseDown={(event) => {
        // Only a click that both starts and ends on the backdrop closes it, so
        // a drag that finishes outside the panel does not dismiss the form.
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        ref={panelRef}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={`my-8 w-full rounded-xl bg-white shadow-panel outline-none ${
          size === 'lg' ? 'max-w-3xl' : 'max-w-xl'
        }`}
      >
        <header className="flex items-start justify-between gap-4 border-b border-shell-200 px-6 py-4">
          <div>
            <h2 className="text-base font-semibold text-shell-900">{title}</h2>
            {description && <p className="mt-0.5 text-sm text-shell-500">{description}</p>}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close dialog"
            className="focus-ring rounded-lg p-1 text-shell-400 transition hover:bg-shell-100 hover:text-shell-600"
          >
            <svg viewBox="0 0 20 20" fill="currentColor" className="h-5 w-5">
              <path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z" />
            </svg>
          </button>
        </header>

        <div className="px-6 py-5">{children}</div>

        {footer && (
          <footer className="flex justify-end gap-3 border-t border-shell-200 bg-shell-50 px-6 py-4">
            {footer}
          </footer>
        )}
      </div>
    </div>
  );
}

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  destructive?: boolean;
  busy?: boolean;
  onConfirm(): void;
  onCancel(): void;
}

/** A deliberate yes/no gate in front of anything irreversible. */
export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  destructive = false,
  busy = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  return (
    <Modal
      open={open}
      title={title}
      onClose={busy ? () => undefined : onCancel}
      footer={
        <>
          <Button variant="secondary" onClick={onCancel} disabled={busy}>
            {cancelLabel}
          </Button>
          <Button
            variant={destructive ? 'danger' : 'primary'}
            onClick={onConfirm}
            loading={busy}
            data-testid="confirm-button"
          >
            {confirmLabel}
          </Button>
        </>
      }
    >
      <p className="text-sm leading-6 text-shell-600">{message}</p>
    </Modal>
  );
}
