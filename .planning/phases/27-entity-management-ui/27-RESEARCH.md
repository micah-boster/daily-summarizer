# Phase 27: Entity Management UI - Research

**Researched:** 2026-04-08
**Domain:** CRUD forms, merge review UI, command palette, alias management
**Confidence:** HIGH

## Summary

Phase 27 adds write operations to the existing entity browsing UI (Phase 26). The backend already has full CRUD (`EntityRepository.add_entity`, `remove_entity`), alias management (`add_alias`, `remove_alias`, `list_aliases`), and merge proposal infrastructure (`merger.py` with `generate_proposals`, `score_pair`, `save_proposal`, `update_proposal_status`). The work is primarily frontend: slide-over create/edit forms, merge review cards, alias chip management, and a command palette -- plus new API endpoints to expose the existing repository write methods.

The existing stack (Next.js 15, shadcn-ui, Zustand, TanStack Query) is well-suited. shadcn-ui provides Dialog/Sheet, Input, Select, Badge, Command components that map directly to requirements. TanStack Query's `useMutation` handles optimistic updates and cache invalidation for write operations.

**Primary recommendation:** Build API endpoints first (POST/PUT/DELETE for entities, aliases, merge proposals), then layer frontend components using shadcn-ui Sheet for forms, shadcn-ui Command for the palette, and custom chip components for aliases.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Slide-over panel from the right for create/edit forms -- keeps entity list visible for context
- Required fields: name and type only (person/partner/initiative). All other metadata optional at creation time
- Inline validation errors beneath each field (red text, standard form pattern)
- Delete confirmation requires typing entity name to confirm -- GitHub-style destructive action guard
- Side-by-side card layout showing both entities being considered for merge
- Each card displays: name, type, aliases, mention count, similarity score
- One-at-a-time review with auto-advance queue -- focus on careful review, not batch speed
- When approving a merge, user explicitly picks which entity name becomes primary; the other becomes an alias
- Chip/tag list below entity name with removable chips and type-to-add input at the end (Notion-style)
- Duplicate alias prevention: warn and block if alias already belongs to another entity, showing which entity owns it
- Alias removal is instant (click X) with temporary undo toast -- no confirmation dialog
- Alias input autocompletes from unmatched mentions (names that appeared in summaries but aren't linked to any entity)
- Command palette search scope: entities by name/alias, dates, and actions (create entity, run pipeline, etc.)
- Results grouped by type under headers: Entities, Dates, Actions -- with recency boost within each group
- On open (before typing): show recently visited entities and dates
- Prefix filters: `/` for actions, `@` for entities, `#` for dates

### Claude's Discretion
- Slide-over panel width and animation
- Exact form field ordering and spacing
- Merge review queue sorting (by similarity score, date, etc.)
- Command palette fuzzy matching algorithm
- Toast duration and positioning
- Loading states during entity writes

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ENT-03 | User can create, edit, and delete entities and their aliases from the browser | EntityRepository already has add_entity, remove_entity, add_alias, remove_alias. Need API endpoints + slide-over form UI + alias chips |
| ENT-04 | Merge proposal review UI with side-by-side comparison, similarity score, approve/reject | merger.py has generate_proposals, score_pair, update_proposal_status. Need API endpoints for pending proposals + review UI |
| NAV-05 | Command palette (Cmd+K) for keyboard-first entity search, date jump, and action triggers | shadcn-ui Command component (based on cmdk) provides the foundation. Need integration with entity search API + routing |
</phase_requirements>

## Standard Stack

### Core (already in project)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| shadcn-ui Sheet | latest | Slide-over panel for create/edit forms | Already in component system; matches "right panel" decision |
| shadcn-ui Command | latest | Command palette foundation (wraps cmdk) | Industry standard (Linear, Vercel, Raycast all use cmdk) |
| shadcn-ui Dialog | latest | Delete confirmation modal | Standard destructive action pattern |
| TanStack Query | 5.x | Mutations for entity writes, cache invalidation | Already used for reads; useMutation handles optimistic updates |
| Zustand | 5.x | UI state (panel open/close, selected entity, recent items) | Already used for entity navigation state |
| sonner | latest | Toast notifications for alias removal undo | Already installed (sonner.tsx in ui/) |

### New shadcn-ui Components Needed
| Component | Purpose |
|-----------|---------|
| Sheet | Slide-over panel (right side) |
| Command | Command palette (Cmd+K) |
| Dialog | Delete confirmation |
| Input | Form text fields |
| Select | Entity type dropdown |
| Label | Form field labels |
| Alert | Inline validation errors |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| cmdk | 1.x | Command palette engine (auto-included with shadcn Command) | Fuzzy search, keyboard navigation, grouped results |
| react-hot-toast / sonner | -- | Toast for undo actions | Already installed; use for alias removal undo |

## Architecture Patterns

### Recommended Component Structure
```
web/src/components/
├── entity/
│   ├── entity-form-panel.tsx      # Sheet slide-over with create/edit form
│   ├── entity-delete-dialog.tsx   # GitHub-style delete confirmation
│   ├── entity-header.tsx          # (exists) -- add edit/delete buttons
│   ├── entity-scoped-view.tsx     # (exists) -- integrate alias chips
│   ├── alias-chip-list.tsx        # Chip/tag list with add/remove
│   └── alias-input.tsx            # Autocomplete input for new aliases
├── merge/
│   ├── merge-review-panel.tsx     # Queue-based review UI
│   ├── merge-comparison-card.tsx  # Side-by-side entity card
│   └── merge-primary-picker.tsx   # Radio to pick primary name
├── command/
│   └── command-palette.tsx        # Cmd+K global command palette
└── ui/
    ├── sheet.tsx                  # (new) shadcn Sheet
    ├── command.tsx                # (new) shadcn Command
    ├── dialog.tsx                 # (new) shadcn Dialog
    ├── input.tsx                  # (new) shadcn Input
    ├── select.tsx                 # (new) shadcn Select
    └── label.tsx                  # (new) shadcn Label
```

### API Endpoint Structure
```
src/api/routers/entities.py (extend existing):
  POST   /entities              -- Create entity
  PUT    /entities/{id}         -- Update entity name/type/metadata
  DELETE /entities/{id}         -- Soft-delete entity
  POST   /entities/{id}/aliases -- Add alias
  DELETE /entities/{id}/aliases/{alias} -- Remove alias
  GET    /entities/unmatched-mentions   -- Names in summaries not linked to entities

src/api/routers/merge_proposals.py (new):
  GET    /merge-proposals       -- List pending proposals (with entity details)
  POST   /merge-proposals/{id}/approve -- Approve with primary_entity_id
  POST   /merge-proposals/{id}/reject  -- Reject proposal
```

### Pattern 1: Mutation with Optimistic Update
**What:** Use TanStack Query `useMutation` with `onMutate` for instant UI feedback and `onSettled` for cache invalidation.
**When to use:** All entity write operations (create, edit, delete, alias add/remove, merge approve/reject).
```typescript
const createEntity = useMutation({
  mutationFn: (data: CreateEntityPayload) =>
    apiMutate("/entities", { method: "POST", body: data }),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ["entities"] });
    toast.success("Entity created");
  },
  onError: (err) => {
    toast.error(err.message);
  },
});
```

### Pattern 2: Slide-over Form with Controlled State
**What:** shadcn Sheet component wrapping a form. Open state managed by Zustand. Form state managed by React useState (local, not global).
**When to use:** Create and edit entity forms.

### Pattern 3: Command Palette with Grouped Results
**What:** shadcn Command (cmdk) with CommandGroup for each result type. Global keyboard listener on Cmd+K.
**When to use:** The command palette that's always accessible.

### Anti-Patterns to Avoid
- **Don't use Dialog for the create/edit form:** User decided slide-over (Sheet), not modal. Sheet keeps entity list visible.
- **Don't batch merge reviews:** User wants one-at-a-time with auto-advance. No multi-select.
- **Don't use confirmation dialog for alias removal:** User wants instant removal with undo toast.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Slide-over panel | Custom animated div | shadcn Sheet | Handles focus trap, escape key, backdrop, animation |
| Command palette | Custom search modal | shadcn Command (cmdk) | Fuzzy search, keyboard nav, grouping, accessibility |
| Toast notifications | Custom toast system | sonner (already installed) | Action buttons for undo, auto-dismiss, stacking |
| Form validation | Custom validation logic | HTML5 + React state | Simple required fields; no need for form libraries |
| Fuzzy matching | Custom string matching | cmdk built-in | Already handles fuzzy filtering with ranking |

## Common Pitfalls

### Pitfall 1: SQLite Write Concurrency
**What goes wrong:** SQLITE_BUSY errors when entity writes conflict with pipeline reads.
**Why it happens:** SQLite only allows one writer at a time. Phase 24 set up `busy_timeout` but entity writes add new write paths.
**How to avoid:** Use `BEGIN IMMEDIATE` for entity writes (per roadmap pitfall warning). The existing `EntityRepository` uses `.commit()` after writes which is correct.
**Warning signs:** Intermittent 500 errors on POST/PUT/DELETE during pipeline runs.

### Pitfall 2: Stale Cache After Mutations
**What goes wrong:** Entity list shows old data after create/edit/delete.
**Why it happens:** TanStack Query cache not invalidated after mutation.
**How to avoid:** Every `useMutation` must call `queryClient.invalidateQueries({ queryKey: ["entities"] })` on success. Also invalidate the specific entity query for the scoped view.

### Pitfall 3: Command Palette Event Conflicts
**What goes wrong:** Cmd+K conflicts with browser find or other shortcuts.
**Why it happens:** Global keydown listener not properly scoped.
**How to avoid:** Only bind when no input/textarea is focused. Use `event.preventDefault()` and check `event.metaKey` (Mac) or `event.ctrlKey` (other).

### Pitfall 4: Alias Undo Race Condition
**What goes wrong:** User removes alias, hits undo, but server already deleted it.
**Why it happens:** Optimistic delete + async undo window.
**How to avoid:** Use optimistic removal in UI with delayed server call (2-3 second window). If undo clicked, cancel the pending request. Or: delete immediately on server, undo re-adds the alias via POST.

### Pitfall 5: Next.js API Patterns
**What goes wrong:** Using outdated Next.js patterns.
**Why it happens:** `web/AGENTS.md` warns: "This is NOT the Next.js you know."
**How to avoid:** Read `node_modules/next/dist/docs/` before writing any Next.js code. Check for deprecation notices. The frontend hits the FastAPI backend directly, so Next.js API routes are not involved.

## Code Examples

### Extending api.ts for Mutations
```typescript
// Add to web/src/lib/api.ts
export async function apiMutate<T>(
  path: string,
  options: { method: string; body?: unknown },
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: options.method,
    headers: { "Content-Type": "application/json" },
    ...(options.body ? { body: JSON.stringify(options.body) } : {}),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
    throw new Error(err.detail || `API error: ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}
