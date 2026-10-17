# NextRM — Product Requirements

NextRM is an AI relationship copilot for banks. It bridges the gap between customer self-service and relationship manager (RM) engagement: customer conversations with a bank assistant and bank-supplied prospect data are transformed into sourced, reviewable signals that an RM can act on, with tenant isolation, customer consent, and strict governance enforced server-side.

---

## 1. Problem Statement

Relationship managers at retail and commercial banks face fragmented information. Context required to serve customers is scattered across chat transcripts, mobile app clickstreams, core account snapshots, and external lead lists. Preparing for a meaningful customer conversation requires manual compilation across disparate systems, leading to missed opportunities and stale follow-ups.

Conversely, retail banking customers seek quick, accurate help with everyday banking questions, card issues, and financial planning, but frequently encounter sales-driven chatbots or unsolicited outreach.

NextRM connects these two domains while preserving clear operational boundaries:
- Customers receive prompt, grounded answers from approved bank knowledge and their own validated financial snapshots, without unsolicited commercial pressure.
- Relationship managers receive an organized queue of evidenced signals, pre-call briefs, and outreach drafts, ensuring that every outreach is relevant, timely, and backed by explicit customer permission or verified institutional events.
- Bank operations and AI administrators retain full auditability and release control over assistant behavior, intent routing, and RM coverage models.

---

## 2. Users, Personas, and Account Boundaries

NextRM enforces strict role and subject boundaries across four primary personas. Each persona has a dedicated surface, and identities cannot access or impersonate other surfaces.

| Persona | Identifier | Role & Primary Surface | Access Boundary |
|---|---|---|---|
| **Dina Rahma** | `usr-dina` | **Customer**<br>`/customer/chat` (Phone-frame layout) | Personal relationship context only. Can view own financial snapshot insights, receive care-first nudges, chat with the assistant across multiple sessions, and open official bank contact channels. Cannot view internal RM notes, other customers, or AI administrative metadata. |
| **Maya Putri** | `usr-maya` | **Relationship Manager**<br>`/workspace`, `/retention`, `/acquisition`, `/relationships/[id]`, `/follow-ups` | Assigned customer relationships and prospects. Can review signals, generate pre-call briefs, prepare follow-ups, and generate outreach drafts. Cannot access customer phone chat directly, modify customer commercial preferences, or access AI quality/monitoring APIs. |
| **Arif** | `usr-aiadmin` | **Institution AI Administrator**<br>`/settings/governance`, `/settings/ai-quality`, `/settings/assignments` | Institution policy configuration, release management (draft, test, publish), RM coverage models, and aggregated system metrics. Cannot access raw customer conversation transcripts or private financial details without an explicit quality grant. |
| **Intan** | `usr-quality` | **Quality Reviewer**<br>`/settings/ai-quality` | Technical review of model evaluation runs, turn telemetry, latency, and error rates under an explicit, scoped quality content grant. Reviewer authority does not permit publishing governance policies or altering RM assignments. |

---

## 3. Core Solutions and Foundation

NextRM organizes bank relationship capabilities into three business solutions supported by an administrative governance foundation.

### Solution 1: Customer Assistant (`/customer/chat`)
- Embedded in a responsive mobile layout representing a modern mobile banking app.
- Multi-session chat support with persistent session history, new conversation creation, and server-side session isolation.
- Grounded factual question-answering over approved institution knowledge (savings, deposits, cards, payments, loans, wealth education, merchant services, privacy).
- Deterministic privacy and sensitive-data redaction (passwords, PINs, OTPs, CVVs, card numbers).
- In-the-moment financial review calculated via Decimal arithmetic: spending breakdown, safe-to-spend until payday, goal progress, credit card cost against savings yield, a snapshot of linked investment holdings, net worth and suggested next steps.
- Answers the ten most common customer money questions (where the money goes, safe spending, starting to invest, goals, portfolio, debt against saving against investing, recurring costs, next best action, financial health, and a market drop) from the customer's own figures and approved education. See "Customer Money Questions" in section 6.
- Investment suitability boundary: the assistant explains the customer's holdings, the dated market note and general concepts, but never recommends buying, selling or holding, never predicts markets and never states a risk tolerance. Personal advice requires the bank's suitability process, reached through an RM handoff that arrives as a sourced `GUIDANCE` signal.
- Personalized, care-first in-app suggestions (nudges) with customer controls to explore, request human follow-up, dismiss, or opt out.
- Official RM contact sheet displaying bank-configured contact channels; no unvetted in-app messaging.

