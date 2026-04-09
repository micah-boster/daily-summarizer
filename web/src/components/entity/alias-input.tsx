"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useQueryClient, useMutation, useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { apiMutate, apiFetch } from "@/lib/api";
import { Input } from "@/components/ui/input";

interface AliasInputProps {
  entityId: string;
  existingAliases: string[];
}

export function AliasInput({ entityId, existingAliases }: AliasInputProps) {
  const queryClient = useQueryClient();
  const [value, setValue] = useState("");
  const [error, setError] = useState("");
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Fetch unmatched mentions for autocomplete
  const { data: unmatchedMentions } = useQuery<string[]>({
    queryKey: ["unmatched-mentions"],
    queryFn: () =>
      apiFetch<string[]>("/entities/unmatched-mentions").catch(() => []),
    staleTime: 60 * 1000,
  });

  const suggestions = (unmatchedMentions ?? []).filter(
    (m) =>
      m.toLowerCase().includes(value.toLowerCase()) &&
      !existingAliases.includes(m) &&
      value.length > 0,
  );

  const addAlias = useMutation({
    mutationFn: async (alias: string) => {
      return apiMutate(`/entities/${entityId}/aliases`, {
        method: "POST",
        body: { alias },
      });
    },
    onSuccess: () => {
      setValue("");
      setError("");
      setShowSuggestions(false);
      queryClient.invalidateQueries({
        queryKey: ["entity-view", entityId],
      });
      queryClient.invalidateQueries({ queryKey: ["unmatched-mentions"] });
    },
    onError: (err: Error) => {
      const msg = err.message || "Failed to add alias";
      // 409 conflict means duplicate
      if (msg.toLowerCase().includes("already") || msg.includes("409")) {
        setError(msg);
      } else {
        setError(msg);
      }
    },
  });

  const submitAlias = useCallback(
    (alias: string) => {
      const trimmed = alias.trim();
      if (!trimmed) return;
      if (existingAliases.includes(trimmed)) {
        setError(`"${trimmed}" is already an alias for this entity`);
        return;
      }
      setError("");
      addAlias.mutate(trimmed);
    },
    [existingAliases, addAlias],
  );

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Escape") {
      setValue("");
      setShowSuggestions(false);
      setError("");
      return;
    }

    if (e.key === "Tab" && showSuggestions && suggestions.length > 0) {
      e.preventDefault();
      submitAlias(suggestions[selectedIndex]);
      return;
    }

    if (e.key === "ArrowDown" && showSuggestions) {
      e.preventDefault();
      setSelectedIndex((i) => Math.min(i + 1, suggestions.length - 1));
      return;
    }

    if (e.key === "ArrowUp" && showSuggestions) {
      e.preventDefault();
      setSelectedIndex((i) => Math.max(i - 1, 0));
      return;
    }

    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      if (showSuggestions && suggestions.length > 0) {
        submitAlias(suggestions[selectedIndex]);
      } else {
        submitAlias(value);
      }
    }
  }

  // Close suggestions on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (
        containerRef.current &&
        !containerRef.current.contains(e.target as Node)
      ) {
        setShowSuggestions(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  // Reset selected index when suggestions change
  useEffect(() => {
    setSelectedIndex(0);
  }, [suggestions.length]);

  return (
    <div ref={containerRef} className="relative">
      <Input
        ref={inputRef}
        placeholder="Type to add alias..."
        value={value}
        onChange={(e) => {
          setValue(e.target.value);
          setShowSuggestions(true);
          if (error) setError("");
        }}
        onFocus={() => setShowSuggestions(true)}
        onKeyDown={handleKeyDown}
        className="h-7 text-xs"
        disabled={addAlias.isPending}
        aria-invalid={!!error}
      />

      {error && <p className="mt-1 text-xs text-destructive">{error}</p>}

      {showSuggestions && suggestions.length > 0 && (
        <div className="absolute top-full left-0 z-50 mt-1 w-full rounded-lg border bg-popover p-1 shadow-md">
          {suggestions.slice(0, 8).map((s, i) => (
            <button
              key={s}
              type="button"
              className={`w-full rounded-md px-2 py-1 text-left text-xs ${
                i === selectedIndex
                  ? "bg-accent text-accent-foreground"
                  : "hover:bg-muted"
              }`}
              onMouseDown={(e) => {
                e.preventDefault();
                submitAlias(s);
              }}
              onMouseEnter={() => setSelectedIndex(i)}
            >
              {s}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
