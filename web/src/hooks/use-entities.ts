import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type {
  EntityListItem,
  EntityScopedViewResponse,
  RelatedEntityItem,
} from "@/lib/types";

const STALE_TIME = 5 * 60 * 1000; // 5 minutes

export function useEntityList(type?: string | null, sort?: string) {
  const params = new URLSearchParams();
  if (type) params.set("type", type);
  if (sort) params.set("sort", sort);
  const qs = params.toString();

  return useQuery<EntityListItem[]>({
    queryKey: ["entities", type ?? null, sort ?? "activity"],
    queryFn: () =>
      apiFetch<EntityListItem[]>(`/entities${qs ? `?${qs}` : ""}`),
    staleTime: STALE_TIME,
  });
}

export function useEntityScopedView(entityId: string | null) {
  return useQuery<EntityScopedViewResponse>({
    queryKey: ["entity-view", entityId],
    queryFn: () =>
      apiFetch<EntityScopedViewResponse>(`/entities/${entityId}`),
    enabled: !!entityId,
    staleTime: STALE_TIME,
  });
}

export function useRelatedEntities(entityId: string | null) {
  return useQuery<RelatedEntityItem[]>({
    queryKey: ["entity-related", entityId],
    queryFn: () =>
      apiFetch<RelatedEntityItem[]>(`/entities/${entityId}/related`),
    enabled: !!entityId,
    staleTime: STALE_TIME,
  });
}