```

### FastAPI Create Entity Endpoint
```python
@router.post("", response_model=EntityResponse, status_code=201)
def create_entity(
    payload: CreateEntityRequest,
    repo: EntityRepository = Depends(get_entity_repo),
) -> EntityResponse:
    entity = repo.add_entity(
        name=payload.name,
        entity_type=payload.entity_type,
    )
    return EntityResponse(entity_id=entity.id, name=entity.name, entity_type=str(entity.entity_type))
```

### shadcn Command Palette Pattern
```typescript
// Global keyboard listener
useEffect(() => {
  const down = (e: KeyboardEvent) => {
    if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      setOpen((prev) => !prev);
    }
  };
  document.addEventListener("keydown", down);
  return () => document.removeEventListener("keydown", down);
}, []);
```

## Open Questions

1. **Update entity endpoint scope**
   - What we know: Repository has `add_entity` but no generic `update_entity` method -- only `update_hubspot_id`
   - What's unclear: Need to add a general update method to EntityRepository
   - Recommendation: Add `update_entity(entity_id, name, entity_type)` method to repository

2. **Merge execution via API**
   - What we know: `merger.py` has `execute_merge()` function that handles mention reassignment, alias transfer
   - What's unclear: Whether approve endpoint should call `execute_merge` directly or just update status
   - Recommendation: Approve endpoint should both update proposal status AND execute the merge in one transaction

## Sources

### Primary (HIGH confidence)
- Codebase inspection: `src/entity/repository.py` -- full CRUD and alias methods exist
- Codebase inspection: `src/entity/merger.py` -- generate_proposals, score_pair, merge execution
- Codebase inspection: `src/api/routers/entities.py` -- existing read endpoints
- Codebase inspection: `web/src/lib/types.ts`, `api.ts`, `ui-store.ts` -- existing frontend patterns
- Codebase inspection: `web/src/components/ui/` -- sonner, badge, button, card already installed

### Secondary (MEDIUM confidence)
- shadcn-ui documentation for Sheet, Command, Dialog components
- cmdk library for command palette patterns
- TanStack Query documentation for useMutation patterns

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all libraries already in project or part of shadcn-ui
- Architecture: HIGH - extending existing patterns (repository, API router, React components)
- Pitfalls: HIGH - identified from codebase analysis and roadmap warnings

**Research date:** 2026-04-08
**Valid until:** 2026-05-08 (stable stack, no fast-moving dependencies)
