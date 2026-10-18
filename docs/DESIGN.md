# NextRM — Design System and UI Specification

NextRM’s design system emphasizes clarity, operational density, and calm, evidence-first interactions. The visual interface is designed for banking professionals who require immediate context and reliable audit trails, and for retail banking customers seeking prompt, unobtrusive assistance.

---

## 1. Visual Language and Design Tokens

The visual design is anchored on a warm paper-like canvas, dark carbon typography, deep-green primary actions, and restrained status accents. Decorative gradients, neon colors, glassmorphism, and artificial confidence animations are strictly avoided.

### Color Palette and Design Tokens

| Token Identifier | Reference Hex Value | Semantic Role |
|---|---|---|
| `--color-canvas` | `#F6F5F1` | Primary application background (warm neutral paper tone) |
| `--color-surface` | `#FFFFFF` | Card, modal, and panel background |
| `--color-surface-subtle` | `#F0F1EA` | Secondary surface, table header, and sidebar background |
| `--color-ink` | `#202720` | Primary text and high-contrast headings |
| `--color-ink-secondary` | `#525D53` | Secondary text, field labels, and metadata |
| `--color-ink-muted` | `#5F695F` | Subdued annotations, helper text, and placeholders |
| `--color-separator` | `#DADFD5` | Subtle dividers and interior borders |
| `--color-border-control` | `#7C877B` | Interactive input borders and toggle outlines |
| `--color-primary` | `#285C3C` | Primary button background and accent green |
| `--color-primary-hover` | `#204D31` | Hover state for primary actions |
| `--color-primary-soft` | `#EDF3E9` | Soft green background for positive tags and active states |
| `--color-warning` | `#805015` | Warning text, attention badges, and time-sensitive flags |
| `--color-warning-soft` | `#FFF4DE` | Background tint for warning callouts and snooze badges |
| `--color-danger` | `#A13228` | Critical errors, fraud alerts, and commercial refusal tags |
| `--color-danger-soft` | `#FBEFEC` | Background tint for error banners and urgent service items |
| `--color-info` | `#285D86` | Information callouts and focus rings |
| `--color-info-soft` | `#EDF3F8` | Background tint for educational insights and citation highlights |

### Border Radii and Elevation
- **Control Radius:** `6px` for buttons, text inputs, dropdown selectors, and small tags.
- **Panel Radius:** `10px` for main cards, modals, phone frames, and container modules.
- **Elevation & Shadows:** Flat borders (`1px solid var(--color-separator)`) are preferred for layout structures. Box shadows are reserved exclusively for overlays and dropdown menus:
  ```css
  box-shadow: 0 12px 36px rgba(32, 39, 32, 0.14);
  ```

### Typography and Hierarchy
- **Font Stack:** Standard system sans-serif font stack (`-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif`) with optional local Inter.
- **Typographic Scale:**
  - Page Title: `28px` font size / `36px` line height, semibold (600 weight).
  - Section Title: `18px` font size / `26px` line height, semibold (600 weight).
  - Subsection / Header: `16px` font size / `24px` line height, medium (500 weight).
  - Body Text: `14px` or `16px` font size / `22px`–`24px` line height, regular (400 weight). Readable narrative text blocks are constrained to `65–75ch`.
  - Metadata / Small: `12px` or `13px` font size / `18px` line height, regular (400 weight).
- **Numerals:** Financial figures, counts, and dates use tabular numerals (`font-variant-numeric: tabular-nums`) to ensure alignment across data tables.
- **Capitalization:** Standard sentence case for headers, table columns, and button labels.

### Spacing and Grid Base
- **Base Grid:** `4px` incremental unit.
- **Spacing Scale:** `8px`, `12px`, `16px`, `20px`, `24px`, `32px`, `48px`.
- **Target Sizes:** Minimum interactive control height is `40px` on desktop and `44px` on mobile/touch interfaces.

---

## 2. Layouts per Application Surface

NextRM organizes views across three distinct physical surfaces: the customer phone interface, the RM relationship workspace, and the administrative governance panel.

