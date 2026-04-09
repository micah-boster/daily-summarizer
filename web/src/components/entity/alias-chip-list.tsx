"use client";

import { useQueryClient, useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { apiMutate } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { XIcon } from "lucide-react";
import { useState, useCallback } from "react";

interface AliasChipListProps {
  aliases: string[];
  entityId: string;
}

export function AliasChipList({ aliases, entityId }: AliasChipListProps) {
  const queryClient = useQueryClient();
  const [optimisticallyRemoved, setOptimisticallyRemoved] = useState<
    Set<string>
  >(new Set());

  const removeAlias = useCallback(
    (alias: string) => {
      // Optimistically hide the chip
      setOptimisticallyRemoved((prev) => new Set(prev).add(alias));

      const undoRemoval = () => {
        setOptimisticallyRemoved((prev) => {
          const next = new Set(prev);
          next.delete(alias);
          return next;
        });
      };

      // Fire the API call
      apiMutate<void>(`/entities/${entityId}/aliases/${encodeURIComponent(alias)}`, {
        method: "DELETE",
      })
        .then(() => {
          // Show undo toast
          toast("Alias removed", {
            description: `"${alias}" was removed`,
            duration: 5000,
            action: {
              label: "Undo",
              onClick: () => {
                // Re-add the alias
                apiMutate(`/entities/${entityId}/aliases`, {
                  method: "POST",
                  body: { alias },
                })
                  .then(() => {
                    undoRemoval();
                    queryClient.invalidateQueries({
                      queryKey: ["entity-view", entityId],
                    });
                  })
                  .catch(() => {
                    toast.error("Failed to undo alias removal");
                  });
              },
            },
          });
          queryClient.invalidateQueries({
            queryKey: ["entity-view", entityId],
          });
        })
        .catch(() => {
          // Restore chip on failure
          undoRemoval();
          toast.error(`Failed to remove alias "${alias}"`);
        });
    },
    [entityId, queryClient],
  );

  const visibleAliases = aliases.filter(
    (a) => !optimisticallyRemoved.has(a),
  );

  if (visibleAliases.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-1.5">
      {visibleAliases.map((alias) => (
        <Badge key={alias} variant="secondary" className="gap-1 pr-1">
          {alias}
          <button
            type="button"
            className="ml-0.5 rounded-full p-0.5 hover:bg-foreground/10"
            onClick={() => removeAlias(alias)}
            aria-label={`Remove alias ${alias}`}
          >
            <XIcon className="size-3" />
          </button>
        </Badge>
      ))}
    </div>
  );
}
