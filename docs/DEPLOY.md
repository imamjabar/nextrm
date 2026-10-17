# NextRM — Deployment and Operations Guide

This guide details local execution, environment configuration, Google Cloud deployment paths, and cloud architecture for NextRM.

---

## 1. Local Development and Testing

### Prerequisites
- **Python:** Version 3.11 or higher.
- **Node.js:** Version 20 LTS or higher (with npm).
- **PostgreSQL:** Version 16 or newer binaries (Postgres.app or `brew install postgresql@17`). `scripts/dev_db.sh` runs a project-local server on 127.0.0.1:54417 and creates the databases on demand.
- **Git:** Standard git client.

### Initial Setup
From the repository root:

```bash
# 1. Create and activate a Python virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install Python dependencies (FastAPI, SQLAlchemy, psycopg, pytest, pytest-xdist)
pip install -r requirements-dev.txt

# 3. Optional: Install Google Gen AI SDK for live Gemini / Vertex testing
pip install -r requirements-google.txt

# 4. Install Next.js frontend dependencies
npm --prefix apps/web ci
```

### Running the Application Locally

#### Production-Mode Local Run (`scripts/start_local.sh`)
Starts the project-local PostgreSQL, backs up an existing local database to `runtime/backups`, applies database migrations, seeds synthetic accounts, builds the Next.js frontend and launches the API, background worker and web server on loopback:
```bash
./scripts/start_local.sh
```

#### Hot-Reload Development Run (`scripts/dev_local.sh`)
Launches the FastAPI backend with uvicorn reload and Next.js in hot-reloading development mode (`next dev`):
```bash
./scripts/dev_local.sh
```

### Accessing the Local Demo
Navigate to <http://localhost:3000/demo> in your browser. Choose an authorized synthetic persona:
- **Dina Rahma** (`Customer`): Opens the mobile phone banking assistant at `/customer/chat`.
- **Maya Putri** (`Relationship Manager`): Opens the RM relationship workspace at `/workspace`.
- **Arif** (`Institution AI Admin`): Opens the governance and AI quality console at `/settings/governance`.
- **Intan** (`Quality Reviewer`): Opens AI quality monitoring with an explicit content inspection grant.

### Running Local Quality and Verification Checks
```bash
# Only the checks affected by edits since the last passing run, in parallel (the first run executes everything)
./scripts/check.sh

# Everything, plus the production build and the end-to-end HTTP flow on a disposable PostgreSQL database
./scripts/check.sh --all

# API suite alone on 6 parallel workers (add -n0 for one process, e.g. -n0 -k name)
./.venv/bin/pytest -q
```

Tests run on PostgreSQL, the production engine. A run applies the Alembic migrations and the synthetic seed once into a template database, each worker clones it once, and every test runs inside a transaction that is rolled back (`services/api/tests/conftest.py`). Measured on the development Mac (18 Oct 2026): the full API suite took 38 s wall time, against 218 s when every test dropped, recreated and reseeded its own SQLite database. `scripts/check.sh --all` (API suite, type check, UI scripts, production build and 152 HTTP checks) took 98 s, against about 280 s for the same checks run in series. `scripts/dev_db.sh gc` removes databases left behind by an interrupted run.

---

## 2. Environment Variables Reference

NextRM strictly isolates configuration between the frontend web service, backend API, and async worker.

