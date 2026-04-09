---
phase: 29-config-management-polish
verified: 2026-04-09T18:00:00Z
status: gaps_found
score: 16/20 must-haves verified
re_verification: false
gaps:
  - truth: "User can press j/k to navigate items in the focused column"
    status: failed
    reason: "The useKeyboardNav hook queries [data-kb-item] to find navigable items, but no component in the codebase applies the data-kb-item attribute to any list item. getItemsForColumn() always returns an empty NodeList, so j/k find zero items and navigation is a no-op."
    artifacts:
      - path: "web/src/hooks/use-keyboard-nav.ts"
        issue: "Queries [data-kb-column='X'] [data-kb-item] but no elements in the DOM have data-kb-item"
    missing:
      - "Apply data-kb-item attribute to navigable items in DateListItem, EntityList items, RunHistory items, and any other clickable list rows in the left/center/right columns"

  - truth: "Enter selects the focused item, Esc deselects or goes up a level"
    status: failed
    reason: "Enter key calls .click() on the element at focusedIndex in the data-kb-item NodeList. Since no items have data-kb-item, the NodeList is always empty and Enter never activates any item. The focus ring is also never applied."
    artifacts:
      - path: "web/src/hooks/use-keyboard-nav.ts"
        issue: "Enter handler: items[idx] is always undefined because NodeList is empty"
    missing:
      - "Same fix as j/k gap: apply data-kb-item to navigable list items so the DOM query returns results"

  - truth: "UX-02 status in REQUIREMENTS.md matches implementation"
    status: failed
    reason: "REQUIREMENTS.md traceability table marks UX-02 as Pending (line 114) despite the keyboard navigation hook, shortcut help, and store state all existing in the codebase. The status was not updated after Plan 03 execution."
    artifacts:
      - path: ".planning/REQUIREMENTS.md"
        issue: "Line 52 shows '- [ ] **UX-02**' (unchecked) and line 114 shows 'Pending'; should be Complete given the code exists (though partially wired)"
    missing:
      - "Update REQUIREMENTS.md UX-02 checkbox and traceability status -- but only after data-kb-item gap is closed, since j/k navigation is currently broken"

human_verification:
  - test: "Open app in browser, toggle dark mode, then open the config panel"
    expected: "Panel slides in from right, all 5 sections visible and collapsible, gear icon and theme toggle visible in status bar bottom-right"
    why_human: "Visual layout, animation quality, and mode-switch behavior cannot be verified programmatically"
  - test: "In light mode, navigate to a daily summary with content"
    expected: "Headings h2 are sticky, have bottom border, and are visually distinct from h3. Lists have breathing room. Code blocks have rounded borders. Typography feels rhythmic and readable."
    why_human: "Visual quality of typography is subjective and requires human judgment"
  - test: "Press ? key in the app"
    expected: "Keyboard shortcut help overlay opens with Navigation, Actions, and Column Focus groups. Each shortcut has a styled kbd element."
    why_human: "Dialog rendering and visual quality require human confirmation"
  - test: "Press r key when pipeline is not running"
    expected: "Toast notification appears: 'Starting pipeline run...' then success or error"
    why_human: "Toast behavior and pipeline trigger require runtime verification"
---

# Phase 29: Config Management Polish Verification Report

**Phase Goal:** The v3.0 feature set is complete and demo-quality -- config is manageable from the browser, the UI is dark-mode ready, keyboard-navigable, and visually polished
**Verified:** 2026-04-09T18:00:00Z
**Status:** gaps_found
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths

