"use client";

import { useState, useEffect } from "react";
import { useQueryClient, useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { apiMutate } from "@/lib/api";
import { useUIStore } from "@/stores/ui-store";
import { useEntityScopedView } from "@/hooks/use-entities";
import type { EntityResponse } from "@/lib/types";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Loader2Icon } from "lucide-react";

const ENTITY_TYPES = [
  { value: "partner", label: "Partner" },
  { value: "person", label: "Person" },
  { value: "initiative", label: "Initiative" },
];

export function EntityFormPanel() {
  const queryClient = useQueryClient();

  const open = useUIStore((s) => s.formPanelOpen);
  const mode = useUIStore((s) => s.formPanelMode);
  const entityId = useUIStore((s) => s.formPanelEntityId);
  const closeFormPanel = useUIStore((s) => s.closeFormPanel);

  // Fetch entity data for edit mode
  const { data: entityData } = useEntityScopedView(
    mode === "edit" ? entityId : null,
  );

  const [name, setName] = useState("");
  const [entityType, setEntityType] = useState("");
  const [nameError, setNameError] = useState("");
  const [typeError, setTypeError] = useState("");
  const [apiError, setApiError] = useState("");

  // Pre-fill fields in edit mode
  useEffect(() => {
    if (mode === "edit" && entityData) {
      setName(entityData.entity_name);
      setEntityType(entityData.entity_type);
    } else if (mode === "create") {
      setName("");
      setEntityType("");
    }
    setNameError("");
    setTypeError("");
    setApiError("");
  }, [mode, entityData, open]);

  const mutation = useMutation({
    mutationFn: async () => {
      if (mode === "create") {
        return apiMutate<EntityResponse>("/entities", {
          method: "POST",
          body: { name: name.trim(), entity_type: entityType },
        });
      } else {
        return apiMutate<EntityResponse>(`/entities/${entityId}`, {
          method: "PUT",
          body: { name: name.trim(), entity_type: entityType },
        });
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["entities"] });
      queryClient.invalidateQueries({ queryKey: ["entity-view"] });
      toast.success(
        mode === "create" ? "Entity created" : "Entity updated",
      );
      closeFormPanel();
    },
    onError: (err: Error) => {
      setApiError(err.message || "An error occurred");
    },
  });

  function validate(): boolean {
    let valid = true;
    if (!name.trim()) {
      setNameError("Name is required");
      valid = false;
    } else {
      setNameError("");
    }
    if (!entityType) {
      setTypeError("Type is required");
      valid = false;
    } else {
      setTypeError("");
    }
    return valid;
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setApiError("");
    if (!validate()) return;
    mutation.mutate();
  }

  return (
    <Sheet
      open={open}
      onOpenChange={(nextOpen) => {
        if (!nextOpen) closeFormPanel();
      }}
    >
      <SheetContent side="right" className="w-[400px] sm:max-w-[400px]">
        <SheetHeader>
          <SheetTitle>
            {mode === "create" ? "Create Entity" : "Edit Entity"}
          </SheetTitle>
          <SheetDescription>
            {mode === "create"
              ? "Add a new entity to track mentions and activity."
              : "Update entity name or type."}
          </SheetDescription>
        </SheetHeader>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4 px-4">
          <div className="space-y-1.5">
            <Label htmlFor="entity-name">Name</Label>
            <Input
              id="entity-name"
              placeholder="Entity name"
              value={name}
              onChange={(e) => {
                setName(e.target.value);
                if (nameError) setNameError("");
              }}
              onBlur={() => {
                if (!name.trim()) setNameError("Name is required");
              }}
              aria-invalid={!!nameError}
            />
            {nameError && (
              <p className="text-xs text-destructive">{nameError}</p>
            )}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="entity-type">Type</Label>
            <Select
              value={entityType}
              onValueChange={(val) => {
                setEntityType(val ?? "");
                if (typeError) setTypeError("");
              }}
            >
              <SelectTrigger
                className="w-full"
                aria-invalid={!!typeError}
              >
                <SelectValue placeholder="Select type" />
              </SelectTrigger>
              <SelectContent>
                {ENTITY_TYPES.map((t) => (
                  <SelectItem key={t.value} value={t.value}>
                    {t.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {typeError && (
              <p className="text-xs text-destructive">{typeError}</p>
            )}
          </div>

          {apiError && (
            <p className="text-xs text-destructive">{apiError}</p>
          )}

          <Button
            type="submit"
            disabled={mutation.isPending}
            className="mt-2"
          >
            {mutation.isPending && (
              <Loader2Icon className="mr-1.5 size-4 animate-spin" />
            )}
            {mode === "create" ? "Create Entity" : "Save Changes"}
          </Button>
        </form>
      </SheetContent>
    </Sheet>
  );
}
