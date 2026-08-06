import { Download, Expand, GripHorizontal, TableProperties, X } from 'lucide-react';
import { type ReactNode, useEffect, useId, useRef, useState } from 'react';
import { createPortal } from 'react-dom';

export function WidgetFrame({
  title,
  subtitle,
  editMode,
  onInspect,
  onExport,
  children,
}: {
  title: string;
  subtitle?: string;
  editMode: boolean;
  onInspect?: () => void;
  onExport?: () => void;
  children: ReactNode;
}) {
  const [expanded, setExpanded] = useState(false);
  const headingId = useId();
  const expandButtonRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLElement>(null);

  useEffect(() => {
    if (!expanded) return;
    const dialog = dialogRef.current;
    dialog?.focus();
    const onKeyDown = (event: KeyboardEvent): void => {
      if (event.key === 'Escape') {
        setExpanded(false);
        return;
      }
      if (event.key !== 'Tab' || !dialog) return;
      const focusable = [
        ...dialog.querySelectorAll<HTMLElement>(
          'button:not([disabled]), [href], [tabindex]:not([tabindex="-1"])',
        ),
      ];
      if (focusable.length === 0) {
        event.preventDefault();
        dialog.focus();
        return;
      }
      const first = focusable[0];
      const last = focusable.at(-1);
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    };
    document.body.classList.add('modal-open');
    window.addEventListener('keydown', onKeyDown);
    return () => {
      document.body.classList.remove('modal-open');
      window.removeEventListener('keydown', onKeyDown);
      expandButtonRef.current?.focus();
    };
  }, [expanded]);

  const header = (
    <header className="widget-header">
      <div className={editMode ? 'widget-drag-handle' : undefined}>
        <div className="widget-title-row">
          {editMode ? <GripHorizontal size={14} aria-hidden="true" /> : null}
          <h2 id={headingId}>{title}</h2>
        </div>
        {subtitle ? <p>{subtitle}</p> : null}
      </div>
      <div className="widget-actions">
        {onInspect ? (
          <button
            type="button"
            className="icon-button"
            aria-label={`Inspectează datele ${title}`}
            onClick={onInspect}
          >
            <TableProperties size={15} />
          </button>
        ) : null}
        {onExport ? (
          <button
            type="button"
            className="icon-button"
            aria-label={`Exportă datele ${title}`}
            onClick={onExport}
          >
            <Download size={15} />
          </button>
        ) : null}
        <button
          ref={expandButtonRef}
          type="button"
          className="icon-button"
          aria-label={`Extinde ${title}`}
          onClick={() => setExpanded(true)}
        >
          <Expand size={15} />
        </button>
      </div>
    </header>
  );

  return (
    <>
      <article className="widget-card" aria-labelledby={headingId}>
        {header}
        <div className="widget-body">{children}</div>
      </article>
      {expanded
        ? createPortal(
            <div className="widget-modal-backdrop">
              <section
                ref={dialogRef}
                className="widget-modal"
                role="dialog"
                aria-modal="true"
                aria-labelledby={`${headingId}-expanded`}
                tabIndex={-1}
                onMouseDown={(event) => event.stopPropagation()}
              >
                <header className="widget-header widget-header--modal">
                  <div>
                    <h2 id={`${headingId}-expanded`}>{title}</h2>
                    {subtitle ? <p>{subtitle}</p> : null}
                  </div>
                  <button
                    type="button"
                    className="icon-button"
                    aria-label="Închide"
                    onClick={() => setExpanded(false)}
                  >
                    <X size={17} />
                  </button>
                </header>
                <div className="widget-modal-body">{children}</div>
              </section>
            </div>,
            document.body,
          )
        : null}
    </>
  );
}
