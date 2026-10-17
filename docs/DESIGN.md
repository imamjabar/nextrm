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
The customer view is presented inside a responsive mobile frame (`390px` width on desktop monitors; fluid full-width on mobile devices) representing a bank’s mobile application:
- **Header:** Institution brand mark, active customer profile greeting, and quick access to official bank RM contact information.
- **Navigation Tabs:**
  - **Home View:** Displays declared personal financial goals (editable inline), validated financial insights (cash flow differences, spending variances), and care-first suggestions (nudges).
  - **Chats View:** Persistent conversation area with multi-session support. Features a compact session bar with `+ New Chat` and an expandable History drawer.
- **Message Area:** Scrollable transcript of messages. Assistant answers clearly display cited source tags (`[Source: Savings Terms]`), expandable certainty notes, and guided next-step chips.
- **Composer:** Multi-line text input with keyboard submission (`Enter` to send, `Shift+Enter` for line breaks) and active provider status indicators (`LIVE` vs `SIMULATED`).
- **Mandatory Footer:** Permanently pinned disclaimer at the base of the conversation:
  > *"AI can make mistakes. Always check important info."*
- **RM Contact Sheet Modal:** Triggered when human assistance is requested. Displays bank-configured official phone numbers, email addresses, and relationship team availability. Contains no unmonitored peer-to-peer chat widget.

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
  - Four structured tabs:
    1. **Overview:** Core party details, relationship duration, contact consent status (`ALLOWED` vs `RESTRICTED`), and assigned coverage mode.
    2. **Needs & Signals:** History of customer statements, detected friction, and reviewable opportunities.
    3. **Behavior Timeline:** Chronological stream of app telemetry events (e.g., repeated deposit views, card error events).
    4. **Notes & History:** Staff-recorded follow-up notes, logged customer contact events, and prior task outcomes.
  - **AI Relationship Brief Panel:** Prominently positioned pre-call briefing card. Synthesizes key facts, talking points with clickable source badges, suggested discovery questions, and institutional cautions.

### 3. RM Acquisition and Territory Desk (`/acquisition`)
A daylight spatial workspace designed for proactive candidate review:
- **Three-Column Spatial Layout:**
  - **Column 1: Candidate Shortlist (`380px` width):** Assigned prospects ranked by inspectable ACQ-1 criteria. Displays company/individual name, industry category, distance from office, why-now rationale, and review status.
  - **Column 2: Interactive Territory View (Fluid):** Procedurally rendered 3D daylight district scene (built with Three.js) projecting semantic establishment pins onto an illustrative street grid. Synchronized pan/zoom controls and an instant 2D SVG map fallback.
  - **Column 3: Discovery Brief & Review (`420px` width):** Detailed candidate dossier showing commercial registration data, professional contact links (e.g., Managing Director, Finance Head), hypothesized need, contact eligibility, and action buttons to qualify or schedule outreach.
- **Radius and Category Filters:** Quick-toggle chips for travel radius (e.g., `1 km`, `3 km`, `5 km`) and industry segments (e.g., `Retail`, `Manufacturing`, `Healthcare`).

### 4. RM Follow-up Management (`/follow-ups`, `/follow-ups/[id]`)
- **Task List View:** Filterable queue showing open, snoozed, overdue, and completed follow-up items.
- **Task Detail Card:**
  - Contextual link to original signal or prospect candidate.
  - State controls: Transition buttons for `START`, `NOTE`, `COMPLETE`, and `CANCEL`.
  - Snooze Selector: Date/time picker to pause task visibility until a specific future date.
  - **AI Outreach Draft Generator:** Modal or inline drawer generating professional English outreach drafts (email or phone script). Drafts cite verified sources, adhere to customer consent gates, and include an explicit "Draft Only — Not Sent" banner.
  - Human Outcome Logging: Required structured outcome selector (e.g., `MEETING_SCHEDULED`, `NEEDS_CONFIRMED`, `NO_INTEREST`, `CALL_UNANSWERED`) with mandatory free-text notes.

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
