# NextRM — Repository Implementation Contract

This document defines engineering constraints, operational boundaries, and code integrity rules for NextRM contributors and automated coding agents.

Read the canonical documentation hierarchy before making changes:
1. [docs/PRODUCT.md](docs/PRODUCT.md): Product scope, personas, solutions, and operational boundaries.
2. [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): System components, data models, APIs, and AI adapter contracts.
3. [docs/DESIGN.md](docs/DESIGN.md): Visual design tokens, screen layouts, states, and accessibility standards.
4. [docs/DEPLOY.md](docs/DEPLOY.md): Local development, environment variables, and Google Cloud deployment.
5. [README.md](README.md): Quickstart setup, repository layout, and verification commands.

---

## 1. Scope and Core Authority

NextRM is an AI relationship copilot that helps banks turn customer conversations and prospect data into sourced, reviewable signals and structured follow-ups. Both core journeys are mandatory and equally important:
- **Journey A (Retention):** Sourced assistance, care-first customer signals, and reviewed RM follow-ups for existing customers.
- **Journey B (Acquisition):** Proactive candidate shortlists, identity/duplicate checks, territory map review, and reviewed RM follow-ups for prospects.

NextRM is strictly an **engagement copilot**. Loan underwriting, credit decisions, product opening, account creation, funds movement, and transaction reconciliation are external bank functions. NextRM neither executes nor simulates those workflows.

---

## 2. Institution and Role Boundaries

1. **Multi-Tenancy:** Every request must enforce tenant isolation server-side. Users, customers, prospects, sources, signals, journeys, and governance configurations belong to an isolated institution tenant. Never trust client-supplied tenant headers or allow cross-tenant data access.
2. **Role Separation:**
   - `CUSTOMER`: Accesses own phone chat, own financial insights, care-first nudges, and official bank contact info. Cannot view internal RM notes, staff drafts, or other customers.
   - `RM`: Relationship Manager is the sole business-staff role. RMs review signals, prepare follow-ups, and generate briefs/drafts. Cannot access customer phone chat directly or modify customer commercial preferences.
   - `INSTITUTION_AI_ADMIN`: Configures governance policies, releases, and RM coverage/capacity. Cannot view raw customer conversations without an explicit quality grant.
   - `QUALITY_REVIEWER`: Inspects evaluation runs and conversation telemetry under an explicit, time-bounded content grant. Cannot publish governance rules or alter RM assignments.
   - `PLATFORM_OPERATOR`: Provisions tenants and platform metadata. Has no access to customer documents, conversation transcripts, or banking decisions.
3. **Entity Separation:** Business organizational contacts (`rm_contacts`) link professional and board roles; they never grant access to individuals' personal accounts or retail finances.

---

## 3. Shared Data and State Integrity

1. **Entity Models:** Use the active `rm_*` domain tables (`rm_parties`, `rm_contacts`, `rm_sources`, `rm_prospects`, `rm_conversations`, `rm_turns`, `rm_signals`, `rm_review_events`, `rm_journeys`, `rm_nudges`, `rm_governance_releases`).
2. **Source Provenance:** Every signal, insight, brief point, and draft must retain its source origin, content hash, version, and visibility scope. Observations, model inferences, staff reviews, and customer statements must remain distinct.
3. **Deterministic Financial Logic:** All money calculations (cash flow differences, spending variances) must use Python `Decimal` arithmetic. Never use floating-point types or delegate calculations to model generation. Missing financial inputs return `UNAVAILABLE`; never default to zero or fabricate balances.
4. **Optimistic Concurrency:** State mutations must use atomic compare-and-swap (CAS) on version numbers (`base_version`) and stable request idempotency keys (`request_key`). Concurrent conflicts must return HTTP 409 with actionable state diffs.
5. **Append-Only Auditing:** Signal reviews, preference changes, and follow-up updates must append immutable audit records (`rm_review_events`, `rm_contact_records`). Never rewrite historical reviews, releases, or customer conversation turns.

---

## 4. AI and Communications Discipline