| #  | Truth | Status | Evidence |
|----|-------|--------|----------|
| 1  | User can open config panel from gear icon and see all settings grouped by section | VERIFIED | status-bar.tsx Settings button calls toggleConfigPanel(); config-panel.tsx renders 5 SECTIONS (Pipeline, Sources, Transcripts, Synthesis, Processing) as collapsible cards |
| 2  | User can edit config fields and see inline Pydantic validation errors | VERIFIED | config-panel.tsx maintains fieldErrors state; handleFieldErrors maps API errors to fields; red text rendered below errored fields |
| 3  | Save button disabled until form dirty; saving writes atomically with backup | VERIFIED | isDirty check + disabled prop on Save button; config.py does shutil.copy2 backup then tempfile + os.rename |
| 4  | Config panel is read-only with banner when pipeline run is active | VERIFIED | isLocked = pipelineStatus === "running"; amber banner rendered; fieldset disabled={isLocked} |
| 5  | App respects system dark/light preference on first load with no flash | VERIFIED | providers.tsx ThemeProvider with defaultTheme="system" enableSystem disableTransitionOnChange; layout.tsx has suppressHydrationWarning |
| 6  | User can manually toggle between System, Light, and Dark modes | VERIFIED | status-bar.tsx ThemeToggle cycles THEME_CYCLE array system->light->dark; mounted guard prevents hydration mismatch |
| 7  | Theme preference persists across browser sessions | VERIFIED | next-themes storageKey="theme" persists to localStorage |
| 8  | Toggle accessible in status bar bottom-right area | VERIFIED | ThemeToggle rendered in right side div of StatusBar alongside Settings button |
| 9  | User can press j/k to navigate items in the focused column | FAILED | useKeyboardNav queries [data-kb-item] but NO component applies this attribute. NodeList always empty -- j/k navigation is a no-op |
| 10 | User can press h/l to move focus between columns | VERIFIED | h/l key handlers call setFocusedColumn with COLUMN_ORDER array; app-shell.tsx has data-kb-column on all three columns |
| 11 | Enter selects the focused item, Esc deselects or goes up a level | FAILED | Enter calls .click() on items[idx] from [data-kb-item] NodeList which is always empty; Esc logic is correct but Enter is broken |
| 12 | Pressing ? opens keyboard shortcut help overlay | VERIFIED | shortcut-help.tsx Dialog controlled by shortcutHelpOpen store state; ? key calls toggleShortcutHelp() |
| 13 | Pressing r triggers pipeline run from anywhere | VERIFIED | r key handler calls apiMutate("/runs", { method: "POST" }) with toast.promise; checks pipelineStatus first |
| 14 | Keyboard shortcuts do not fire when typing in input/textarea/select | VERIFIED | isEditableElement() checks tagName + isContentEditable; handler returns early |
| 15 | Cmd+K command palette continues to work | VERIFIED | Handler checks e.metaKey or e.ctrlKey and returns early; command palette not intercepted |
| 16 | Summary markdown headings have clear visual hierarchy | VERIFIED | h1-h4 styled: xl/lg/base/sm font sizes with tracking-tight; h2 has border-b border-border |
| 17 | Lists have breathing room and consistent indentation | VERIFIED | ul/ol: space-y-1.5 mb-4 pl-5; li: pl-1 leading-relaxed |
| 18 | Code blocks and inline code have distinct styling in both modes | VERIFIED | inline: rounded-md bg-muted px-1.5 py-0.5 text-[13px] font-mono; pre: rounded-lg border border-border bg-muted/50 p-4 |
| 19 | Consistent spacing and alignment across all three columns | VERIFIED | app-shell.tsx adds border-r/border-l border-border to side columns; center has px-6 py-4 wrapper |
| 20 | Brand colors (green primary, gold accent, warm whites) visible | VERIFIED | globals.css :root has --primary: oklch(0.33 0.08 160) (dark green), --chart-1: oklch(0.73 0.14 85) (gold), --background: oklch(0.97 0.01 90) (warm white) |

**Score:** 17/20 truths verified (2 failed on data-kb-item wiring, 1 administrative/docs gap)

---

## Required Artifacts

