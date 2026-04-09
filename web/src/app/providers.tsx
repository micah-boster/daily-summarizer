"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "next-themes";
import { useState, type ReactNode } from "react";
import { CommandPalette } from "@/components/command/command-palette";
import { ConfigPanel } from "@/components/config/config-panel";
import { EntityFormPanel } from "@/components/entity/entity-form-panel";
import { EntityDeleteDialog } from "@/components/entity/entity-delete-dialog";

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
    <ThemeProvider
      attribute="class"
      defaultTheme="system"
      enableSystem
      disableTransitionOnChange
      storageKey="theme"
    >
      <QueryClientProvider client={queryClient}>
        {children}
        <CommandPalette />
        <ConfigPanel />
        <EntityFormPanel />
        <EntityDeleteDialog />
      </QueryClientProvider>
    </ThemeProvider>
  );
}
