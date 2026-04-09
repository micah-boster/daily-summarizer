# Phase 29: Config Management + Polish - Context

**Gathered:** 2026-04-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Complete the v3.0 feature set to demo-quality: browser-based config viewer/editor with Pydantic validation, dark mode with system detection, vim-style keyboard navigation, and comprehensive visual polish using Bounce AI brand colors. Desktop-only target.

</domain>

<decisions>
## Implementation Decisions

### Config viewer/editor
- Structured form layout — grouped sections (Sources, Channels, Priorities, etc.) with labeled fields, toggles, dropdowns. Feels like a settings page, not raw YAML.
- Lives in a slide-over panel triggered from a gear icon (status bar or header), not a nav tab.
- Inline validation errors — red text below each invalid field with Pydantic error message. Save button disabled until all fields valid.
- Block edits during active pipeline runs — show a banner "Config locked while pipeline is running" with all fields read-only.
- Atomic writes with backup of previous config version (per roadmap pitfall warning).

### Dark mode
- System preference detection + manual toggle. Three states: System / Light / Dark.
- Toggle lives in the status bar (bottom right) — sun/moon icon.
- Use shadcn/ui dark theme tokens as the base. No custom dark palette.
- Trust defaults for edge cases (markdown, code blocks, badges) — fix during polish if anything looks wrong.
- Preference persisted across sessions (Zustand persist or localStorage).

### Keyboard navigation
- Vim-style, no modifier key — j/k for list traversal, h/l for column focus, Enter to select, Esc to deselect. Disabled when an input is focused.
- `?` key shows a keyboard shortcut help overlay (modal, dismissible with Esc). Pattern: GitHub, Gmail, Slack.
- Subtle highlight ring (light blue/accent border) for keyboard focus indicator. Standard accessibility pattern.
- Additional shortcut: `r` to trigger a pipeline run from anywhere.
- Existing Cmd+K command palette continues to work alongside vim keys.

### Visual polish
- **Quality bar: best-in-class.** User is willing to invest cycles for premium look and feel. This is not a quick pass — it's a comprehensive review and upgrade.
- Linear-style clean aesthetic — tight spacing, clear hierarchy, minimal decoration. Professional tool feel.
- **Bounce AI brand colors:**
  - Primary green (dark): `#03532c`
  - Primary green (mid): `#006634` / `#0a6b39`
  - Primary green (light/accent): `#52b788`
  - Gold accent: `#d4a017` (highlights, status indicators)
  - Warm off-white backgrounds: `#faf6ee` / `#fff7e7`
  - Neutral gray: `#797979`
- Map brand colors to shadcn/ui theme tokens for both light and dark modes.
- Known pain points: spacing/alignment inconsistency, typography needs work, color palette is bland, markdown rendering is unstyled.
- **Markdown rendering overhaul:** Headings don't stand out, lists are cramped, no visual rhythm, code blocks look bad. Needs a complete typography treatment — font sizes, line heights, spacing between sections, inline code and code block styling.
- Desktop-only for v3.0. No responsive/mobile considerations.

### Claude's Discretion
- Exact spacing values and typography scale
- How to structure the config form sections (which fields group together)
- Loading/saving animation for config panel
- Dark mode color adjustments for charts or data-heavy views
- Order and grouping of keyboard shortcuts in the help overlay

</decisions>

<specifics>
## Specific Ideas

- "I really want this to be a best-in-class product from a look and feel perspective" — the polish pass should be thorough, not a quick tweak
- Brand colors from Bounce AI deck (April 2026 Business Review) — green primary, gold accent, warm whites
- Linear as the aesthetic reference — clean, tight, professional tool
- Summary markdown rendering is the most visible pain point — users read summaries daily, so typography quality matters most there

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 29-config-management-polish*
*Context gathered: 2026-04-09*
