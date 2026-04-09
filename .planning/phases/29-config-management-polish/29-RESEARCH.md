# Phase 29: Config Management + Polish - Research

**Researched:** 2026-04-09
**Domain:** Config management UI, dark mode theming, keyboard navigation, visual polish
**Confidence:** HIGH

## Summary

Phase 29 completes the v3.0 feature set with four workstreams: (1) a config viewer/editor backed by the existing Pydantic `PipelineConfig` model, (2) dark mode via `next-themes` (already installed, not yet wired), (3) vim-style keyboard navigation across the three-column layout, and (4) a comprehensive visual polish pass applying Bounce AI brand colors and Linear-style aesthetic.

The existing codebase provides strong foundations: `src/config.py` has a fully-validated `PipelineConfig` with `extra="forbid"`, field validators, and formatted error messages. The frontend uses shadcn/ui with Tailwind v4 CSS variables (oklch color space), Zustand for state, and TanStack Query for data fetching. `next-themes` v0.4.6 is already in `package.json` but not integrated. The `StatusBar` component (fixed bottom bar) is the natural home for the theme toggle and already has pipeline state wired.

**Primary recommendation:** Build the config API first (read-only, then write with validation), then dark mode (foundational for polish), then keyboard nav, then the visual polish pass last (so all UI changes are in place before the final sweep).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Config viewer/editor: Structured form layout with grouped sections, labeled fields, toggles, dropdowns. Lives in a slide-over panel from gear icon (not a nav tab). Inline validation errors below fields with Pydantic messages. Save disabled until valid. Block edits during active pipeline runs with banner. Atomic writes with backup.
- Dark mode: System preference detection + manual toggle. Three states: System / Light / Dark. Toggle in status bar (bottom right) with sun/moon icon. Use shadcn/ui dark theme tokens as base. Preference persisted via Zustand persist or localStorage.
- Keyboard navigation: Vim-style (j/k/h/l/Enter/Esc), disabled when input focused. `?` shows shortcut help overlay. Subtle highlight ring. `r` triggers pipeline run. Existing Cmd+K continues.
- Visual polish: Best-in-class quality bar. Linear-style clean aesthetic. Bounce AI brand colors (greens: #03532c, #006634, #0a6b39, #52b788; gold: #d4a017; warm whites: #faf6ee, #fff7e7; gray: #797979). Map brand colors to shadcn tokens for both modes. Markdown rendering overhaul with full typography treatment. Desktop-only.

### Claude's Discretion
- Exact spacing values and typography scale
- How to structure config form sections (field grouping)
- Loading/saving animation for config panel
- Dark mode color adjustments for charts or data-heavy views
- Order and grouping of keyboard shortcuts in help overlay

### Deferred Ideas (OUT OF SCOPE)
None
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CFG-01 | User can view current pipeline config in browser | Config GET API endpoint + PipelineConfig.model_dump() serialization + slide-over panel with grouped form sections |
| CFG-02 | User can edit config with Pydantic validation, invalid configs rejected with structured errors | Config PUT endpoint with PipelineConfig(**data) validation + _format_validation_error() for structured error messages + inline field errors in UI |
| CFG-03 | Config writes are atomic (temp file + rename) with backup of previous version | Python tempfile + os.rename pattern + shutil.copy2 for backup + reject writes during active runs |
| UX-01 | Dark mode with system preference detection and manual toggle | next-themes ThemeProvider (already installed) + oklch CSS variable override + 3-state toggle in StatusBar |
| UX-02 | Keyboard navigation across all three columns | Global keydown listener with focus management + column focus state in Zustand + input-aware disable logic |
| UX-04 | Demo-presentable design quality | Brand color mapping to shadcn CSS variables + markdown typography overhaul + spacing/alignment audit |
</phase_requirements>

## Standard Stack

### Core (Already Installed)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| next-themes | ^0.4.6 | Dark mode with system detection | Already in package.json, standard Next.js dark mode solution |
| shadcn/ui | ^4.2.0 | Component library with CSS variable theming | Already the UI foundation, dark mode built-in via `.dark` class |
| Tailwind CSS | ^4 | Utility-first CSS with oklch color space | Already configured with `@custom-variant dark` |
| Zustand | ^5.0.12 | State management with persist middleware | Already used for UI state, keyboard focus state fits naturally |
| TanStack Query | ^5.96.2 | Server state management | Already used for all API calls |
| lucide-react | ^1.7.0 | Icons (Sun, Moon, Settings, Keyboard) | Already installed |
| react-markdown | ^10.1.0 | Markdown rendering (typography overhaul target) | Already in use |
| sonner | ^2.0.7 | Toast notifications for config save feedback | Already in use |

### No New Dependencies Needed
The existing stack covers all requirements. `next-themes` handles dark mode. `shadcn/ui` Sheet component handles the slide-over panel. Zustand handles keyboard focus state. No new libraries required.

## Architecture Patterns

### Backend: Config API Endpoints

Two new endpoints on the existing FastAPI router pattern:

```python
# src/api/routers/config.py
from fastapi import APIRouter, HTTPException
from src.config import PipelineConfig, load_config, _format_validation_error
from pydantic import ValidationError

router = APIRouter(tags=["config"])

@router.get("/config")
def get_config():
    """Return current config as JSON. Sensitive fields (tokens) redacted."""
    config = load_config()
    return config.model_dump()

@router.put("/config")
def update_config(body: dict):
    """Validate and write config. Returns 409 if pipeline running, 422 if invalid."""
    # Check pipeline lock
    # Validate through PipelineConfig
    # Atomic write with backup
    pass
```

**Key pattern: PipelineConfig already does all validation.** The `extra="forbid"` on every sub-model means unknown keys are rejected. Field validators enforce constraints. `_format_validation_error()` produces human-readable messages. The API just needs to catch `ValidationError` and return structured errors.

### Backend: Atomic Write Pattern

```python
import shutil
import tempfile
import yaml
from pathlib import Path

def atomic_config_write(config_path: Path, new_data: dict) -> None:
    """Write config atomically: backup existing, write to temp, rename."""
    # 1. Backup current
    if config_path.exists():
        backup = config_path.with_suffix('.yaml.bak')
        shutil.copy2(config_path, backup)

    # 2. Write to temp file in same directory (same filesystem for rename)
    fd, tmp_path = tempfile.mkstemp(
        dir=config_path.parent, suffix='.yaml.tmp'
    )
    try:
        with os.fdopen(fd, 'w') as f:
            yaml.safe_dump(new_data, f, default_flow_style=False)
        os.rename(tmp_path, config_path)  # Atomic on POSIX
    except Exception:
        os.unlink(tmp_path)
        raise
```

### Backend: Pipeline Lock Check

The existing `pipeline_runner.py` uses `BEGIN EXCLUSIVE` on SQLite for run creation. To check if a run is active:

```python
def is_pipeline_running(db_path: str | None = None) -> bool:
    """Check if any pipeline run is currently in progress."""
    conn = _get_conn(db_path)
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM pipeline_runs WHERE status = 'running'"
        ).fetchone()
        return row[0] > 0
    finally:
        conn.close()
```

### Frontend: Config Panel as Sheet

Use the existing `Sheet` component (already installed, used for entity form panel at 400px). Config panel follows the same pattern:

```typescript
// Gear icon in StatusBar -> opens Sheet
// Sheet contains grouped form with sections matching PipelineConfig structure
// TanStack Query for GET /api/v1/config
// useMutation for PUT /api/v1/config with error handling
```

### Frontend: Config Form Section Grouping (Claude's Discretion)

Recommended grouping based on PipelineConfig structure:

1. **Pipeline Settings** -- timezone, output_dir
2. **Sources** -- calendars, slack (enabled + channels), google_docs (enabled + settings), hubspot (enabled + settings), notion (enabled + settings)
3. **Transcripts** -- gemini_drive, gemini patterns, gong patterns, matching, preprocessing
4. **Synthesis** -- model, token limits, concurrency
5. **Processing** -- dedup settings, entity settings, cache retention

Each source has an enable/disable toggle as the primary control, with detail fields shown only when enabled.

### Frontend: Dark Mode Integration

```typescript
// providers.tsx -- wrap with ThemeProvider
import { ThemeProvider } from "next-themes";

export function Providers({ children }) {
  return (
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
      <QueryClientProvider client={queryClient}>
        {children}
      </QueryClientProvider>
    </ThemeProvider>
  );
}
```

```typescript
// layout.tsx -- add suppressHydrationWarning to <html>
<html lang="en" suppressHydrationWarning className={...}>
```

The existing `globals.css` already has both `:root` and `.dark` CSS variable blocks. `next-themes` adds the `.dark` class to `<html>`, which the `@custom-variant dark` directive picks up automatically.

### Frontend: Three-State Theme Toggle

```typescript
// In StatusBar (bottom right)
import { useTheme } from "next-themes";
import { Sun, Moon, Monitor } from "lucide-react";

// Cycle: system -> light -> dark -> system
// Display resolved icon (sun/moon) with system indicator
```

### Frontend: Keyboard Navigation Architecture

**Global listener pattern:**

```typescript
// hooks/use-keyboard-nav.ts
// Single useEffect with document.addEventListener('keydown', handler)
// Checks document.activeElement -- skip if input/textarea/select/contenteditable
// Column focus state: 'left' | 'center' | 'right' tracked in Zustand
// Item index per column tracked in Zustand (ephemeral, not persisted)
```

**Column focus model:**
- `h` moves focus left, `l` moves focus right
- `j/k` navigate items within the focused column
- `Enter` activates/selects, `Esc` deselects/goes up a level
- `r` triggers pipeline run (calls same function as RunTrigger button)
- `?` toggles shortcut help overlay

**Focus indicator:** Add `data-kb-focused` attribute or ring class to focused item. Use `ring-2 ring-primary/50` for the subtle highlight ring.

### Frontend: Brand Color Mapping

Map Bounce AI hex colors to oklch for CSS variables:

| Brand Color | Hex | Purpose in Light Mode | Purpose in Dark Mode |
|-------------|-----|----------------------|---------------------|
| Dark green | #03532c | `--primary` | `--primary` (slightly lighter) |
| Mid green | #006634 | `--primary` hover states | -- |
| Light green | #52b788 | `--accent`, links | `--primary` |
| Gold | #d4a017 | `--chart-1`, status indicators, badges | Same, slightly brighter |
| Warm white | #faf6ee | `--background` | -- |
| Lighter warm | #fff7e7 | `--card`, `--muted` | -- |
| Gray | #797979 | `--muted-foreground` | -- |

Convert hex to oklch using CSS `oklch()` values:
- `#03532c` -> approximately `oklch(0.33 0.08 160)`
- `#52b788` -> approximately `oklch(0.68 0.12 160)`
- `#d4a017` -> approximately `oklch(0.73 0.14 85)`
- `#faf6ee` -> approximately `oklch(0.97 0.01 90)`
- `#fff7e7` -> approximately `oklch(0.98 0.02 90)`

**Note:** Exact oklch conversions should be verified at implementation time with a color converter. The above are estimates.

### Anti-Patterns to Avoid
- **Direct hex values in components:** Always use CSS variables / Tailwind tokens. Never hardcode `#03532c` in JSX.
- **Separate dark mode styles:** Never use inline conditional styles for dark mode. The CSS variable system handles it.
- **Global keyboard listener without cleanup:** Always return cleanup function from useEffect.
- **Config form as raw YAML editor:** User explicitly wants structured form, not a text area.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Dark mode detection | Custom matchMedia listener | next-themes (already installed) | Handles SSR hydration mismatch, localStorage persistence, system detection |
| Theme toggle persistence | Custom localStorage logic | next-themes storageKey | Built-in, handles edge cases |
| Slide-over panel | Custom absolute-positioned div | shadcn Sheet component | Already used for entity form, consistent behavior |
| Form validation display | Custom error parsing | PipelineConfig ValidationError + _format_validation_error() | Already exists in src/config.py, battle-tested |
| Atomic file writes | Manual file I/O | tempfile + os.rename pattern | POSIX atomic rename guarantee |
| Toast notifications | Custom notification system | sonner (already installed) | Already integrated in providers |
| oklch color conversion | Manual calculation | Online converter (oklch.com) or CSS `color-mix()` | One-time conversion, not runtime |

## Common Pitfalls

### Pitfall 1: Hydration Mismatch with Dark Mode
**What goes wrong:** Server renders light mode, client detects dark preference, flash of wrong theme.
**Why it happens:** Next.js SSR doesn't know the client's theme preference.
**How to avoid:** `next-themes` handles this with an inline script. Must add `suppressHydrationWarning` to `<html>`. Must NOT conditionally render theme-dependent content without `useTheme` mounted check.
**Warning signs:** React hydration error in console, flash of unstyled content on page load.

### Pitfall 2: Config Write During Pipeline Run
**What goes wrong:** Config changes mid-run cause inconsistent pipeline behavior.
**Why it happens:** Pipeline subprocess reads config at startup; changing config during run creates mismatch.
**How to avoid:** Check `pipeline_runs` table for active runs before allowing writes. Return 409 Conflict. Frontend disables form and shows banner.
**Warning signs:** User sees "Config locked" banner but can still edit (frontend-only lock without backend enforcement).

### Pitfall 3: Keyboard Events Captured in Input Fields
**What goes wrong:** Typing "j" in a text input navigates instead of inserting character.
**Why it happens:** Global keydown listener doesn't check if an input element is focused.
**How to avoid:** Check `document.activeElement?.tagName` -- skip handler for INPUT, TEXTAREA, SELECT, and elements with `contenteditable`. Also check if inside a dialog/modal.
**Warning signs:** Cannot type in config form fields when keyboard nav is active.

### Pitfall 4: Config Sensitive Fields Exposed
**What goes wrong:** API tokens (HubSpot access_token, Notion token) returned in GET response.
**Why it happens:** `model_dump()` includes all fields by default.
**How to avoid:** Redact sensitive fields in the GET response. On PUT, if token field is masked/empty, preserve the existing value rather than overwriting with the mask.
**Warning signs:** Tokens visible in browser network tab.

### Pitfall 5: oklch Color Conversion Inaccuracy
**What goes wrong:** Brand colors look wrong because hex-to-oklch conversion was estimated.
**Why it happens:** oklch is a perceptual color space; mental math conversion is unreliable.
**How to avoid:** Use a verified converter tool (oklch.com or browser devtools color picker) for each brand color. Test visually.
**Warning signs:** Colors look "off" compared to brand deck.

### Pitfall 6: Tailwind v4 CSS Variable Scope
**What goes wrong:** Custom CSS variables don't apply because they're in the wrong scope or format.
**Why it happens:** Tailwind v4 uses `@theme inline` and `@custom-variant` -- different from v3 `tailwind.config.js`.
**How to avoid:** Modify `:root` and `.dark` blocks in `globals.css` directly. The existing pattern shows how it works. Don't try to use `tailwind.config.js` (doesn't exist in this project).
**Warning signs:** Colors don't change between light/dark mode.