### Solution 2: RM Retention (`/workspace`, `/retention`, `/relationships/[id]`, `/follow-ups`, `/pulse`)
- Centralized relationship desk displaying prioritized customer signals categorized as `SERVICE_ISSUE`, `OPPORTUNITY`, `RESEARCH`, or `GUIDANCE`.
- Care-first ordering: urgent service friction and time-sensitive customer requests always outrank commercial opportunities.
- Comprehensive customer profile view divided into Overview, Needs & Signals, Behavior Timeline, and Notes & History.
- Automated AI pre-call relationship briefing synthesizing verified customer statements, interaction timeline, and staff notes with strict source citations.
- Follow-up lifecycle state machine (`PLANNED`, `IN_PROGRESS`, `DONE`, `CANCELLED`) with snooze scheduling and structured human outcome recording.
- Engagement pulse tracking active review needs, urgent service items, and overdue follow-ups.

### Solution 3: RM Acquisition (`/acquisition`)
- Proactively supplied candidate shortlist generated from bank-authorized imports (CSV or seed sources), eliminating cold manual prospecting.
- Inspectable prioritization ordering (ACQ-1) based on verified candidate attributes, business need indicators, and contact eligibility.
- Territory visualization pairing an interactive 3D/2D district map with a synchronized list and candidate detail panel.
- Entity disambiguation handling both retail individuals (`PERSON`) and registered businesses (`ORGANIZATION`). Business profiles link professional contacts and board roles without granting access to individuals' personal finances.
- Duplicate detection and existing-customer cross-matching; existing banking relationships suppress redundant acquisition outreach.
- Structured needs-discovery briefing outlining conversation starters, missing qualification items, and contact channel constraints.

### Foundation: AI Governance & Coverage (`/settings/governance`, `/settings/ai-quality`, `/settings/assignments`)
- Bounded intent and response flow editor enabling administrators to map customer query patterns to approved bank knowledge and allowed response steps.
- Immutable release lifecycle: **Draft → Test → Publish**. Drafts must pass deterministic regression suites before publication.
- Runtime release binding: Active chat turns and nudge generation pin the published release version and content digest.
- RM coverage and capacity management: Configures dedicated RM assignment, shared service pool claims, and digital-first routing with enforceable book limits.
- Durable AI evaluation framework executing versioned test suites to measure model latency, adherence, and error rates.

---

## 4. Core User Journeys

### Journey A: Existing Customer Retention and Service Escalation
1. **Trigger:** A customer interacts with the bank assistant via `/customer/chat` or experiences service friction (e.g., repeated card failure or app error).
2. **Contextual Evaluation:** The assistant retrieves authorized customer context and approved bank knowledge. The request is evaluated against the active governance release.
3. **Assistance & Clarification:** The assistant provides a grounded factual answer, citing approved knowledge sources. If the customer indicates an unresolved issue or explicitly requests human assistance, the assistant offers to connect with their relationship manager.
4. **Signal Generation:** Under institution-configured capture rules, a reviewable signal is generated in `rm_signals` containing an exact-span customer need, category, urgency, and semantic deduplication key.
5. **RM Prioritization:** The signal appears in Maya's Retention queue. If marked `URGENT` (e.g., card loss or fraud concern), it surfaces at the top of the queue.
6. **Preparation:** Maya reviews the signal and customer profile. She triggers the AI Relationship Brief, which generates verified talking points and cautions citing specific source records.
7. **Task Creation & Outreach:** Maya creates an `RM_FOLLOWUP` task, generates an AI outreach draft (email or phone script), and conducts the call via the bank's official telephony.
8. **Resolution:** Maya records the human outcome, logs contact history, and marks the follow-up `DONE`. If the customer wishes to open a deposit or loan, Maya directs them to the bank's separate product menu.

### Journey B: Proactive Prospect Acquisition
1. **Candidate Ingestion:** New prospect records are ingested via CSV or authorized integration into `rm_prospects`.
2. **Identity & Duplicate Check:** The system verifies the entity against existing bank parties. If a match is found, acquisition outreach is suppressed to avoid contacting an existing customer as a cold lead.
3. **Shortlist Assignment:** Qualified prospects are assigned to Maya's Acquisition desk and displayed on the territory map.
4. **Context Review:** Maya selects a prospect from the list or map. The system displays source origin, registration date, why-now rationale, and associated business contact roles.
5. **Needs Review:** Maya reviews the hypothesized need, confirms contact permission (`ALLOWED`), and creates an `RM_FOLLOWUP` task.
6. **Outreach & Disposition:** Maya prepares an outreach script, contacts the prospect via authorized channels, logs the conversation, and sets the prospect disposition (`CONTACTED`, `QUALIFIED`, `NURTURE`, `DECLINED`, or `NO_CURRENT_NEED`).
7. **Transition:** Completed prospect tasks retain full audit history. Successful conversions guide the prospect to the bank's formal customer onboarding portal.

---

## 5. Scope Boundaries and Principles

