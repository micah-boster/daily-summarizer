"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { CommandPalette } from "@/components/command/command-palette";
import { ConfigPanel } from "@/components/config/config-panel";
import { EntityFormPanel } from "@/components/entity/entity-form-panel";
import { EntityDeleteDialog } from "@/components/entity/entity-delete-dialog";
import { ShortcutHelp } from "@/components/keyboard/shortcut-help";
import { useTheme } from "@/hooks/use-theme";

/** Mounts global hooks that need to run on every page. */
function GlobalHooks() {
  useTheme(); // applies theme class to <html> on mount
  return null;
}

export function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 5 * 60 * 1000,
            retry: 1,
          },
        },
      }),
  );

  return (
    <QueryClientProvider client={queryClient}>
      <GlobalHooks />
      {children}
      <CommandPalette />
      <ConfigPanel />
      <EntityFormPanel />
      <EntityDeleteDialog />
      <ShortcutHelp />
    </QueryClientProvider>
  );
}
