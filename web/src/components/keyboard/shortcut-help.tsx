"use client";

import { useUIStore } from "@/stores/ui-store";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";

interface Shortcut {
  key: string;
  description: string;
}

const NAVIGATION_SHORTCUTS: Shortcut[] = [
  { key: "j", description: "Move down / next item" },
  { key: "k", description: "Move up / previous item" },
  { key: "h", description: "Focus left column" },
  { key: "l", description: "Focus right column" },
  { key: "Enter", description: "Select focused item" },
  { key: "Esc", description: "Deselect / reset focus" },
];

const ACTION_SHORTCUTS: Shortcut[] = [
  { key: "r", description: "Run pipeline" },
  { key: "\u2318K", description: "Open command palette" },
  { key: "?", description: "Show this help" },
];

const COLUMN_INFO = [
  { key: "h/l", description: "Cycle: Left \u2190 Center \u2192 Right" },
];

function Kbd({ children }: { children: string }) {
  return (
    <kbd className="inline-flex min-w-[1.5rem] items-center justify-center rounded-md border border-border bg-muted px-1.5 py-0.5 font-mono text-xs font-medium text-foreground">
      {children}
    </kbd>
  );
}

function ShortcutGroup({
  title,
  shortcuts,
}: {
  title: string;
  shortcuts: Shortcut[];
}) {
  return (
    <div>
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        {title}
      </h3>
      <ul className="space-y-1.5">
        {shortcuts.map((s) => (
          <li key={s.key} className="flex items-center gap-3">
            <Kbd>{s.key}</Kbd>
            <span className="text-sm text-muted-foreground">
              {s.description}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function ShortcutHelp() {
  const open = useUIStore((s) => s.shortcutHelpOpen);
  const toggleShortcutHelp = useUIStore((s) => s.toggleShortcutHelp);

  return (
    <Dialog
      open={open}
      onOpenChange={(nextOpen) => {
        if (!nextOpen) toggleShortcutHelp();
      }}
    >
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Keyboard Shortcuts</DialogTitle>
          <DialogDescription>
            Vim-style navigation for power users
          </DialogDescription>
        </DialogHeader>

        <div className="grid grid-cols-2 gap-6 pt-2">
          <ShortcutGroup title="Navigation" shortcuts={NAVIGATION_SHORTCUTS} />
          <div className="space-y-6">
            <ShortcutGroup title="Actions" shortcuts={ACTION_SHORTCUTS} />
            <ShortcutGroup title="Column Focus" shortcuts={COLUMN_INFO} />
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
