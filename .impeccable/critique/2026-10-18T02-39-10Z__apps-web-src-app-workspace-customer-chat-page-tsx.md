---
target: customer/chat Home and Chat
total_score: 28
p0_count: 1
p1_count: 2
timestamp: 2026-10-18T02-39-10Z
slug: apps-web-src-app-workspace-customer-chat-page-tsx
---
## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3 | Snapshot date shown; no readiness cue on the empty chat |
| 2 | Match System / Real World | 2 | Figures did not add up: safe to spend and expected spending ignored goals; "Active subscriptions 10" counted weekly groceries and dining |
| 3 | User Control and Freedom | 3 | Panels had a back button but no Escape |
| 4 | Consistency and Standards | 2 | Tiles, lead strip and pill links used three styles for the same action |
| 5 | Error Prevention | 4 | Empty sends blocked, busy and unknown states locked |
| 6 | Recognition Rather Than Recall | 3 | Tile chips lacked comparison bases |
| 7 | Flexibility and Efficiency | 2 | Static chat starters ignored the customer's own data |
| 8 | Aesthetic and Minimalist Design | 2 | Goals tile overflowed its card; device mockup wasted 160px on real phones |
| 9 | Error Recovery | 3 | Retry notices push the frame |
| 10 | Help and Documentation | 4 | Approved education and official RM contact present |
| **Total** | | **28/40** | **Good** |

## Anti-Patterns Verdict
Calm paper and forest palette, tabular figures, no gradients or glass. Tells: generic sparkle icon, static starters. Deterministic detector unavailable (bundled detector missing); axe: heading-one on Home (sr-only h1 present) and region on the demo strip.

## Priority Issues
- [P0] Numbers did not tally. Available IDR 12,500,000 split into safe to spend and "expected spending" without goal contributions; recurring "amount" summed single charges (IDR 3,815,000) instead of monthly estimates (IDR 5,568,333.33); weekly groceries were scheduled monthly and counted as subscriptions. Fix: backend waterfall (bills due, card due, goal set-aside, everyday spending) and bills vs regular spending split.
- [P1] Device mockup on real phones: top bar 56px + wrapping demo strip 90px + fake status bar; Home overflowed 375x667 by 123px. Fix: full-bleed at 520px or less.
- [P1] Goals tile progress and percent overflowed the tile by 35px. Fix: min-width 0 on the mini goal row.
- [P2] Three visual patterns for one action. Fix: shortcuts styled like tiles, each with its key figure.
- [P2] No Escape from panels; 200% zoom collapsed tiles to 63px. Fix: Escape handler, single column under 300px container width.

## Persona Red Flags
- Dina (mobile banking customer): sees IDR 10,643,888.89 safe to spend while IDR 2,000,000 of goal contributions are due; cannot reconcile the figures.
- Casey (one-handed, distracted): 11 targets, scroll needed on a small phone.
- Sam (keyboard and zoom): no Escape; 200% zoom squeezes targets under 44px.

## Minor Observations
- Chat source note still says "View Insights".
- Hero decimals (".89") add noise in IDR.

## Questions to Consider
- Should safe to spend lead the hero instead of the raw balance?
- Should goal contributions be scheduled on a real date rather than reserved for the whole month?
