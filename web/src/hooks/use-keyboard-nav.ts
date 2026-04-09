"use client";

import { useEffect } from "react";
import { useUIStore } from "@/stores/ui-store";
import { usePipelineStore } from "@/stores/pipeline-store";
import { apiMutate } from "@/lib/api";
import { toast } from "sonner";

type Column = "left" | "center" | "right";

const COLUMN_ORDER: Column[] = ["left", "center", "right"];

function isEditableElement(el: Element | null): boolean {
  if (!el) return false;
  const tag = (el as HTMLElement).tagName?.toLowerCase();
  if (tag === "input" || tag === "textarea" || tag === "select") return true;
  if ((el as HTMLElement).isContentEditable) return true;
  return false;
}

function getItemsForColumn(column: Column): NodeListOf<Element> {
  return document.querySelectorAll(
    `[data-kb-column="${column}"] [data-kb-item]`,
  );
}

function applyFocusRing(column: Column, index: number) {
  // Remove all existing focus indicators
  document
    .querySelectorAll("[data-kb-focused]")
    .forEach((el) => {
      el.removeAttribute("data-kb-focused");
      el.classList.remove("ring-2", "ring-primary/50");
    });

  if (index < 0) return;

  const items = getItemsForColumn(column);
  const target = items[index];
  if (target) {
    target.setAttribute("data-kb-focused", "true");
    target.classList.add("ring-2", "ring-primary/50");
    (target as HTMLElement).scrollIntoView?.({
      block: "nearest",
      behavior: "smooth",
    });
  }
}

export function useKeyboardNav() {
  const focusedColumn = useUIStore((s) => s.focusedColumn);
  const focusedIndex = useUIStore((s) => s.focusedIndex);
  const commandPaletteOpen = useUIStore((s) => s.commandPaletteOpen);
  const configPanelOpen = useUIStore((s) => s.configPanelOpen);
  const setFocusedColumn = useUIStore((s) => s.setFocusedColumn);
  const setFocusedIndex = useUIStore((s) => s.setFocusedIndex);
  const toggleShortcutHelp = useUIStore((s) => s.toggleShortcutHelp);
  const shortcutHelpOpen = useUIStore((s) => s.shortcutHelpOpen);

  // Apply focus ring when column/index changes
  useEffect(() => {
    applyFocusRing(focusedColumn, focusedIndex);
    return () => {
      // Cleanup on unmount
      document
        .querySelectorAll("[data-kb-focused]")
        .forEach((el) => {
          el.removeAttribute("data-kb-focused");
          el.classList.remove("ring-2", "ring-primary/50");
        });
    };
  }, [focusedColumn, focusedIndex]);

  // Keyboard event handler
  useEffect(() => {
    function handler(e: KeyboardEvent) {
      // Skip if typing in editable element
      if (isEditableElement(document.activeElement)) return;

      // Skip if any modal/dialog is open
      if (commandPaletteOpen || configPanelOpen || shortcutHelpOpen) return;
      if (document.querySelector("[role='dialog']")) return;

      // Do not intercept modifier-key combos (Cmd+K, Ctrl+K, etc.)
      if (e.metaKey || e.ctrlKey || e.altKey) return;

      const store = useUIStore.getState();
      const col = store.focusedColumn;
      const idx = store.focusedIndex;

      switch (e.key) {
        case "j": {
          e.preventDefault();
          const items = getItemsForColumn(col);
          const maxIdx = items.length - 1;
          if (maxIdx < 0) return;
          const next = Math.min(idx + 1, maxIdx);
          setFocusedIndex(next);
          break;
        }

        case "k": {
          e.preventDefault();
          if (idx <= 0) {
            setFocusedIndex(0);
            return;
          }
          setFocusedIndex(idx - 1);
          break;
        }

        case "h": {
          e.preventDefault();
          const curIdx = COLUMN_ORDER.indexOf(col);
          if (curIdx > 0) {
            setFocusedColumn(COLUMN_ORDER[curIdx - 1]);
            setFocusedIndex(-1);
          }
          break;
        }

        case "l": {
          e.preventDefault();
          const curIdx = COLUMN_ORDER.indexOf(col);
          if (curIdx < COLUMN_ORDER.length - 1) {
            setFocusedColumn(COLUMN_ORDER[curIdx + 1]);
            setFocusedIndex(-1);
          }
          break;
        }

        case "Enter": {
          if (idx >= 0) {
            e.preventDefault();
            const items = getItemsForColumn(col);
            const target = items[idx] as HTMLElement | undefined;
            target?.click();
          }
          break;
        }

        case "Escape": {
          e.preventDefault();
          if (idx >= 0) {
            setFocusedIndex(-1);
          } else {
            setFocusedColumn("center");
          }
          break;
        }

        case "?": {
          e.preventDefault();
          toggleShortcutHelp();
          break;
        }

        case "r": {
          e.preventDefault();
          const pipelineStatus = usePipelineStore.getState().status;
          if (pipelineStatus === "running") {
            toast.info("Pipeline already running");
            return;
          }
          toast.promise(
            apiMutate("/runs", { method: "POST" }),
            {
              loading: "Starting pipeline run...",
              success: "Pipeline run started",
              error: "Failed to start pipeline run",
            },
          );
          break;
        }

        default:
          break;
      }
    }

    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [
    commandPaletteOpen,
    configPanelOpen,
    shortcutHelpOpen,
    setFocusedColumn,
    setFocusedIndex,
    toggleShortcutHelp,
  ]);
}
