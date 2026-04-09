import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { apiFetch, API_BASE } from "@/lib/api";

const STALE_TIME = 5 * 60 * 1000; // 5 minutes

export interface ConfigValidationError {
  field: string;
  message: string;
}

export interface ConfigErrorResponse {
  detail: string;
  errors?: ConfigValidationError[];
}

/** Custom error that carries structured validation errors from the API. */
class ConfigMutationError extends Error {
  fieldErrors: ConfigValidationError[];
  constructor(message: string, fieldErrors: ConfigValidationError[] = []) {
    super(message);
    this.name = "ConfigMutationError";
    this.fieldErrors = fieldErrors;
  }
}

export function useConfig() {
  return useQuery<Record<string, unknown>>({
    queryKey: ["config"],
    queryFn: () => apiFetch<Record<string, unknown>>("/config"),
    staleTime: STALE_TIME,
  });
}

export function useUpdateConfig(options?: {
  onFieldErrors?: (errors: ConfigValidationError[]) => void;
}) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: Record<string, unknown>) => {
      const res = await fetch(`${API_BASE}/config`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });

      if (!res.ok) {
        const body = (await res.json().catch(() => ({
          detail: `HTTP ${res.status}`,
        }))) as ConfigErrorResponse;
        throw new ConfigMutationError(
          body.detail || `API error: ${res.status}`,
          body.errors ?? [],
        );
      }

      return (await res.json()) as Record<string, unknown>;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["config"] });
      toast.success("Configuration saved");
    },
    onError: (err: Error) => {
      if (
        err instanceof ConfigMutationError &&
        err.fieldErrors.length > 0 &&
        options?.onFieldErrors
      ) {
        options.onFieldErrors(err.fieldErrors);
        toast.error("Validation errors - check highlighted fields");
        return;
      }
      toast.error(err.message || "Failed to save configuration");
    },
  });
}
