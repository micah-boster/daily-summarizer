# Phase 25: Next.js Scaffold + Summary View - Research

**Researched:** 2026-04-08
**Domain:** Next.js 16 + shadcn/ui dashboard with FastAPI backend
**Confidence:** HIGH

## Summary

Phase 25 builds the primary daily-use interface: a three-column layout where the user opens localhost:3000 and sees yesterday's summary with structured cards (decisions, commitments, substance) above rendered markdown. The left nav provides date-based navigation with Daily/Weekly/Monthly grouping, and the right sidebar shows summary metadata.

The project already has Next.js 16.2.3 scaffolded with React 19, shadcn/ui (base-nova style), Tailwind CSS 4, and Lucide icons. The FastAPI backend on :8000 serves summary data via `/api/v1/summaries` (list) and `/api/v1/summaries/{date}` (detail), but lacks roll-up endpoints for weekly/monthly data. The frontend needs TanStack Query for data fetching and Zustand for UI state (sidebar collapse, section collapse).

**Primary recommendation:** Build the three-column shell as a server component layout, all interactive panels as client components with TanStack Query for API calls, and add roll-up API endpoints before the frontend can display weekly/monthly summaries.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Structured cards (decisions, commitments, substance) render above the full markdown summary
- Cards are expanded by default but collapsible; collapse state persists per session
- Commitments display owner and deadline as inline colored badges/chips
- Markdown section renders clean by default; hovering over sentences reveals source attribution (source type, confidence)
- Empty structured sections are hidden
- Left nav shows a scrollable date list, most recent on top
- Navigation organized into grouped sections: "Daily", "Weekly", "Monthly" -- each section expandable
- Each date entry shows: date, meeting count, commitment count, and 1-2 top themes as tags
- Prev/next arrows skip to next available date; unavailable dates show empty state
- Calendar popover for jumping to specific date; dates with summaries highlighted
- Right sidebar shows summary metadata: sources used, meeting count, items extracted, pipeline run timestamp, quality indicators
- Both left nav and right sidebar are collapsible to thin icon rails (~48px), Linear/Notion style
- When sidebars collapsed, center panel caps at ~800-900px max-width and centers
- Desktop-first; set minimum viewport width, do NOT invest in responsive/mobile layout
- Sticky section headers in the markdown content area

### Claude's Discretion
- Loading skeleton design and animation style
- Exact spacing, typography, and color palette choices
- Error boundary visual treatment
- Toast notification positioning and timing
- Icon choices for source types and nav elements
- Exact sidebar icon rail icons

### Deferred Ideas (OUT OF SCOPE)
- Responsive/mobile layout -- deferred to Phase 29
- Entity data in right sidebar -- Phase 26 will add entity insights
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| NAV-01 | Three-column layout: entity nav (left), content panel (center), context sidebar (right) | CSS Grid layout with collapsible sidebars using Zustand state |
| SUM-01 | User can view daily summary (structured data + rendered markdown) for any available date | TanStack Query fetching from `/api/v1/summaries/{date}`, react-markdown for rendering |
| SUM-02 | User can navigate between dates (prev/next, date picker) with graceful handling of missing dates | Summary index from `/api/v1/summaries`, shadcn Calendar component for date picker |
| SUM-04 | Weekly and monthly roll-up summaries are browsable alongside daily summaries | Requires new API endpoints: `/api/v1/summaries/weekly` and `/api/v1/summaries/monthly` |
| UX-03 | Loading skeletons per panel, error boundaries per column, toast notifications for actions | shadcn Skeleton, React error boundaries, shadcn Sonner toast |
</phase_requirements>

## Standard Stack

### Core (already installed)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Next.js | 16.2.3 | React framework | Already scaffolded in web/ |
| React | 19.2.4 | UI library | Already installed |
| shadcn/ui | 4.2.0 (base-nova) | Component library | Already configured with components.json |
| Tailwind CSS | 4.x | Utility CSS | Already configured |
| Lucide React | 1.7.0 | Icons | Already installed |

