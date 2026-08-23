# MeetingHQ Design System

This document is the permanent implementation contract for MeetingHQ product UI.
New visual or interaction patterns must be added here before they are introduced
in feature code.

## Management page anatomy

Management pages follow the User Management reference:

1. Linked breadcrumbs
2. Page title and concise description
3. Primary actions
4. Live statistic cards
5. Search
6. Filters
7. Bulk actions
8. Main content
9. Optional contextual panel

Layouts use available screen width. Dense enterprise tables use horizontal
scrolling only when columns cannot be responsibly collapsed.

## Navigation and context

- Every authenticated page renders linked breadcrumbs.
- Deep links are first-class routes.
- Filters, search, pagination, and tabs are encoded into the URL.
- Browser Back and Forward restore route context.
- The last 20 pages are retained per signed-in user. Each entry stores its path,
  query context, label, parent, icon key, and timestamp.
- `Ctrl+K` opens command navigation and Global Search.

## Feedback

- Toasts appear in the top-right.
- Success toasts remain for 9 seconds; information and warning toasts remain for
  8.5 seconds.
- Error and explicitly critical toasts remain until dismissed.
- Toasts contain tone, icon, title, optional description, timestamp, dismiss
  action, and optional contextual action.
- Mutations show a global progress indicator and disable local controls while
  pending.
- Destructive actions use the shared confirmation dialog.

## Pagination

Enterprise data sets support 10, 25, 50, and 100 rows per page with total count,
first, previous, next, last, and current/total page controls. Infinite loading is
reserved for Chat, Notifications, and Activity.

## Responsive and accessible behavior

- Minimum supported viewport width is 320 pixels.
- Split panes collapse into drawers or full-screen detail surfaces on mobile.
- Every control has an accessible name and visible keyboard focus.
- Color never carries meaning alone.
- Motion respects `prefers-reduced-motion`.
- Loading uses skeletons for content and progress for operations.

## Incomplete modules

An incomplete route must render a professional Module Status page describing
availability, current state, and a safe navigation path. Placeholder cards,
dummy statistics, dead links, and fake actions are prohibited.