### 1. Customer Assistant (`/customer/chat`)
The customer view is presented inside a device frame (`390px` wide) on wider screens. At 520px wide or less the frame, fake status bar and outer caption spacing disappear: the app fills the viewport under a one-line synthetic-demo strip, and the institution top bar is hidden while that strip is shown.
- **Header:** Institution brand mark, active customer profile greeting, and quick access to official bank RM contact information.
- **Navigation Tabs:**
  - **Home View:** One screen with no long scroll at phone height. A balance block shows available funds, a 30-day balance line and a bar whose parts add up to the balance: safe to spend, everyday spending until payday, this month's goal contributions set aside, and any bills or card payment due before payday, each with its figure. Four widgets follow (spending by category, goals, investments, market), then a next-step strip and three shortcuts in the same style as the widgets, each with its key figure (bills a month, net worth, explore). Every widget opens an in-place detail panel with a back button (`Escape` also returns). The Bills and cash panel repeats the tally as a waterfall ending in safe to spend, then lists bills and subscriptions separately from regular spending (weekly shopping, dining, transport) with cadence and next date. Goal savings sit in separate pockets: they count in net worth, not in available funds. Chart geometry comes only from the backend's decimal strings and the 30-day balance series; unavailable data shows a plain empty tile, never a placeholder chart.
  - **Chats View:** Persistent conversation area with multi-session support. One slim row carries `New chat`, `History` and the session title; the welcome state is a single heading with four starter chips. Up to three starters come from the customer's own figures (the fastest-rising spending category, a goal that is behind, a card to pay down, safe to spend); the fourth is always banking help.
- **Message Area:** Scrollable transcript. Customer messages are solid bubbles; assistant answers are cards with a mode tag (`Gemini · live` or `Simulated`), cited sources, and guided next-step chips.
- **Composer:** Pill-shaped input that grows to about five lines (16px text so iOS does not zoom), keyboard submission (`Enter` to send, `Shift+Enter` for line breaks) and a 44px send button.
- **Mandatory Footer:** Permanently pinned disclaimer at the base of the conversation:
  > *"AI can make mistakes. Always check important info."*
