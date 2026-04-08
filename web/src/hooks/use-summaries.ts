import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type {
  SummaryListItem,
  SummaryResponse,
  StatusResponse,
  WeeklyRollupListItem,
  WeeklyRollupResponse,
  MonthlyRollupListItem,
  MonthlyRollupResponse,
} from "@/lib/types";

const STALE_TIME = 5 * 60 * 1000; // 5 minutes

export function useSummaryList() {
  return useQuery<SummaryListItem[]>({
    queryKey: ["summaries"],
    queryFn: () => apiFetch<SummaryListItem[]>("/summaries"),
    staleTime: STALE_TIME,
  });
}

export function useSummary(date: string | null) {
  return useQuery<SummaryResponse>({
    queryKey: ["summary", date],
    queryFn: () => apiFetch<SummaryResponse>(`/summaries/${date}`),
    enabled: !!date,
    staleTime: STALE_TIME,
  });
}

export function useWeeklyList() {
  return useQuery<WeeklyRollupListItem[]>({
    queryKey: ["weekly-rollups"],
    queryFn: () => apiFetch<WeeklyRollupListItem[]>("/summaries/weekly"),
    staleTime: STALE_TIME,
  });
}

export function useWeeklyRollup(year: number | null, week: number | null) {
  return useQuery<WeeklyRollupResponse>({
    queryKey: ["weekly-rollup", year, week],
    queryFn: () =>
      apiFetch<WeeklyRollupResponse>(`/summaries/weekly/${year}/${week}`),
    enabled: year !== null && week !== null,
    staleTime: STALE_TIME,
  });
}

export function useMonthlyList() {
  return useQuery<MonthlyRollupListItem[]>({
    queryKey: ["monthly-rollups"],
    queryFn: () => apiFetch<MonthlyRollupListItem[]>("/summaries/monthly"),
    staleTime: STALE_TIME,
  });
}

export function useMonthlyRollup(year: number | null, month: number | null) {
  return useQuery<MonthlyRollupResponse>({
    queryKey: ["monthly-rollup", year, month],
    queryFn: () =>
      apiFetch<MonthlyRollupResponse>(`/summaries/monthly/${year}/${month}`),
    enabled: year !== null && month !== null,
    staleTime: STALE_TIME,
  });
}

export function useStatus() {
  return useQuery<StatusResponse>({
    queryKey: ["status"],
    queryFn: () => apiFetch<StatusResponse>("/status"),
    staleTime: STALE_TIME,
  });
}