NextRM enforces strict functional boundaries to maintain regulatory compliance, data protection, and operational safety.

### RM Engagement Only — No Banking Execution
NextRM is an engagement copilot, not a core banking system, loan origination system (LOS), or payment processor:
- **No Loan Underwriting or Approval:** NextRM does not assess creditworthiness, calculate loan affordability, issue approvals, or execute disbursements.
- **No Account or Product Opening:** NextRM cannot create core deposit accounts, issue credit cards, or bind insurance contracts.
- **No Financial Movement or Transactions:** NextRM cannot execute funds transfers, bill payments, or transaction reversals.
- **No Transaction Reconciliation:** NextRM does not reconcile general ledger entries or settle payment disputes.

### Draft-Only Outreach
- NextRM generates outreach drafts (email text and phone call scripts).
- NextRM **never sends outbound communications** directly (no automated emails, SMS messages, or WhatsApp notifications). All outbound outreach must be reviewed and initiated by the RM through official, monitored institution communication systems.

### Consent, Privacy, and Commercial Refusal
- Customer commercial communication preferences are strictly enforced (`ALLOWED` vs `RESTRICTED`).
- If a customer expresses commercial refusal (e.g., "stop selling," "no marketing," "do not contact"), commercial suggestions and opportunity signals are immediately suppressed.
- Service and support access **survives commercial refusal**: customers who opt out of sales retain full access to assistant help for service issues, card problems, and general inquiries.
- Internal RM notes, draft outreach text, and review rationales are strictly staff-only and are never projected to customer interfaces or included in customer model prompts.
- Personal financial details of business owners or executives are never accessible via commercial organizational relationships.

### Product-Menu Navigation Guidance vs Completion
- When customers inquire about opening accounts or applying for credit, NextRM guides them toward the appropriate section of the bank's existing application (e.g., "Products → Loans").
- Institution-configured destination links (`/v1/rm/destinations`) are static, server-validated URLs.
- If an institution URL is not configured, the interface displays `NOT_CONFIGURED` with manual navigation instructions; the model is never permitted to invent or hallucinatory deep links.
- Marking an RM follow-up `DONE` signifies that RM preparation and outreach work has been recorded. It does not certify that a product was opened, a loan was approved, or a prospect converted.

### Product Principles
1. **Calm, Precise, and Honest:** Interfaces prioritize clear typographic tables, readable rows, and explicit evidence citations over decorative widgets, synthetic risk scores, or artificial confidence meters.
2. **No AI Theatre:** The assistant does not present staged thinking steps, fake multi-agent debates, or simulated tool executions. If information is missing or unverified, the system abstains honestly.
3. **Deterministic Superiority:** Calculations, access permissions, commercial consent gates, and governance policies are executed by deterministic code (Python Decimal, database scopes, regex safety checks), never delegated to model discretion.
4. **Data as Content, Not Instructions:** All customer messages, imported prospect fields, and retrieved documents are treated as untrusted data strings, preventing prompt injection attacks.

---

## 6. Nudge Catalog and Financial Insights

NextRM provides explainable, care-first customer engagement through a bounded catalog of twelve nudge families and deterministic financial insights.

### Bounded Catalog of 12 Nudge Families

| ID | Family | Category | Trigger Condition | Customer Action | RM Consequence |
|---|---|---|---|---|---|
| **E01** | Welcome | `GUIDANCE` | Confirmed new customer relationship start event. | Explore assistant capabilities. | Deduplicated; creates no sales lead. |
| **E02** | Recognition | `RECOGNITION` | Verified birthday or anniversary on local date. | View greeting; dismiss. | Pure recognition; creates no commercial opportunity. |
| **E03** | Declared Goal | `GUIDANCE` | Customer declared life or savings goal (e.g., education, travel). | Edit goal privately; request RM discussion. | Explicit request creates an RM reviewable signal. |
| **E04** | Existing-Product Help | `GUIDANCE` | Customer holds product and reports difficulty or confusion. | Read approved guide; view bank menu. | Self-service guidance; unresolved issue routes to service. |
| **E05** | Service Care | `CARE` | Detected open service friction, failed transfer, or card issue. | Review status; request RM support. | High-priority service signal created; suppresses commercial nudges. |
| **E06** | Maturity Discussion | `GUIDANCE` | Confirmed time-deposit maturity approaching. | Review options; request RM discussion. | RM follow-up prepared on customer request; no auto-renewal. |
| **E07** | Liquidity Clarification | `GUIDANCE` | Customer inquires about available reserves or options. | Clarify horizon; read educational guide. | Educational guidance; no unauthorized investment suitability. |
| **E08** | Feedback & Preferences | `CARE` | Customer indicates irrelevance, snooze, or stop. | Dismiss instance, snooze topic, or opt out. | Commercial suppression applied; service assistance preserved. |
| **E09** | Cash-Flow Insight | `CARE` | Verified financial snapshot shows upcoming commitments near available funds. | Inspect breakdown; request budgeting help. | Sourced care prompt; suppressed if data snapshot is incomplete. |
| **E10** | Spending Analysis | `GUIDANCE` | Evidenced period-over-period spend variance or recurring charge. | View comparison; correct category. | Private analytical insight; customer correction logged as feedback. |
| **E11** | Life Planning | `EDUCATION` | Customer declared upcoming travel, relocation, or life milestone. | View checklist; ask approved questions. | Goal-aligned education; expires automatically at stated horizon. |
| **E12** | Reconnect | `CARE` | Customer inactivity exceeding configured threshold without refusal. | Inquire if assistance is needed. | Gentle check-in; respects contact limits and refusal flags. |