### To Install
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| @tanstack/react-query | 5.x | Server state management | All API data fetching |
| zustand | 5.x | Client state management | Sidebar collapse state, section collapse persistence |
| react-markdown | 9.x | Markdown rendering | Summary markdown content |
| remark-gfm | 4.x | GFM markdown support | Tables, strikethrough in summaries |
| date-fns | 4.x | Date formatting/manipulation | Date display, week/month grouping |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| TanStack Query | SWR | TQ has better devtools, mutation support, and query invalidation |
| Zustand | Jotai | Zustand is simpler for this use case (few global state atoms) |
| react-markdown | MDX | MDX is overkill -- summaries are generated markdown, not authored content |

**Installation:**
```bash
cd web && pnpm add @tanstack/react-query zustand react-markdown remark-gfm date-fns
```

## Architecture Patterns

### Recommended Project Structure
```
web/src/
├── app/
│   ├── layout.tsx          # Root layout (server component - metadata, fonts, providers)
│   ├── page.tsx            # Main dashboard page (redirects to latest date)
│   ├── globals.css         # Tailwind + theme variables
│   └── providers.tsx       # Client-side providers (QueryClient, Toaster)
├── components/
│   ├── ui/                 # shadcn components (button.tsx already exists)
│   ├── layout/
│   │   ├── app-shell.tsx   # Three-column grid container
│   │   ├── left-nav.tsx    # Date navigation sidebar
│   │   ├── right-sidebar.tsx # Metadata sidebar
│   │   └── sidebar-rail.tsx  # Collapsed icon rail
│   ├── summary/
│   │   ├── summary-view.tsx    # Main summary display
│   │   ├── structured-cards.tsx # Decisions/commitments/substance cards
│   │   ├── markdown-renderer.tsx # Markdown with hover attribution
│   │   └── empty-state.tsx     # "No summary for this date"
│   └── nav/
│       ├── date-list.tsx       # Scrollable date entries with stats
│       ├── date-group.tsx      # Daily/Weekly/Monthly expandable group
│       └── date-picker.tsx     # Calendar popover
├── hooks/
│   ├── use-summaries.ts    # TanStack Query hooks for summary API
│   └── use-ui-state.ts     # Zustand store for UI state
├── lib/
│   ├── utils.ts            # Already exists (cn utility)
│   ├── api.ts              # API client base (fetch wrapper with base URL)
│   └── types.ts            # TypeScript types matching API response models
└── stores/
    └── ui-store.ts         # Zustand store definition
```

### Pattern 1: Server Component Layout Shell + Client Interactive Panels
**What:** RootLayout is a server component (metadata, fonts). All interactive content is client components.
**When to use:** Always -- per roadmap pitfall warning #9 (RSC misuse).
**Key:** The `providers.tsx` wraps children in QueryClientProvider and is marked `"use client"`.

### Pattern 2: TanStack Query for All API State
**What:** Every API call goes through useQuery/useMutation hooks. No raw useEffect+fetch.
**When to use:** All data fetching from FastAPI backend.
**Key patterns:**
- `useQuery({ queryKey: ['summaries'], queryFn: ... })` for summary list
- `useQuery({ queryKey: ['summary', date], queryFn: ... })` for individual summary
- `staleTime: 5 * 60 * 1000` -- summaries don't change often
- Prefetch adjacent dates for instant navigation

### Pattern 3: Zustand for UI-Only State
**What:** Sidebar collapse, section collapse states in Zustand with sessionStorage persistence.
**When to use:** Any state that affects layout but isn't from the API.
**Key:** `persist` middleware with `sessionStorage` for collapse states.

