# Phase 25: Next.js Scaffold + Summary View - Context

**Gathered:** 2026-04-08
**Status:** Ready for planning

<domain>
## Phase Boundary

User opens localhost:3000 and sees yesterday's summary in a three-column layout, can navigate between dates, and browse weekly/monthly roll-ups. Entity browsing (Phase 26), entity management (Phase 27), and responsive/mobile layout (Phase 29) are out of scope.

</domain>

<decisions>
## Implementation Decisions

### Summary rendering
- Structured cards (decisions, commitments, substance) render above the full markdown summary
- Cards are expanded by default but collapsible — collapse state persists per session
- Commitments display owner and deadline as inline colored badges/chips next to commitment text
- Markdown section renders clean by default; hovering over sentences reveals source attribution (source type, confidence)
- Empty structured sections are hidden — only cards with data for that day are shown

### Date navigation flow
- Left nav shows a scrollable date list, most recent on top
- Navigation organized into grouped sections: "Daily", "Weekly", "Monthly" — each section expandable
- Each date entry shows: date, meeting count, commitment count, and 1-2 top themes as tags
- Prev/next arrows skip to next available date; unavailable dates show empty state ("No summary for April 5")
- Calendar popover (triggered by calendar icon) for jumping to a specific date — dates with summaries highlighted in the popover

### Three-column layout
- Right sidebar shows summary metadata panel: sources used (with icons), meeting count, items extracted, pipeline run timestamp at top; quality indicators (confidence scores, source coverage, synthesis warnings) below
- Both left nav and right sidebar are collapsible to thin icon rails (~48px), Linear/Notion style
- When sidebars are collapsed, center panel caps at ~800-900px max-width and centers on screen for readable line lengths
- Desktop-first — set minimum viewport width, do NOT invest in responsive/mobile layout (deferred to Phase 29)

### Information density
- Sticky section headers in the markdown content area — as user scrolls, current section header sticks to top for orientation

### Claude's Discretion
- Loading skeleton design and animation style
- Exact spacing, typography, and color palette choices
- Error boundary visual treatment
- Toast notification positioning and timing
- Icon choices for source types and nav elements
- Exact sidebar icon rail icons

</decisions>

<specifics>
## Specific Ideas

- Both sidebars collapsible was an explicit user request — treat as a first-class feature, not an afterthought
- Hover-to-reveal source attribution on markdown: this needs careful UX — should feel informational, not cluttered. Consider subtle underline or highlight on hover to indicate attribution is available
- The grouped sections pattern (Daily/Weekly/Monthly) in the left nav should feel like Notion's sidebar sections — expandable/collapsible with clear visual hierarchy
- Date list entries with stats + theme tags should be scannable — think of them as mini-cards in the nav

</specifics>

<deferred>
## Deferred Ideas

- Responsive/mobile layout — explicitly deferred to Phase 29 (design polish). Document the minimum viewport width assumption so Phase 29 knows what to address
- Entity data in right sidebar — Phase 26 will replace/augment the metadata panel with entity insights

</deferred>

---

*Phase: 25-next-js-scaffold-summary-view*
*Context gathered: 2026-04-08*