- **RM Contact Sheet Modal:** Opened from the header person icon. Displays bank-configured official phone numbers, email addresses, and relationship team availability. Contains no unmonitored peer-to-peer chat widget.
- **Message Your RM Sheet:** Native dialog opened from Home ("Message Maya" on the request card) or from the button under an answer when the assistant suggests a person (prefilled with the customer's words). Fields: the message, how to be contacted (Phone call, Video call, Meet at a branch, Email) and when (Morning, Afternoon, Any time). Sending shows a confirmation in the sheet ("Sent to Maya. Maya will call you in the morning."). Helper text states the RM replies outside the app.
- **Request Card (Home):** Always visible. Header "Your RM, Maya" with the Message button; empty state invites a first message. Each request shows the customer's words, a three-step track (Sent, Maya contacts you, Done), the contact preference with Change, and one status sentence in the customer's terms ("Maya plans to call you by 21 Oct").

### 2. Relationship Manager Workspace (`/workspace`, `/retention`, `/relationships/[id]`)
Designed for high information density and fast decision-making:
- **Application Shell:**
  - Sidebar (`216px` fixed width): Navigation links for Home & Briefing, Existing Customers (Retention), Acquisition (Territory), and Follow-ups.
  - Topbar (`64px` height): Search input, active institution indicator, signed-in RM avatar, and demo account switcher.
  - Content Canvas: Fluid width (up to `1600px` maximum useful width), padded with `24px`–`32px`.
- **Retention Desk (`/retention`):**
  - Care-First Queue: Priority rows ordered by service urgency. Row columns: Customer Name, Signal Category (`SERVICE_ISSUE`, `OPPORTUNITY`, `RESEARCH`, `GUIDANCE`), Urgency Badge, Evidenced Source, Time Ingested, and Next Action button.
  - Signal Review Drawer: Expanding side sheet showing exact source excerpts, proposed customer need, uncertainty classification, and buttons to Accept, Correct, or Dismiss with required audit reasons.
- **Relationship Detail (`/relationships/[id]`):**
  - Header: name, one line of kind, segment, locality and relationship, then one line of facts (identity, contact permission, RM, products). No card grid.
  - Tabs, opening on **Needs** when any need is open, otherwise on **Overview**:
    1. **Needs (count):** open needs grouped care first (Customer has a problem, Ready to talk, Asked for you, Spotted for you). Each need is one row: title, a one-line excerpt, urgency, a step chip (`To check`, `Plan follow-up`, `Follow-up in progress`) and age. One row is open at a time (the linked need, else the first). An open row shows what happened with its source, what it means only when that differs from the customer's words, the customer's contact preference, the next step and only the actions for that step. Follow-ups without a need are listed under Other follow-ups. Done and dismissed needs fold into one disclosure.
    2. **Overview:** financial snapshot and the AI relationship brief (key facts, talking points with source badges, discovery questions, cautions).
    3. **Behavior:** chronological app activity (e.g. repeated deposit views, card error events).
    4. **Notes & history:** sources, business contacts, internal note and review history.

### 3. RM Acquisition and Territory Desk (`/acquisition`)
One desk for every acquisition opportunity. Assigned prospects (bank source records) and businesses found around the chosen area share one list, one map and one detail panel.
- **Area bar:** the current centre (demo office, device location or a searched place), address search, `Use my location` (opt-in, never sent to the server), `Use demo area`, and a radius select (`500 m`, `1.5 km`, `3 km`, `5 km`, `All my prospects`).
- **Group chips:** `All`, `Ready to talk` (need checked and contact allowed; hot leads first), `To check` (need, identity, possible customer match or stale source), `New nearby` (not a customer or prospect yet), `In follow-up`, and `Not for now` (restricted, on hold or already a customer; collapsed under `All`). Each chip shows its count. A text search covers name, place, need and contacts.
- **Three columns:** the grouped list (`300–360px`) with a sort select (`Best first`, `Nearest first`); the Google map (fluid) with one pin colour per group and a legend; the detail panel (`340–400px`): the prospect brief or the place card with its customer-match check. Below 1300px the detail moves under the map; below 768px a `List` / `Map` switch shows one view at a time and choosing a row opens its detail.
- **Deduplication:** a business already linked to one of your prospects appears once, as the prospect. Adding a new business as a prospect moves it into `To check` and selects it.
- **Map failure:** a missing key or a map that fails to load shows an inline notice. The list and details keep working.

### 4. RM Follow-up Management (`/follow-ups`, `/follow-ups/[id]`)
- **Task List View:** Filterable queue showing open, snoozed, overdue, and completed follow-up items.
- **Two-Stage Follow-up Detail Card (`/follow-ups/[id]`):**
  - **Live Synchronization Strip:** Shows the customer's preferred contact channel, due date, and a live preview chip of what the customer currently sees in their mobile banking app (e.g. `Maya plans to contact you by 21 Oct`).
  - **Stage 1 (Pre-call prep / Before the call):** Customer's exact words in an emphasized quote box, paired with a unified **Outreach Script** (tailored to phone script or email) with a 1-click `Copy script` action and optional Gemini refinement.
  - **Stage 2 (Outcome logging / After the call):** After speaking with the customer via official bank channels, the RM selects a structured human outcome (e.g., `DISCUSSION_RECORDED`, `MEETING_SCHEDULED`, `NO_CURRENT_NEED`), logs mandatory notes, and clicks `Record follow-up done`.
  - **Closing parity:** Clicking `Record follow-up done` completes the RM task and transitions the customer's in-app 3-step tracker to `Done`.
### 5. AI Governance and Administration (`/settings/governance`, `/settings/ai-quality`, `/settings/assignments`)
- **Rules & Governance (`/settings/governance`):**
  - Bounded intent flow editor displaying intent name, trigger keywords, example queries, linked knowledge base categories, and permitted execution steps.
  - **Draft → Test → Publish Toolbar:** Displays current draft version, test execution status, generated SHA-256 digest, and an immutable publish button.
  - Policy preview drawer allowing administrators to test query resolution and view the resolved execution plan without model invocation.
- **AI Quality & Observability (`/settings/ai-quality`):**
  - Real-time telemetry dashboard showing average model response latency, token consumption, and error rates across evaluated test suites.
  - Evaluation Run Launcher: Button to trigger asynchronous test runs with live status tracking (`QUEUED`, `RUNNING`, `COMPLETED`).
  - Monitored session trace inspector (visible only to users with explicit quality content grants).
- **RM Coverage & Capacity (`/settings/assignments`):**
  - Workload matrix configuring dedicated customer book caps, active shared-case limits, and shared-pool participation per RM.
  - Customer coverage re-assignment tool supporting dedicated, shared, and digital-first relationship tiers.

### 6. Staff Assistant Panel (RM Copilot and AI Quality Analyst)
A right-side panel (`clamp(340px, 27vw, 400px)`, sticky, full viewport height) beside the record in view, so it never covers the work. Open by default at 1200px and wider; narrower screens get an `Ask copilot` launcher that opens it as a right sheet. `/` opens and focuses it; `Esc` closes it and returns focus to the launcher.
- **Header:** what the answer can use, in words (`Dina Rahma · assigned to you`, `AI quality · metadata only`), the record version, and an access line with the `Gemini` or `Simulated` tag.
- **Empty state:** `Ask about {subject}`, the record count and up to three starters built from the open record (open needs, contact permission, overdue follow-ups, latest run).
- **Answer:** the direct answer first, then up to four points. Each point carries an evidence tag (`Customer said`, `Observed`, `Your note`, `Recorded activity`, `NextRM record`, `Bank policy`, `Measured`) and record chips; a source chip expands the original excerpt in place. `AI inference` points use a dashed outline and secondary italic text so they never read as fact.
- **Actions:** at most one per answer (`Insert into note`, `Prepare follow-up`, `Open draft`, `Open run`, `Inspect trace`, `Run reference evaluation`, `Open governance`). Each opens the existing form or control, pre-filled; the person confirms. An unavailable action stays visible, disabled, with its reason (for example restricted commercial contact).
- **States:** pending (`Reading the records in scope…` within the same frame), answer withheld (failed evidence checks), Gemini unavailable (no simulated substitute), outside your access, and record changed (`Reload record`). Each names what happened and the next step.
- **Footer:** `AI can make mistakes. Always check important info.`

---

## 3. Component and State Interaction Rules

To ensure predictable behavior across the application, components follow strict state and recovery guidelines:

### State Machine for Key Components

| Component | Allowed States | Transition Rules & UI Behavior |
|---|---|---|
| **Queue Row** | `DEFAULT`, `HOVER`, `SELECTED`, `PROCESSING` | Clicking a row selects it and immediately updates the detail panel. Multi-row bulk selections are prohibited to prevent accidental bulk actions. |
| **Signal Item** | `NEW`, `IN_REVIEW`, `ACCEPTED`, `DISMISSED` | Accepting a signal requires selecting a proposed need and opens follow-up preparation. Dismissing a signal requires an explicit cancellation reason. |
| **Follow-up Task** | `PLANNED`, `IN_PROGRESS`, `DONE`, `CANCELLED` | Transitioning to `DONE` or `CANCELLED` requires an outcome classification and notes. Completed tasks are immutable and archived to history. |
| **In-App Nudge** | `AVAILABLE`, `EXPLORED`, `REQUESTED`, `DISMISSED` | `EXPLORED` populates the chat composer without creating staff tasks. `REQUESTED` creates a reviewable signal. `DISMISSED` suppresses the item. |
| **Governance Policy** | `DRAFT`, `TESTED`, `PUBLISHED` | Edits modify `DRAFT`. `TESTED` requires 100% pass on regression cases and pins a SHA-256 digest. `PUBLISHED` generates an immutable release record. |

### Empty, Error, and Loading States
- **Loading States:** Skeletons matching exact row heights are used instead of spinning loaders. Interactive buttons display inline spinner icons while retaining original button dimensions.
- **Empty States:** When queues or search results return zero items, the interface presents an honest explanation (e.g., *"No urgent service signals pending review"*) rather than a blank canvas.
- **Error Boundaries:** Component-level error boundaries isolate failures. If the 3D territory map encounters WebGL context loss, the interface immediately falls back to a clean 2D SVG map without crashing the candidate shortlist or detail panels.
- **Honest Abstention:** When model generation fails or times out, the assistant displays an explicit recovery message (e.g., *"Service temporarily unavailable; please check official bank channels"*) rather than fabricating an answer or showing raw stack traces.

---

## 4. Accessibility and Responsive Guidelines

NextRM is engineered to comply with **WCAG 2.2 Level AA** standards:

### Keyboard Navigation and Focus Management
- **Logical Tab Order:** All interactive controls (buttons, inputs, table rows, tabs) are reachable via `Tab` and `Shift+Tab`.
- **Visible Focus Rings:** Every focused element exhibits a distinct, high-contrast focus outline (`2px solid var(--color-info)`, with a `2px` offset). Default browser outlines are never removed without replacement.
- **Modal Dialogs:** Named native `<dialog>` elements or accessible modal containers capture focus on open, trap focus within the modal during interaction, and return focus to the trigger element upon closing (`Escape` key closes modals).
- **Map Accessibility:** The 3D map is fully operable via keyboard: arrow keys pan the scene, `+`/`-` keys zoom, and each establishment pin is accessible via standard tab stops with `Enter` triggering selection. The candidate shortlist acts as an accessible keyboard alternative to the map.

### Visual and Contrast Requirements
- **Contrast Ratios:**
  - Body text and primary headings exceed `4.5:1` contrast against their respective backgrounds.
  - Interactive controls, borders, and functional status badges exceed `3:1` contrast.
- **Non-Color Differentiation:** Status indicators (e.g., `URGENT`, `SERVICE_ISSUE`, `RESTRICTED`) never rely solely on color. Each status badge pairs a distinct background/border tint with clear text labels and standard iconography.
- **Zoom and Reflow:** Layouts gracefully reflow at up to `200%` browser zoom without clipping text, overlapping controls, or introducing horizontal scrolling on the root window.
- **Reduced Motion:** When `prefers-reduced-motion: reduce` is enabled, smooth transitions, camera fly-to animations on the 3D map, and layout drawer slides are disabled, resolving immediately.