| Variable Name | Service | Purpose and Default Values |
|---|---|---|
| `API_INTERNAL_URL` | Web | Loopback or private Cloud Run URL of the backend API (e.g., `http://127.0.0.1:8000`). |
| `NEXTRM_DEMO_MODE` | Web | Enables or disables the `/demo` synthetic persona selector (`true` for local/demo, `false` for production). |
| `NEXTRM_AUTH_PROVIDER` | Web | Authentication provider configured on the frontend (`synthetic_demo` or `firebase`). |
| `FIREBASE_WEB_API_KEY` | Web | Public Firebase Web API key for client-side authentication in production. |
| `ENVIRONMENT` | API, Worker | Application runtime environment (`development`, `test`, `production`). |
| `DEBUG` | API | Enables verbose exception traces (`true` locally, `false` in production). |
| `DATABASE_URL` | API, Worker | PostgreSQL URL. Local default `postgresql+psycopg://127.0.0.1:54417/nextrm` (`scripts/dev_db.sh`). Cloud Run reads it from Secret Manager: `postgresql+psycopg://nextrm_app:<password>@/nextrm?host=/cloudsql/<project>:<region>:nextrm-pg`. Required explicitly when `ENVIRONMENT=production`. |
| `DB_POOL_SIZE`, `DB_MAX_OVERFLOW` | API, Worker | SQLAlchemy pool per process (defaults 5 + 5; the demo API uses 10 + 10 and its in-container worker 2 + 0). Keep instances × (size + overflow) below the Cloud SQL `max_connections` (100). |
| `DB_POOL_TIMEOUT`, `DB_POOL_RECYCLE` | API, Worker | Seconds to wait for a pooled connection (default 30) and to recycle an idle one (default 1800). |
| `AUTH_PROVIDER` | API | Backend authentication verification mode (`synthetic_demo` or `firebase`). |
| `NEXTRM_AI_PROVIDER` | API, Worker | AI engine provider: `local` (deterministic simulated engine), `gemini` (Google AI Studio API key), or `vertex` (Vertex AI on Google Cloud). |
| `GOOGLE_CLOUD_PROJECT` | API, Worker | Authorized Google Cloud Project ID required when `NEXTRM_AI_PROVIDER=vertex`. |
| `GOOGLE_CLOUD_LOCATION` | API, Worker | Google Cloud region for Vertex AI endpoints (e.g., `asia-southeast1`, `asia-southeast2`). |
| `GEMINI_MODEL` | API, Worker | Pinned Gemini model ID. Pick one listed as available for your Vertex AI location at deploy time. |
| `GEMINI_API_KEY` | API | Server-side API key used only when `NEXTRM_AI_PROVIDER=gemini`. |
| `GEMINI_TIMEOUT_MS` | API | Upstream model request deadline in milliseconds (default: `20000`). |
| `GEMINI_THINKING_BUDGET`| API | Optional integer token budget for reasoning models. |
| `GEMINI_THINKING_LEVEL` | API | Optional string thinking level (e.g., `low`, `high`). |
| `NEXTRM_MENU_LINKS_JSON`| API | JSON mapping of tenant IDs and product categories to bank-configured destination URLs. |
| `NEXTRM_WORKER_HEALTH_FILE` | API, Worker | Path to JSON worker heartbeat file (default: `/tmp/worker-health.json`). |
| `NEXTRM_POI_PROVIDER` | API | Nearby-business source: `synthetic` (seeded demo dataset, default) or `google` (Places API New). `google` without a key returns HTTP 503; it never falls back to synthetic. |
| `GOOGLE_MAPS_SERVER_KEY` | API | Server-side Places API (New) key. Inject from Secret Manager; restrict the key to the Places API. |
| `GOOGLE_MAPS_BROWSER_KEY` | Web | Maps JavaScript API key, served at runtime through `/api/config`. Public by design: restrict it to the web URL (HTTP referrer) and the Maps JavaScript API. Without it the acquisition page shows an honest "Google Maps is not configured" notice and stays usable as a list. |
| `GOOGLE_MAPS_MAP_ID` | Web | Map ID required for Advanced Markers (create one in Google Maps Platform → Map management). |

---

## 3. Public Evaluation Demo Deployment (`scripts/gcp/deploy-demo.sh`)

For hackathons, evaluation juries, and public demonstration, NextRM provides an automated deployment script that provisions a fully functional public demo on Google Cloud Run.