1. **Single AI Seam:** All generative model interactions must route through `services/api/app/services/assistant/engine.py` using the official Google Gen AI SDK (`google-genai`).
2. **Typed Structured Outputs:** All model calls must specify `temperature: 0` and enforce strict Pydantic schemas (`ModelAnswer`, `RMAIBriefModel`, `RMAIDraftModel`).
3. **Deterministic Guardrails:**
   - **Exact-Span Need:** Extracted customer needs must match an exact substring of the customer's message.
   - **Numerical Grounding:** Every digit or percentage in an answer, brief, or draft must exist in the cited source text or validated snapshot.
   - **Source Verification:** Every cited source ID must exist in approved prompt sources.
   - **Prohibited Phrases:** Rejects commitments (`approved`, `guaranteed`, `i have sent`, `transfer completed`, `risk tolerance`, `creditworthy`).
   - **URL Integrity:** No external URLs are permitted unless present in approved knowledge.
   - **Credential Redaction:** Passwords, PINs, OTPs, CVVs, and card numbers are redacted prior to persistence or prompt assembly.
4. **No Silent Fallback:** If the selected Google provider (`vertex` or `gemini`) fails or times out, the system must raise `ProviderFailure` or `ProviderUnavailable`. Never silently fall back to mock or replay responses. Responses must clearly declare their mode (`LIVE` vs `SIMULATED`).
5. **Draft-Only Communications:** NextRM generates outreach drafts (email and phone scripts) only. It **never sends outbound communications** directly (no automated emails, SMS, or WhatsApp messages).
6. **Commercial Consent & Refusal:** Customers with `RESTRICTED` consent cannot receive commercial suggestions or outreach. Customer refusal suppresses sales signals immediately; service and support assistance survive refusal.
7. **Prompt Security:** Customer messages and retrieved documents must be treated as untrusted data strings. The model is never granted arbitrary tools, SQL access, shell execution, or outbound network access.

---

## 5. UI and Engineering Discipline

1. **Shared Design Tokens:** Adhere to tokens defined in [docs/DESIGN.md](docs/DESIGN.md) (canvas `#F6F5F1`, primary `#285C3C`, ink `#202720`). Avoid ad-hoc styling, neon accents, or unverified animation libraries.
2. **Care-First Priority:** Relationship queues must order urgent service friction ahead of commercial opportunities.
3. **Navigation Guidance vs Completion:** External product menu links are static, server-validated URLs. Missing links display `NOT_CONFIGURED`. Marking an RM follow-up `DONE` records staff task completion only; it never converts a prospect or opens a product.
4. **Component State Hygiene:** Handle loading, empty, partial, and error states gracefully. Provide accessible keyboard alternatives for complex views (e.g., candidate shortlist complements the 3D map).
5. **No Placeholders:** Never commit dead code, mocked endpoints, stubs, fake fallbacks, or unresolved `TODO` comments.

---

## 6. Testing and Verification Discipline

1. **Focused Verification:** Run targeted checks before submitting changes:
   - Backend pytest suite: `./.venv/bin/pytest -q`
   - Frontend typechecking & build: `npm --prefix apps/web run typecheck && npm --prefix apps/web run build`
   - Invariant and UI scripts: `node scripts/test_cache_invariants.mjs`, `node scripts/test_account_ui.mjs`, `node scripts/test_governance_ui.mjs`, `node scripts/test_customer_mvp_ui.mjs`, `node scripts/test_enrichment_ui.mjs`
   - End-to-end HTTP validation: `./.venv/bin/python scripts/validate_account_http.py`
2. **Honest Reporting:** Report only executed test commands and observed results. Never claim verification for commands that were not run.

---

## 7. Cloud Delivery and Operations

1. **Architecture:** Public Next.js web service and private FastAPI backend hosted as separate Cloud Run services.
2. **Service Identity:** In Google Cloud, the web service invokes the private API using Cloud Run IAM OIDC tokens (`Authorization: Bearer <ID_TOKEN>`). End-user identity is separately transmitted and verified via Firebase JWTs (`X-Firebase-Token`).
3. **Database Migrations:** Schema migrations (`alembic upgrade head`) run once as a controlled Cloud Run Job before traffic migration. Database schema changes must be backward-compatible; changing traffic routes does not roll back schema.
4. **Secret Isolation:** Database credentials and API keys are managed exclusively through Google Secret Manager or secure environment variables. Never expose server secrets to client bundles.