### Anti-Patterns to Avoid
- **RSC for interactive panels:** All summary viewing, navigation, and collapsible elements MUST be client components. Server components only for the static layout shell.
- **Prop drilling API data:** Use TanStack Query hooks directly in components that need data, not prop drilling from a parent.
- **useEffect for data fetching:** TanStack Query handles loading, error, refetch, and caching automatically.
- **Global CSS for component styles:** Use Tailwind utilities. Global CSS only for CSS variables and base resets.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Markdown rendering | Custom parser | react-markdown + remark-gfm | Edge cases with GFM tables, code blocks, links |
| Data fetching + caching | useEffect + useState | TanStack Query | Loading/error states, caching, deduplication, prefetching |
| Date formatting | Custom date logic | date-fns | Locale handling, relative dates, week boundaries |
| Toast notifications | Custom toast system | shadcn Sonner (sonner) | Animation, stacking, auto-dismiss, accessibility |
| Calendar picker | Custom date picker | shadcn Calendar component | Keyboard navigation, accessibility, date highlighting |
| Skeleton loading | Custom shimmer | shadcn Skeleton | Consistent animation, composable shapes |

**Key insight:** Every UI primitive (buttons, cards, skeleton, toast, calendar) should come from shadcn/ui. Only build custom components for domain-specific layouts (three-column shell, summary cards, date nav).

## Common Pitfalls

### Pitfall 1: RSC Misuse (Roadmap #9)
**What goes wrong:** Putting interactive elements in server components causes hydration mismatches or missing interactivity.
**Why it happens:** Next.js 16 defaults to server components. Easy to forget "use client".
**How to avoid:** Only layout.tsx and pure wrapper components are server components. Everything with onClick, useState, useQuery gets "use client".
**Warning signs:** Hydration mismatch errors, components not responding to clicks.

### Pitfall 2: Two Build Systems (Roadmap #15)
**What goes wrong:** Forgetting to start both FastAPI and Next.js dev servers.
**Why it happens:** Two separate processes needed.
**How to avoid:** `make dev` already uses concurrently to run both. Always use `make dev`.
**Warning signs:** CORS errors (API not running), blank page (Next.js not running).

### Pitfall 3: CORS Issues
**What goes wrong:** Browser blocks API requests from localhost:3000 to localhost:8000.
**Why it happens:** Different ports = different origins.
**How to avoid:** FastAPI already has CORS middleware configured for localhost:3000 (from Phase 24). Verify it's working.
**Warning signs:** Network errors in browser console mentioning CORS.

### Pitfall 4: Missing Roll-Up API Endpoints
**What goes wrong:** Frontend can't display weekly/monthly summaries because API doesn't serve them.
**Why it happens:** Phase 24 only built daily summary endpoints.
**How to avoid:** Add `/api/v1/summaries/weekly` and `/api/v1/summaries/monthly` endpoints in this phase. The backend models (WeeklySynthesis, MonthlySynthesis) exist in `src/models/rollups.py`. Need a reader service for weekly/monthly output files.
**Warning signs:** 404 errors when clicking Weekly/Monthly sections in nav.

### Pitfall 5: Large Bundle from Markdown Libraries
**What goes wrong:** react-markdown + remark plugins add significant JS bundle size.
**Why it happens:** Markdown parsing is complex.
**How to avoid:** Dynamic import the markdown renderer so it's code-split. Use `next/dynamic` with loading skeleton.
**Warning signs:** Slow initial page load, large JS chunks in network tab.

## Code Examples

### TanStack Query Provider Setup
```typescript
// web/src/app/providers.tsx
"use client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 5 * 60 * 1000,
        retry: 1,
      },
    },
  }));
  return (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  );
}
```

### API Client Base
```typescript
// web/src/lib/api.ts
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export async function apiFetch<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}
```

### Summary Query Hooks
```typescript
// web/src/hooks/use-summaries.ts
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";

export function useSummaryList() {
  return useQuery({
    queryKey: ["summaries"],
    queryFn: () => apiFetch<SummaryListItem[]>("/summaries"),
  });
}

export function useSummary(date: string) {
  return useQuery({
    queryKey: ["summary", date],
    queryFn: () => apiFetch<SummaryResponse>(`/summaries/${date}`),
    enabled: !!date,
  });
}
```