### Plan 01 Artifacts (CFG-01, CFG-02, CFG-03)

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/api/routers/config.py` | GET /config and PUT /config endpoints | VERIFIED | 163 lines; router exported; GET redacts tokens; PUT validates via PipelineConfig, returns 422 with structured errors, writes atomically |
| `web/src/components/config/config-panel.tsx` | Slide-over config panel with grouped form sections | VERIFIED | 669 lines (well above 100 min); Sheet-based; 5 SECTIONS defined; renderField for text/number/bool/textarea |
| `web/src/hooks/use-config.ts` | TanStack Query hooks for config CRUD | VERIFIED | useConfig() + useUpdateConfig(); ConfigMutationError class for field-level error propagation |

### Plan 02 Artifacts (UX-01)

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `web/src/app/providers.tsx` | ThemeProvider wrapping the app | VERIFIED | ThemeProvider with attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange wraps QueryClientProvider |
| `web/src/app/layout.tsx` | suppressHydrationWarning on html element | VERIFIED | `<html ... suppressHydrationWarning>` present at line 30 |
| `web/src/app/globals.css` | Brand-colored CSS variables for :root and .dark | VERIFIED | :root has oklch brand colors; .dark block has dark mode palette; both use oklch |

### Plan 03 Artifacts (UX-02)

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `web/src/hooks/use-keyboard-nav.ts` | Global keyboard navigation hook | VERIFIED (exists, substantive) | 191 lines; h/l/?/r/Esc all wired; j/k/Enter PARTIALLY WIRED -- hook code correct but data-kb-item never applied to DOM |
| `web/src/components/keyboard/shortcut-help.tsx` | Keyboard shortcut help overlay modal | VERIFIED | 99 lines; Dialog with grouped shortcuts; Kbd styled component |

### Plan 04 Artifacts (UX-04)

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `web/src/app/globals.css` | .markdown-content scoped styles | VERIFIED | Lines 154-167: .markdown-content first/last child margin reset + nested list spacing |
| `web/src/components/summary/markdown-renderer.tsx` | Markdown typography with heading hierarchy | VERIFIED | 159 lines; h1-h4 hierarchy; ul/ol/li/blockquote/code/pre/a/hr/table/th/td all styled |

---

## Key Link Verification

### Plan 01 Key Links

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| config-panel.tsx | /api/v1/config | useConfig + useUpdateConfig | WIRED | config-panel.tsx imports useConfig, useUpdateConfig; mutation.mutate(formData) on save |
| config.py | src/config.py | PipelineConfig validation | WIRED | `from src.config import PipelineConfig, _format_validation_error, load_config`; PipelineConfig(**body) in PUT |
| status-bar.tsx | config-panel.tsx | gear icon triggers panel open | WIRED | toggleConfigPanel from useUIStore called in onClick; ConfigPanel mounted in providers.tsx |

### Plan 02 Key Links

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| providers.tsx | next-themes | ThemeProvider with attribute="class" | WIRED | `<ThemeProvider attribute="class" ...>` present |
| status-bar.tsx | next-themes | useTheme hook for toggle | WIRED | `import { useTheme } from "next-themes"` and `const { theme, setTheme } = useTheme()` in ThemeToggle |

### Plan 03 Key Links

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| use-keyboard-nav.ts | ui-store.ts | focusedColumn/focusedIndex state | WIRED | Hook reads/writes focusedColumn, focusedIndex, shortcutHelpOpen from useUIStore |
| use-keyboard-nav.ts | pipeline-store.ts | r key triggers pipeline run | WIRED | `usePipelineStore.getState().status` checked; apiMutate("/runs") called |
| app-shell.tsx | use-keyboard-nav.ts | Hook mounted in AppShell | WIRED | `useKeyboardNav()` called at top of AppShell component |
| use-keyboard-nav.ts | navigable list items | data-kb-item attribute | NOT WIRED | No component in the codebase applies data-kb-item; j/k/Enter navigation broken |

### Plan 04 Key Links

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| globals.css | all components | CSS variables consumed by Tailwind | WIRED | --primary, --background, --muted all defined; @theme inline maps to Tailwind color- utilities |
| markdown-renderer.tsx | globals.css | Tailwind classes referencing CSS vars | WIRED | text-primary, bg-muted, border-border used throughout component |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| CFG-01 | Plan 01 | User can view current pipeline config in the browser | SATISFIED | GET /config endpoint returns full config; config-panel.tsx displays all sections |
| CFG-02 | Plan 01 | User can edit config with Pydantic validation, structured errors | SATISFIED | PUT /config validates via PipelineConfig; 422 returns {detail, errors[]}; inline field errors in panel |
| CFG-03 | Plan 01 | Config writes atomic (temp file + rename) with backup | SATISFIED | config.py: shutil.copy2 backup then tempfile.mkstemp + os.rename |
| UX-01 | Plan 02 | Dark mode with system preference detection and manual toggle | SATISFIED | ThemeProvider, suppressHydrationWarning, three-state toggle -- all implemented |
| UX-02 | Plan 03 | Keyboard navigation j/k/h/l/Enter/Esc across three columns | PARTIALLY SATISFIED | h/l column switching, ?/r/Esc, input guard -- all work. j/k/Enter broken: data-kb-item never applied to list items |
| UX-04 | Plan 04 | Design quality demo-presentable -- typography, spacing, visual hierarchy | SATISFIED (code) | markdown-renderer.tsx fully overhauled; globals.css .markdown-content scoped; app-shell borders added -- NEEDS HUMAN visual confirmation |

### REQUIREMENTS.md Tracking Discrepancy

The REQUIREMENTS.md traceability table has inconsistencies after Phase 29 execution:
- **CFG-01, CFG-02, CFG-03**: Listed as "Pending" (line 110-112) but implemented -- SHOULD be "Complete"
- **UX-02**: Listed as "Pending" (line 114) -- CORRECTLY reflects partial implementation (j/k broken)
- **UX-01**: Shows "Complete" -- correct
- **UX-04**: Shows "Complete" -- correct

The checkboxes in the requirements section (lines 45-54) reflect the same stale state for CFG-01, CFG-02, CFG-03 (still unchecked `[ ]`).

---

## Anti-Patterns Found

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| `web/src/hooks/use-keyboard-nav.ts` | Queries `[data-kb-item]` which is never set in DOM | BLOCKER | j/k traversal, Enter selection, and focus ring are all non-functional |
| `.planning/REQUIREMENTS.md` | CFG-01/02/03 checkboxes still `[ ]` despite implementation | WARNING | Tracking inconsistency; misleading status |
| `.planning/phases/29-config-management-polish/` | No 29-03-SUMMARY.md exists | INFO | Plan 03 (UX-02 keyboard nav) completed without summary file |

---

## Human Verification Required

### 1. Config Panel Visual Quality

**Test:** Start dev server, click gear icon in status bar
**Expected:** Panel slides in from right at 540px width, all 5 sections visible and collapsible, pipeline lock banner shows amber when run is active
**Why human:** Animation quality, panel width rendering, and amber banner visibility require visual confirmation

### 2. Dark Mode Toggle and Brand Colors

**Test:** Click the Monitor/Sun/Moon icon in status bar bottom-right to cycle through themes
**Expected:** App transitions between warm-white light mode (green primary buttons, gold chart colors) and dark mode (neutral dark background, light green primary). No flash on page reload in dark mode.
**Why human:** Color rendering, contrast ratios, and flash-of-wrong-theme require runtime browser testing

### 3. Markdown Typography

**Test:** Navigate to a daily summary with headings, lists, code, and blockquotes
**Expected:** h2 headings are sticky and have a bottom border. Lists have visible spacing between items. Code blocks have a border and rounded corners. Blockquotes have a green left border with subtle green background.
**Why human:** Typography quality and visual rhythm require human judgment

### 4. ? Key Shortcut Help

**Test:** Press ? key with no input focused
**Expected:** Dialog opens with "Keyboard Shortcuts" title, showing Navigation, Actions, and Column Focus groups. Each key shown in a styled kbd element. Esc closes the dialog.
**Why human:** Dialog appearance and styled kbd elements require visual confirmation

---

## Gaps Summary

**Critical gap: data-kb-item attribute never applied to any list items.**

The keyboard navigation hook (`use-keyboard-nav.ts`) implements a DOM-query strategy: it finds navigable items by querying `[data-kb-column="X"] [data-kb-item]`. The three column wrappers correctly have `data-kb-column` attributes (in `app-shell.tsx`). However, no component in the entire codebase applies the `data-kb-item` attribute to any list element.

This means:
- `getItemsForColumn()` always returns an empty NodeList
- `j` key: `maxIdx < 0` guard triggers immediately, nothing happens
- `k` key: `idx <= 0` resets to 0, but no item to highlight
- `Enter` key: `items[idx]` is `undefined`, `.click()` is never called
- `applyFocusRing()`: `target` is always `undefined`, no ring ever appears

The h/l column switching, ?, r, and Esc keys work correctly because they do not depend on data-kb-item.

**Fix required:** Apply `data-kb-item` attribute to clickable navigable rows in the left, center, and right columns -- specifically: date items in the summary list (DateListItem), entity items in the entity list (EntityList row components), and run history items (RunHistory rows).

**Documentation gap:** CFG-01, CFG-02, CFG-03 are fully implemented but remain marked as unchecked/Pending in REQUIREMENTS.md. These should be updated to reflect completion. UX-02 should remain Pending until the data-kb-item gap is closed.

---

_Verified: 2026-04-09T18:00:00Z_
_Verifier: Claude (gsd-verifier)_