### Demo Architecture
- **Private API Service (`nextrm-api`):** Deployed to Cloud Run with `--no-allow-unauthenticated`. Accessible only to the web service via Google Cloud IAM. One to three instances share one Cloud SQL database (10 + 10 pooled connections each). The evaluation worker runs inside each container beside FastAPI (`scripts/gcp/demo-api-entrypoint.sh`) and claims runs through a database lease, so instances never duplicate work.
- **Cloud SQL for PostgreSQL (`nextrm-pg`):** PostgreSQL 17, Enterprise edition, `db-custom-1-3840` (1 vCPU, 3.75 GB), zonal, 10 GB SSD that grows automatically, `max_connections=100`, daily backups at 01:00 WIB with point-in-time recovery, deletion protection and encrypted connections only. The API connects through the built-in Cloud SQL connector (a unix socket under `/cloudsql`). The connection URL, including the generated password, lives in Secret Manager (`nextrm-database-url`) and is pinned by version at deploy.
- **Cloud Run Job (`nextrm-db-setup`):** Runs `alembic upgrade head` and the repeat-safe synthetic seed (`scripts/gcp/db-setup.sh`) and finishes before a new API revision takes traffic. The API never migrates at startup. Conversations, customer choices and RM requests persist across deploys and restarts.
- **Public Web Service (`nextrm-web`):** Deployed to Cloud Run with `--allow-unauthenticated`. Serves public traffic, hosts the `/demo` account chooser, and signs outbound API calls with its service account identity.
- **Vertex AI Gemini:** Authenticated via the API service account (`nextrm-api-sa`) with `roles/aiplatform.user`.

### Execution Steps
```bash
# 1. Authenticate with Google Cloud
gcloud auth login
gcloud auth application-default login

# 2. Set deployment parameters
export GCP_PROJECT_ID="your-gcp-project-id"
export GCP_REGION="asia-southeast1"
export GEMINI_LOCATION="asia-southeast1"
export GEMINI_MODEL="<model-id available in GEMINI_LOCATION>"

# 3. Optional: Google Maps Platform (create keys in Google Maps Platform → Keys & Credentials)
printf '%s' "$PLACES_SERVER_KEY" | gcloud secrets create maps-server-key --data-file=- --project="$GCP_PROJECT_ID"
export MAPS_SERVER_KEY_SECRET="maps-server-key"
export GOOGLE_MAPS_BROWSER_KEY="<browser key restricted to the web URL>"
export GOOGLE_MAPS_MAP_ID="<map id>"

# 4. Execute the automated demo deployment
./scripts/gcp/deploy-demo.sh
```

With `MAPS_SERVER_KEY_SECRET` set, the script enables the Places API and Secret Manager, grants the API service account access to that secret only, and deploys the API with `NEXTRM_POI_PROVIDER=google`. Without it the API uses the synthetic POI dataset. With `GOOGLE_MAPS_BROWSER_KEY` set it enables the Maps JavaScript API. After the first deploy, add the printed web URL to the browser key's HTTP referrer restriction. Places content is cached for at most 30 days (`poi_places.expires_at`) and shown with Google attribution.

### What `deploy-demo.sh` Performs:
1. First deploy only (or with `--setup`): enables the Google Cloud APIs, runs `scripts/gcp/bootstrap.sh` (Artifact Registry `nextrm-repo`, service accounts `nextrm-api-sa` and `nextrm-web-sa`) and `scripts/gcp/provision-sql.sh` (Cloud SQL instance, database, user, secret, `roles/cloudsql.client`), grants `roles/aiplatform.user` to `nextrm-api-sa`, and grants `roles/cloudbuild.builds.builder` to the project's default compute service account, which Cloud Build uses in new projects (without it the source upload fails with `storage.objects.get` denied).
2. Hashes the build inputs of each service. The hash is the image tag, so an existing tag means no build.
3. Runs two pipelines in parallel. API: Cloud Build with layer caching (`infra/cloudbuild-api.yaml`), then the `nextrm-db-setup` job only when migrations, models or seed inputs changed (`--db-setup` forces it), then `nextrm-api` with `NEXTRM_AI_PROVIDER=vertex`. Web: `next build` on your machine, packaged into a Node 20 image by Cloud Build (`infra/Dockerfile.web-prebuilt`; `--remote-web-build` compiles inside Cloud Build instead), then `nextrm-web` pointing at the internal API URL with `NEXTRM_DEMO_MODE=true`.
4. On the first deploy, grants `roles/run.invoker` on `nextrm-api` to `nextrm-web-sa`. This binding can take about a minute to propagate; until then the web proxy receives HTTP 403 from the API.
5. Prints the API and web URLs, image tags and elapsed time (for example `https://nextrm-web-...-as.a.run.app/demo`).