### Zustand UI Store with Session Persistence
```typescript
// web/src/stores/ui-store.ts
import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";

interface UIState {
  leftNavCollapsed: boolean;
  rightSidebarCollapsed: boolean;
  collapsedSections: Record<string, boolean>;
  toggleLeftNav: () => void;
  toggleRightSidebar: () => void;
  toggleSection: (id: string) => void;
}

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      leftNavCollapsed: false,
      rightSidebarCollapsed: false,
      collapsedSections: {},
      toggleLeftNav: () => set((s) => ({ leftNavCollapsed: !s.leftNavCollapsed })),
      toggleRightSidebar: () => set((s) => ({ rightSidebarCollapsed: !s.rightSidebarCollapsed })),
      toggleSection: (id) => set((s) => ({
        collapsedSections: { ...s.collapsedSections, [id]: !s.collapsedSections[id] },
      })),
    }),
    { name: "ui-state", storage: createJSONStorage(() => sessionStorage) }
  )
);
```

### Three-Column Grid Layout
```typescript
// Collapsible sidebar pattern with CSS Grid
// Left: 280px | 48px, Center: 1fr (max 900px centered), Right: 300px | 48px
<div className="grid h-screen" style={{
  gridTemplateColumns: `${leftCollapsed ? '48px' : '280px'} 1fr ${rightCollapsed ? '48px' : '300px'}`,
}}>
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Next.js pages/ router | App Router (app/) | Next.js 13+ | Already using app/ |
| getServerSideProps | Server Components | Next.js 13+ | Use client components for interactive content |
| CSS Modules | Tailwind CSS 4 | 2024+ | Already configured |
| custom fetch hooks | TanStack Query v5 | 2023+ | Better caching, devtools, TypeScript |
| Redux for UI state | Zustand | 2022+ | Simpler API, smaller bundle |
| shadcn v0 (radix) | shadcn v4 (base-ui) | 2025 | Uses @base-ui/react instead of @radix-ui |

**Important shadcn/ui note:** The project uses shadcn v4 with `base-nova` style which uses `@base-ui/react` (already in package.json) instead of the older `@radix-ui` primitives. When adding shadcn components, use the `pnpm dlx shadcn@latest add <component>` command which will pull the correct variant.

## Open Questions

1. **Roll-up file locations**
   - What we know: `src/models/rollups.py` has WeeklySynthesis and MonthlySynthesis models. `src/synthesis/weekly.py` and `src/synthesis/monthly.py` exist.
   - What's unclear: Where do weekly/monthly output files get written? No `output/weekly/` or `output/monthly/` directories exist.
   - Recommendation: Check `src/output/writer.py` for roll-up write paths. The API reader for roll-ups needs to know the file layout. If no roll-up files exist on disk, the nav sections will show empty states.

2. **Source attribution data in sidecar**
   - What we know: CONTEXT.md requires hover-to-reveal source attribution on markdown sentences.
   - What's unclear: The sidecar has `substance_entity_refs`, `decision_entity_refs`, `commitment_entity_refs` but no per-sentence attribution mapping.
   - Recommendation: For Phase 25, implement hover attribution only where sidecar data maps to structured sections (decisions, commitments, substance items). Full sentence-level attribution in markdown body may need a future enhancement.

## Sources

### Primary (HIGH confidence)
- Project codebase: `web/package.json`, `web/components.json`, `web/src/` -- actual installed versions and configuration
- Project codebase: `src/api/` -- actual API endpoints and response models
- Project codebase: `src/sidecar.py` -- actual structured data model
- Project codebase: `src/models/rollups.py` -- actual roll-up data models

### Secondary (MEDIUM confidence)
- TanStack Query v5 patterns -- well-established, stable API
- Zustand v5 patterns -- well-established, stable API
- react-markdown v9 -- stable, widely used

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all versions verified from package.json and npm
- Architecture: HIGH - patterns follow Next.js 16 App Router conventions
- Pitfalls: HIGH - roadmap explicitly calls out RSC misuse and two build systems

**Research date:** 2026-04-08
**Valid until:** 2026-05-08 (stable stack, low churn risk)