### Selection and Prioritization Rules
1. **Category Ordering:** Nudges are strictly prioritized by category: `CARE` > `GUIDANCE` > `EDUCATION` > `RECOGNITION` > `COMMERCIAL`.
2. **Display Budget:** The customer feed displays at most three items simultaneously (one primary card and up to two secondary cards).
3. **Freshness & Snooze:** Nudges respect configured freshness windows and customer snooze timers. Dismissed items are suppressed from immediate re-display.
4. **Commercial Suppression:** Any active service friction (`E05`), customer refusal (`E08`), or `RESTRICTED` contact status completely suppresses commercial nudge families.

### Financial Insights and Snapshot Rules
- Financial insights are derived strictly from authorized, validated customer financial snapshots using deterministic Python `Decimal` formulas.
- Available formulas:
  - **Cash-flow difference:** `available_funds - upcoming_commitments`.
  - **Spend change percentage:** `((current_spend - previous_spend) / previous_spend) * 100` (reported as unavailable if previous spend is zero).
  - **Recurring charge tracking:** Identifies repeated transactions within designated billing cycles.
- Missing data yields an explicit `UNAVAILABLE` status. NextRM never defaults missing balances or transactions to zero or fabricates estimates.
- Financial snapshots reflect reference periods only; they are never presented as live core-banking ledger balances or confirmed investable surplus.

### Customer Money Questions

| # | Customer question | Evidence used | Behavior | Boundary |
|---|---|---|---|---|
| 1 | Where is my money going and how can I stop overspending? | 30-day spend by category, share and change | Names the largest and fastest-growing categories, offers a cap or review | Information, no automatic budget |
| 2 | How much can I safely spend or save this month? | Balance, typical spending until payday, 30-day projection | Headroom until payday; flags a shortfall | Snapshot, not a live balance |
| 3 | How do I start investing with limited money? | Cash buffer, card debt, monthly surplus, approved education | Buffer and debt first, then how funds work | No product recommendation |
| 4 | Am I on track for my goals? | Target, saved, date, required against planned monthly saving | Per-goal status, monthly gap, later-date alternative | Goals are customer-declared |
| 5 | Is my portfolio performing well and what should I do next? | Holdings, value, gain or loss, 30-day change, concentration | Explains the figures, offers an RM review | No buy, sell or hold advice |
| 6 | Pay down debt, save more or invest? | Card rate, minimum payment, savings yield, cash left after repayment | Compares certain cost with possible return | No product advice |
| 7 | Can I cut subscriptions or recurring costs? | Per-merchant monthly estimate and type | Lists discretionary items with amounts | Cancelling happens with the merchant |
| 8 | What should I do next? | Fixed-order rules over the cards above | Presents the first steps as options | No execution |
| 9 | How is my overall financial health and net worth trending? | Assets, liabilities, buffer months, savings rate | Separate measures, never one score | No generic risk or health score |
| 10 | Why did my investments drop, is this normal, should I sell? | Holdings and the bank's dated market note | Explains the move, states it cannot say whether to sell, lists decision facts, offers an RM review | No timing, no prediction |

---

## 7. Non-Goals

The following areas are explicitly outside the scope of NextRM:
1. **Autonomous Financial Decisioning:** NextRM will never autonomously approve credit, decline loan applications, adjust interest rates, or execute portfolio trades.
2. **Direct Marketing Campaign Engine:** NextRM is not a mass-email or SMS broadcast marketing platform.
3. **Core Banking System / Ledger:** NextRM does not maintain ledger accounts, process clearing, settle transactions, or hold funds.
4. **Document Forgery Detection / Legal Certification:** OCR and document extraction adapters extract text spans for review; they do not certify document legality, authenticity, or audit compliance.
5. **Cross-Tenant Data Pooling:** NextRM never shares customer identities, conversation history, or prospect databases across different banking institutions.