### Pitfall 7: Sheet Z-Index Conflict with StatusBar
**What goes wrong:** Config slide-over panel appears behind the StatusBar.
**Why it happens:** StatusBar is `z-50` fixed. Sheet default z-index may be lower.
**How to avoid:** Ensure Sheet overlay/content has z-index >= 50. Check shadcn Sheet defaults.
**Warning signs:** Bottom of config panel is clipped or hidden behind status bar.

## Code Examples

### PipelineConfig Serialization (Verified from src/config.py)

```python
# PipelineConfig has 11 top-level sections, each a Pydantic BaseModel
# All use extra="forbid" and have sensible defaults
# model_dump() returns a clean dict suitable for YAML serialization

config = load_config()
data = config.model_dump()
# data = {"pipeline": {"timezone": "America/New_York", ...}, "calendars": {...}, ...}

# Validation with error capture:
try:
    PipelineConfig(**raw_data)
except ValidationError as exc:
    formatted = _format_validation_error(exc)
    # Returns structured error with field paths and suggestions
```

### next-themes Integration (Verified from next-themes type definitions)

```typescript
// ThemeProvider props for three-state (system/light/dark):
<ThemeProvider
  attribute="class"          // Adds .dark class to <html>
  defaultTheme="system"      // Respects OS preference by default
  enableSystem={true}        // Enable system preference detection
  disableTransitionOnChange  // Prevent flash during theme switch
  storageKey="theme"         // localStorage key for persistence
>

// useTheme() hook:
const { theme, setTheme, resolvedTheme, systemTheme } = useTheme();
// theme: "system" | "light" | "dark" (what user selected)
// resolvedTheme: "light" | "dark" (actual applied theme)
// systemTheme: "light" | "dark" (OS preference)
```