Verified configuration (17 Oct 2026): `GEMINI_MODEL=gemini-3.5-flash`, `GEMINI_LOCATION=asia-southeast1`, `GEMINI_THINKING_LEVEL=low`. `gemini-3.8-flash` and `gemini-3.1-flash-lite` were not served regionally in `asia-southeast1` for this project (HTTP 404) and are available only on `global`.

### Deploy Speed

Wall time of `scripts/gcp/deploy-demo.sh`, measured on 18 Oct 2026 against the public demo in `asia-southeast1`:

| Change | Time |
|---|---|
| Original script: two Cloud Build builds in series, setup calls on every run, migrate and seed at container start | 377 s |
| Web only | 100 s |
| API only, schema and seed unchanged | 90 s |
| API only, with a migration or seed change | 155 s |
| Redeploy of images that are already built (rollback, configuration change) | 32 s |

Both pipelines run in parallel, so a change to both takes about as long as the slower one. What made the difference: content-hash tags skip unchanged services; the one-time setup calls (APIs, IAM, registry) run only on the first deploy or with `--setup`; the API container no longer migrates and seeds at startup, the job does and only when needed; the web app compiles locally in about 30 s instead of about 90 s on a Cloud Build machine; and Cloud Build uses its default machine, because requesting `E2_HIGHCPU_8` added about 60 s of queueing per build.

### Operating the Demo Database

- **Cost:** Cloud SQL bills every hour the instance exists, independent of traffic. At the us-central1 list price (vCPU 0.0413 USD/hour, memory 0.007 USD per GiB-hour) `db-custom-1-3840` costs about 0.07 USD/hour, roughly 50 USD/month, before storage and backups; `asia-southeast1` is priced higher. Check <https://cloud.google.com/sql/pricing> and set a budget alert (budgets alert, they do not cap spending). Pause compute with `gcloud sql instances patch nextrm-pg --activation-policy=NEVER` (storage and backups keep billing) and resume with `ALWAYS`.
- **Backups:** daily automated backup (7 retained) and point-in-time recovery (7 days of logs). Restore into a new instance with `gcloud sql instances clone nextrm-pg nextrm-pg-restore --point-in-time=<UTC timestamp>`.
- **Verify a deployment:** `./.venv/bin/python scripts/gcp/smoke_demo.py https://<web-url>`. It makes one live Gemini call per chat turn and writes a few synthetic rows. `./.venv/bin/python scripts/top10_questions.py --url https://<web-url>` then asks the ten most common customer money questions as the demo customer, grades each live answer (figures, route, no investment advice) and checks that an RM handoff reaches the RM queue (measured on 18 Oct 2026: 10 of 10 live, 3.8 to 8.4 s each). It writes about a dozen synthetic chat turns; run the reset below afterwards.
- **Restore pristine demo data** (before recording or judging): `scripts/gcp/reset-demo-data.sh --yes` drops every object owned by the application role, then migrates and reseeds. Synthetic data only.
- **Roll back traffic:** `gcloud run revisions list --service nextrm-api --region $GCP_REGION`, then `gcloud run services update-traffic nextrm-api --to-revisions=<revision>=100`. Traffic changes never undo migrations, which are additive. Revisions created before the Cloud SQL cutover use the retired SQLite configuration and must not be used for rollback.
- **Delete:** deletion protection is on. Run `gcloud sql instances patch nextrm-pg --no-deletion-protection`, then `gcloud sql instances delete nextrm-pg`. A deleted instance name cannot be reused for about a week.

