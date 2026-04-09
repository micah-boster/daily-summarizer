"use client";

import { useState, useEffect } from "react";
import { useQueryClient, useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { apiMutate } from "@/lib/api";
import { useUIStore } from "@/stores/ui-store";
import { useEntityScopedView } from "@/hooks/use-entities";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader2Icon } from "lucide-react";

export function EntityDeleteDialog() {
  const queryClient = useQueryClient();

  const open = useUIStore((s) => s.deleteDialogOpen);
  const entityId = useUIStore((s) => s.deleteDialogEntityId);
  const closeDeleteDialog = useUIStore((s) => s.closeDeleteDialog);
  const selectEntity = useUIStore((s) => s.selectEntity);

  const { data: entityData } = useEntityScopedView(entityId);

  const [confirmText, setConfirmText] = useState("");
  const [apiError, setApiError] = useState("");

  const entityName = entityData?.entity_name ?? "";

  useEffect(() => {
    setConfirmText("");
    setApiError("");
  }, [open]);

  const mutation = useMutation({
    mutationFn: async () => {
      return apiMutate<void>(`/entities/${entityId}`, {
        method: "DELETE",
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["entities"] });
      queryClient.invalidateQueries({ queryKey: ["entity-view"] });
      toast.success(`Deleted "${entityName}"`);
      closeDeleteDialog();
      selectEntity(null);
    },
    onError: (err: Error) => {
      setApiError(err.message || "Failed to delete entity");
    },
  });

  const canDelete = confirmText === entityName && entityName.length > 0;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canDelete) return;
    setApiError("");
    mutation.mutate();
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(nextOpen) => {
        if (!nextOpen) closeDeleteDialog();
      }}
    >
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Delete {entityName}?</DialogTitle>
          <DialogDescription>
            This will soft-delete the entity and all its aliases. This action
            can be reversed by an administrator.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="confirm-delete">
              Type <span className="font-semibold">{entityName}</span> to
              confirm
            </Label>
            <Input
              id="confirm-delete"
              placeholder={entityName}
              value={confirmText}
              onChange={(e) => setConfirmText(e.target.value)}
              autoComplete="off"
            />
          </div>

          {apiError && (
            <p className="text-xs text-destructive">{apiError}</p>
          )}

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={closeDeleteDialog}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="destructive"
              disabled={!canDelete || mutation.isPending}
            >
              {mutation.isPending && (
                <Loader2Icon className="mr-1.5 size-4 animate-spin" />
              )}
              Delete Entity
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