### Existing CSS Variable Pattern (Verified from globals.css)

```css
/* Light mode */
:root {
  --primary: oklch(0.205 0 0);        /* Will become brand green */
  --background: oklch(1 0 0);          /* Will become warm white */
  --muted-foreground: oklch(0.556 0 0); /* Will become brand gray */
}

/* Dark mode */
.dark {
  --primary: oklch(0.922 0 0);        /* Will become light green */
  --background: oklch(0.145 0 0);      /* Dark surface */
}
```

### Sheet Component Pattern (Verified -- entity-form-panel.tsx uses Sheet)

```typescript
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";

// Opens from right side, 400px wide (entity form precedent)
// Config panel can use same pattern, possibly wider (500-600px)
<Sheet open={isOpen} onOpenChange={setIsOpen}>
  <SheetContent side="right" className="w-[500px] sm:w-[500px]">
    <SheetHeader>
      <SheetTitle>Pipeline Configuration</SheetTitle>
    </SheetHeader>
    {/* Form content */}
  </SheetContent>
</Sheet>
```

### Existing API Pattern (Verified from api.ts)

```typescript
// GET: apiFetch<T>(path)
// POST/PUT/DELETE: apiMutate<T>(path, { method, body })
// Both throw on non-2xx

// Config hooks would follow existing pattern:
// hooks/use-config.ts with useQuery + useMutation
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| tailwind.config.js themes | CSS variables in globals.css (@theme inline) | Tailwind v4 | Theme tokens live in CSS, not JS config |
| Manual dark mode class toggle | next-themes + class strategy | Standard since Next.js 13+ | Handles SSR, persistence, system detection |
| Separate color values per mode | oklch CSS variables with .dark override | Tailwind v4 | Single source of truth for theming |

## Open Questions

1. **Exact oklch values for brand colors**
   - What we know: Hex values from brand deck (#03532c, #52b788, #d4a017, #faf6ee, #fff7e7)
   - What's unclear: Precise oklch conversions (estimated above, need verification)
   - Recommendation: Use browser devtools or oklch.com to convert at implementation time. This is a 5-minute task per color.

2. **Config form field types for complex fields**
   - What we know: PipelineConfig has strings, ints, bools, lists of strings, floats with min/max
   - What's unclear: Best UI widget for list fields (e.g., `slack.channels`, `calendars.ids`) -- tags input vs textarea
   - Recommendation: Use a simple tags/chip input for short lists, textarea for pattern lists (regex). Claude's discretion area.

3. **Dark mode for warm white backgrounds**
   - What we know: Light mode uses warm whites (#faf6ee). Dark mode needs distinct dark surfaces.
   - What's unclear: Whether to maintain warm tint in dark mode or go neutral dark.
   - Recommendation: Go neutral dark (standard shadcn dark values work well). Warm tint is subtle in dark mode and can look muddy. Claude's discretion area.

## Sources

### Primary (HIGH confidence)
- `src/config.py` -- PipelineConfig model with all 11 sections, validators, error formatting
- `config/config.yaml` -- Actual config file structure (78 lines)
- `web/src/app/globals.css` -- Current CSS variable setup with `:root` and `.dark` blocks (oklch)
- `web/package.json` -- next-themes ^0.4.6 already installed
- `web/node_modules/next-themes/dist/index.d.ts` -- ThemeProvider API verified
- `web/src/stores/ui-store.ts` -- Zustand persist pattern for state management
- `web/src/stores/pipeline-store.ts` -- Pipeline status detection pattern
- `web/src/components/layout/status-bar.tsx` -- StatusBar layout (theme toggle location)
- `web/src/components/layout/app-shell.tsx` -- Three-column grid layout
- `web/src/lib/api.ts` -- apiFetch/apiMutate pattern
- `web/components.json` -- shadcn config (base-nova style, Tailwind v4 CSS variables)
- `src/api/routers/pipeline.py` -- Pipeline run management pattern
- `src/api/services/pipeline_runner.py` -- Pipeline lock mechanism (BEGIN EXCLUSIVE)

### Secondary (MEDIUM confidence)
- oklch color conversions -- estimated from hex values, need verification with a converter tool

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all libraries already installed and in use, no new dependencies
- Architecture: HIGH - follows established patterns from Phase 26-28 (Sheet panels, Zustand stores, API routes)
- Config API: HIGH - PipelineConfig already has complete validation, just needs API wrapping
- Dark mode: HIGH - next-themes is standard, already installed, CSS variables already structured
- Keyboard nav: MEDIUM - custom implementation needed, but pattern is well-understood
- Visual polish: MEDIUM - brand color oklch conversions need verification, typography is subjective
- Pitfalls: HIGH - identified from real codebase patterns (z-index, hydration, pipeline lock)

**Research date:** 2026-04-09
**Valid until:** 2026-05-09 (stable stack, no fast-moving dependencies)