---

## 4. Production Deployment Path (`scripts/gcp/deploy.sh`)

For enterprise production deployments, NextRM connects to Cloud SQL (PostgreSQL), Google Secret Manager, and Firebase Authentication, with synthetic demo modes disabled.

### Production Architecture
- **Cloud Run Job (`nextrm-migrate`):** Executes database migrations (`alembic upgrade head`) before application traffic is routed.
- **Cloud SQL for PostgreSQL:** Managed database instance with automated backups, point-in-time recovery, and private IP or Cloud SQL connector.
- **Google Secret Manager:** Secure storage of the database connection string (`DATABASE_URL`) and server credentials.
- **Firebase Authentication:** Production end-user identity. The `/demo` persona chooser is disabled.

### Execution Steps
```bash
# 1. Configure production environment parameters
export GCP_PROJECT_ID="your-authorized-project-id"
export GCP_REGION="asia-southeast1"
export CLOUD_SQL_CONNECTION_NAME="${GCP_PROJECT_ID}:asia-southeast1:nextrm-pg"   # created by scripts/gcp/provision-sql.sh
export DATABASE_SECRET_VERSION="nextrm-database-url:1"                           # SECRET:VERSION, pinned rather than latest
export FIREBASE_WEB_API_KEY="your-public-firebase-web-api-key"
export IMAGE_TAG="$(date +%Y%m%d-%H%M%S)"

# 2. Execute production deployment
./scripts/gcp/deploy.sh
```

### Preflight and Verification Scripts
- **Preflight Check (`scripts/gcp/preflight.sh`):** Validates that all required environment variables, gcloud CLI tools, and IAM permissions exist before build execution.
- **Bootstrap (`scripts/gcp/bootstrap.sh`):** Creates Artifact Registry repositories, service accounts, and IAM role bindings safely and idempotently.
- **Smoke Tests (`scripts/gcp/smoke-test.sh`):** Verifies that the deployed web and API services respond correctly to authenticated health probes and canary turns.

---

## 5. Google Cloud Ecosystem Mapping

The following table details how NextRM responsibilities map to Google Cloud services:

| Architectural Responsibility | Google Cloud Destination | Production Implementation |
|---|---|---|
| **Governed Model Orchestration** | Gemini on Vertex AI | Invocations via `google-genai` SDK using workload identity. Temperature 0 with strict Pydantic schemas. |
| **Application Hosting** | Cloud Run | Independent auto-scaling containers for public web and private API. |
| **Relational Data & Audit Store**| Cloud SQL (PostgreSQL) | Multi-tenant persistence for parties, signals, journeys, governance releases, and audit logs. |
| **Secret & Key Management** | Google Secret Manager | Database URLs and external keys stored as versioned secrets. |
| **End-User Authentication** | Firebase Authentication | Cryptographically verified JWTs mapped to institution user assignments. |
| **Service-to-Service Security** | Cloud Run IAM & OIDC | Web service account invokes private API via signed Google ID tokens. |
| **Durable Async Evaluation** | Cloud Run Job / Worker | Standalone worker processing batch evaluation suites without affecting turn latency. |
| **Event Pipeline (Planned)** | Google Cloud Pub/Sub | Scalable ingestion for core-banking activity and customer event feeds. |
| **Long-Term Analytics (Planned)**| BigQuery | Redacted aggregate telemetry and model performance reporting. |
| **Document Ingestion (Planned)** | Document AI | Structured extraction of customer statements and financial documents. |
| **Knowledge Retrieval (Planned)** | Vertex AI Search | Enterprise document search over approved banking policy catalogs. |
