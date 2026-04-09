"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { CommandPalette } from "@/components/command/command-palette";
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
    <QueryClientProvider client={queryClient}>
      {children}
      <CommandPalette />
      <EntityFormPanel />
      <EntityDeleteDialog />
    </QueryClientProvider>
  );
}
