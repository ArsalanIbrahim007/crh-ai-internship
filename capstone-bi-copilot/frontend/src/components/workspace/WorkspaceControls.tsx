import {
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";
import { MoreHorizontal, X } from "lucide-react";

export function WorkspaceDialog({
  title,
  children,
  close,
}: {
  title: string;
  children: ReactNode;
  close: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    const previous = document.activeElement as HTMLElement;
    dialog?.showModal();
    return () => {
      dialog?.close();
      previous?.focus();
    };
  }, []);
  return (
    <dialog
      ref={ref}
      className="workspace-dialog"
      aria-label={title}
      onCancel={(event) => {
        event.preventDefault();
        close();
      }}
      onClick={(event) => {
        if (event.target === event.currentTarget) {
          const box = event.currentTarget.getBoundingClientRect();
          if (
            event.clientX < box.left ||
            event.clientX > box.right ||
            event.clientY < box.top ||
            event.clientY > box.bottom
          )
            close();
        }
      }}
    >
      <button
        className="workspace-dialog__close"
        aria-label="Close dialog"
        onClick={close}
      >
        <X size={19} />
      </button>
      <h2>{title}</h2>
      {children}
    </dialog>
  );
}
export function ActionMenu({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  const anchor = useRef<HTMLButtonElement>(null),
    panel = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false),
    [position, setPosition] = useState({ left: 0, top: 0 });
  useLayoutEffect(() => {
    if (!open) return;
    const place = () => {
      const rect = anchor.current?.getBoundingClientRect();
      if (!rect) return;
      const height = panel.current?.offsetHeight ?? 180;
      setPosition({
        left: Math.max(8, Math.min(rect.right - 172, innerWidth - 180)),
        top:
          rect.bottom + height + 8 > innerHeight
            ? Math.max(8, rect.top - height)
            : rect.bottom + 4,
      });
    };
    place();
    panel.current?.querySelector("button")?.focus();
    window.addEventListener("resize", place);
    window.addEventListener("scroll", place, true);
    return () => {
      window.removeEventListener("resize", place);
      window.removeEventListener("scroll", place, true);
    };
  }, [open]);
  useEffect(() => {
    if (!open) return;
    const outside = (event: PointerEvent) => {
      if (
        !panel.current?.contains(event.target as Node) &&
        !anchor.current?.contains(event.target as Node)
      )
        setOpen(false);
    };
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
        anchor.current?.focus();
      }
    };
    document.addEventListener("pointerdown", outside);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("pointerdown", outside);
      document.removeEventListener("keydown", escape);
    };
  }, [open]);
  return (
    <div className="workspace-menu">
      <button
        ref={anchor}
        className="workspace-menu__trigger"
        aria-label={label}
        title={label}
        aria-expanded={open}
        onClick={() => setOpen(!open)}
      >
        <MoreHorizontal size={20} />
      </button>
      {open &&
        createPortal(
          <div
            ref={panel}
            className="workspace-menu__items"
            style={{ ...position, position: "fixed" }}
            onClick={() => {
              anchor.current?.focus();
              setOpen(false);
            }}
          >
            {children}
          </div>,
          document.body,
        )}
    </div>
  );
}
