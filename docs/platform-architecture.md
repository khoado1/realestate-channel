# Platform architecture — SaaS conversion

Status: whiteboard / pre-implementation. This doc records the architecture decisions made while
scoping the conversion of this repo's single-user Python content pipeline into a multi-tenant,
multi-user, workflow-driven SaaS product with web/desktop/mobile clients.

## 1. Decisions log

| Area | Decision | Rationale / notes |
|---|---|---|
| Workflow engine | **Temporal** | Durable execution, retries, and human-in-the-loop pauses (review gates) come for free instead of hand-rolled. |
| Multi-tenancy | **Hybrid**: shared schema + Postgres RLS by default, dedicated database per tenant as an opt-in | Most tenants don't need hard isolation; security-conscious tenants can opt into a dedicated DB without forking the schema. |
| Repo strategy | **Polyrepo** (backend + one repo per client) | Simpler ownership per client; requires a shared API contract (OpenAPI/protobuf) so clients don't drift from the backend. |
| Object storage | **Self-hosted MinIO** (S3-compatible API) for now | Lets us test without committing to a cloud vendor; swappable to Cloudflare R2/S3/B2 later since the API is S3-compatible. Shared bucket, tenant-prefixed keys, presigned URLs for upload/download. |
| Auth | **WorkOS** (managed) | Pricing is per-company/connection rather than per-MAU, which fits an org/tenant-shaped (B2B) product better than Clerk/Auth0/Supabase's per-MAU models. Free up to 1M MAU. |
| Credential/secrets storage | **Encrypted columns in Postgres** (no Vault) | Vault (Community or Enterprise) adds real ops overhead (unseal keys, HA, storage backend) that isn't justified at current scale. Revisit only if a tenant requires it for compliance. |
| Social platforms | **YouTube first, TikTok later** | Scopes the first Integration/publish provider implementation. |
| Deployment target | **Self-hosted, Docker Compose (dev) / Kubernetes (prod)** on our own infrastructure | No managed-cloud-compute dependency; matches the self-hosted-storage/self-hosted-secrets choices above. |
| Backend language/framework (core) | **Java / Spring Boot** | Chosen over the original Python plan (and over C#/.NET) to credibly demonstrate enterprise-grade, DDD/component-based/event-driven architecture to investors and traditional-enterprise consulting prospects (healthcare/insurance/banking, which run Java/.NET internally) — Spring's DI container, module conventions, and idioms (Spring Modulith, Axon for CQRS/event sourcing) give this natively, where Python's equivalent is assembled rather than idiomatic. Java over C#: broader enterprise vertical footprint (esp. finance/banking) and larger long-term hiring pool. API layer: **Spring Boot (Spring MVC)**. Data layer: **Spring Data JPA/Hibernate + Flyway** for the Postgres model + migrations. Shared API contract for the polyrepo clients: **springdoc-openapi** (auto-generates OpenAPI from controllers, same role FastAPI would have played). Validation: **Jakarta Bean Validation**. Orchestration: **Temporal Java SDK**. |
| Backend language (AI/media workers) | **Python**, kept for the research/script/voice/video Temporal activities | The existing `scripts/providers/` registry and pipeline scripts (`research.py`, `script.py`, `generate_voice.py`, `generate_video.py`, `repurpose.py`) get promoted into a Python worker service rather than rewritten — AI/media provider SDKs ship Python-first, and the workload here is I/O-bound so the GIL doesn't matter. Wired to the Java orchestrator via **Temporal's native cross-language worker support**: the `ContentPipelineWorkflow` (Java) invokes these activities on shared task queues regardless of implementation language. |
| CI/CD | **GitHub Actions** + **GHCR** (container registry) + **ArgoCD** (GitOps deploy to k8s) | GitOps fits the self-hosted k8s target — audit trail and drift detection instead of CI pushing directly. Each polyrepo client repo builds its own artifact independently (web static build, desktop installer per OS, mobile store build); the backend repo builds/pushes images and lets ArgoCD reconcile the cluster. |
| Observability | Self-hosted **Grafana stack**: Prometheus (metrics) + Loki (logs) + Tempo (traces, via OpenTelemetry) + Grafana (dashboards/alerting via Alertmanager) | All self-hostable and integrate with each other and with k8s. Temporal's own Web UI still gives per-workflow/activity visibility; `temporal_workflow_id`/`temporal_activity_id` on WorkflowRun/StepRun cross-link app UI to it. |
| Billing/subscription | Deferred integration; **usage-based metering tied to StepRun volume** is the intended shape when it's built, using **Stripe Billing** as the processor | AI provider calls cost real money per use, so usage-based (vs. seat/flat) protects margin. Not modeled in the schema yet beyond the `Organization` entity being the natural anchor for a future `subscription`/`plan` relation. |
| Desktop client | **Tauri** wrapper (not Electron) | Local file access is required (importing raw footage, exporting renders), which rules out a plain web wrapper. Tauri's Rust shell uses the OS-native webview (smaller binary than Electron) and has a fine-grained filesystem permission model. Electron remains the fallback if a needed native integration is missing from Tauri's plugin ecosystem. |
| Mobile client scope | **Review/approve + analytics only**, no authoring | Confirmed — running research/script/voice/video generation from a phone isn't the workflow; mobile is for approving pending StepRuns and checking AnalyticsSnapshot data. |

## 2. Component recap

- **API layer** — auth (WorkOS), CRUD for Projects/Workflows/Assets, run-triggering, review/approve endpoints.
- **Temporal orchestrator** — one Temporal Workflow per WorkflowRun; one Activity per Step. Handles retries and pause-for-review.
- **Workers** — Temporal worker processes, one activity implementation per step type (research, script, voice, video, repurpose, publish, analytics). These wrap the logic currently in `scripts/research.py`, `scripts/script.py`, `scripts/generate_voice.py`, `scripts/generate_video.py`, `scripts/repurpose.py`, `scripts/analytics.py`.
- **Provider plugin layer** — extension of the existing `scripts/providers/` registry pattern (`base.py`, `registry.py`, `claude.py`, `http.py`) to cover AI text/voice/video providers and, later, social-publish providers.
- **Storage** — Postgres (relational + workflow state), MinIO (media assets).
- **Clients** — web (primary control plane), desktop (Tauri wrapper, needs local file access), mobile (review/approve + analytics, not full authoring).

## 3. Data model

### Entities

- **Organization** — tenant boundary; billing and isolation-mode lives here.
- **User** / **OrganizationMember** — identity (via WorkOS) and org membership with role.
- **Project** — one "channel" within an org (this repo today = exactly one Project).
- **Workflow** / **WorkflowStepDefinition** — a named, versioned sequence of step definitions a Project can run.
- **WorkflowRun** — one execution of a Workflow, tied to a Temporal workflow execution.
- **StepRun** — one execution of a single step within a run, tied to a Temporal activity execution.
- **Asset** — any produced artifact (script, voiceover, video, image, social post copy), versioned.
- **Integration** — encrypted credentials for an AI provider or social platform, scoped to org or project.
- **SocialAccount** — a specific connected channel/account on a platform (e.g. one YouTube channel), backed by an Integration.
- **PublishedPost** — links an Asset to where/when it was published.
- **AnalyticsSnapshot** — metrics pulled back for a PublishedPost over time.

### ERD

```mermaid
erDiagram
    ORGANIZATION ||--o{ ORGANIZATION_MEMBER : has
    USER ||--o{ ORGANIZATION_MEMBER : has
    ORGANIZATION ||--o{ PROJECT : owns
    ORGANIZATION ||--o{ INTEGRATION : owns
    PROJECT ||--o{ WORKFLOW : defines
    WORKFLOW ||--o{ WORKFLOW_STEP_DEFINITION : contains
    WORKFLOW ||--o{ WORKFLOW_RUN : executes_as
    WORKFLOW_RUN ||--o{ STEP_RUN : contains
    WORKFLOW_STEP_DEFINITION ||--o{ STEP_RUN : instantiates
    STEP_RUN ||--o| ASSET : produces
    PROJECT ||--o{ ASSET : owns
    PROJECT ||--o{ SOCIAL_ACCOUNT : connects
    INTEGRATION ||--o{ SOCIAL_ACCOUNT : backs
    ASSET ||--o{ PUBLISHED_POST : published_as
    SOCIAL_ACCOUNT ||--o{ PUBLISHED_POST : receives
    PUBLISHED_POST ||--o{ ANALYTICS_SNAPSHOT : tracked_by
```

### Table sketch

```
Organization
  id (uuid, pk)
  name
  isolation_mode        enum(shared, dedicated)
  dedicated_db_ref       text, nullable   -- secret reference, not a raw connection string
  created_at, updated_at

OrganizationMember
  id (uuid, pk)
  org_id       fk -> Organization
  user_id      fk -> User
  role         enum(owner, admin, editor, viewer)
  created_at

User
  id (uuid, pk)
  workos_user_id   text, unique
  email
  name
  created_at, updated_at

Project
  id (uuid, pk)
  org_id       fk -> Organization   -- tenant column, RLS-enforced
  name
  slug
  channel_config   jsonb   -- voice/tone/provider defaults
  created_at, updated_at

Workflow
  id (uuid, pk)
  org_id       fk -> Organization   -- tenant column
  project_id   fk -> Project
  name
  version      int
  is_active    bool
  created_at, updated_at

WorkflowStepDefinition
  id (uuid, pk)
  workflow_id      fk -> Workflow
  order_index      int
  step_type        enum(research, script, voice, video, repurpose, publish, analytics)
  config           jsonb   -- provider selection + step-specific settings
  requires_review  bool    -- human-in-the-loop gate before advancing
  created_at, updated_at

WorkflowRun
  id (uuid, pk)
  org_id                 fk -> Organization   -- tenant column
  project_id             fk -> Project
  workflow_id            fk -> Workflow
  temporal_workflow_id   text
  status        enum(pending, running, paused_for_review, completed, failed, cancelled)
  triggered_by  fk -> User, nullable   -- null if scheduled/automated
  started_at, completed_at
  created_at, updated_at

StepRun
  id (uuid, pk)
  org_id                  fk -> Organization   -- tenant column
  workflow_run_id         fk -> WorkflowRun
  step_definition_id      fk -> WorkflowStepDefinition
  step_type               enum(...)   -- denormalized for fast filtering
  temporal_activity_id    text, nullable
  status         enum(pending, running, awaiting_review, approved, rejected, completed, failed, retrying)
  output_asset_id  fk -> Asset, nullable
  error_message    text, nullable
  attempt_count    int
  started_at, completed_at
  created_at, updated_at

Asset
  id (uuid, pk)
  org_id         fk -> Organization   -- tenant column
  project_id     fk -> Project
  step_run_id    fk -> StepRun, nullable   -- null for user-uploaded raw inputs
  asset_type     enum(script, voiceover, video, image, social_post, thumbnail, transcript)
  storage_bucket text
  storage_key    text
  mime_type      text
  version        int
  status         enum(draft, in_review, approved, published, archived)
  metadata       jsonb   -- duration, resolution, word count, etc.
  created_by     fk -> User, nullable
  created_at, updated_at

Integration
  id (uuid, pk)
  org_id          fk -> Organization   -- tenant column
  project_id      fk -> Project, nullable   -- null = org-level, set = project-level override
  provider_type   enum(ai_text, ai_voice, ai_video, social_platform)
  provider_name   text   -- "claude", "elevenlabs", "youtube", "tiktok"
  credential_encrypted            bytea
  oauth_refresh_token_encrypted   bytea, nullable
  oauth_expires_at                timestamptz, nullable
  created_at, updated_at

SocialAccount
  id (uuid, pk)
  org_id               fk -> Organization   -- tenant column
  project_id           fk -> Project
  platform             enum(youtube, tiktok)
  external_account_id  text
  integration_id       fk -> Integration
  created_at, updated_at

PublishedPost
  id (uuid, pk)
  org_id             fk -> Organization   -- tenant column
  asset_id           fk -> Asset
  social_account_id  fk -> SocialAccount
  platform_post_id   text
  status             enum(scheduled, published, failed, removed)
  published_at
  created_at, updated_at

AnalyticsSnapshot
  id (uuid, pk)
  org_id              fk -> Organization   -- tenant column
  published_post_id   fk -> PublishedPost
  captured_at         timestamptz
  metrics             jsonb   -- views, watch_time, likes, retention_30s, etc.
  created_at
```

Every tenant-scoped table carries `org_id` so RLS policies can enforce isolation uniformly; the
`Organization.isolation_mode` + `dedicated_db_ref` pair is what the connection-resolver layer reads
to decide whether a query for that org routes to the shared pool or a dedicated database.

## 4. Multi-tenancy implementation notes

- Data-access layer needs a **tenant-aware connection resolver**: look up `Organization.isolation_mode`
  before issuing a query; shared-mode orgs go through the shared pool with RLS (`org_id = current_setting('app.org_id')`),
  dedicated-mode orgs are routed to their own connection (secret pulled from the encrypted credential store, not Vault).
- Migrations must run against the shared DB and fan out across every dedicated DB.
- Provisioning a dedicated DB for a tenant is itself a good candidate for a Temporal workflow
  (create DB, run migrations, store connection secret, flip `isolation_mode`).

## 5. Local dev / self-hosted stack

Services needed for a local Docker Compose environment, based on the decisions above:

- Postgres (shared-tenant DB; dedicated-tenant DBs can be additional containers/instances in dev)
- MinIO (S3-compatible object storage)
- Temporal server + Temporal Web UI
- Backend API service
- Temporal worker service(s) — one process type per step-type group, or one worker binary handling all activity types initially

Production target is the same service set running on Kubernetes rather than Compose.

## 6. Temporal workflow/activity structure

### Parent workflow

One workflow type, `ContentPipelineWorkflow`, per `WorkflowRun`. It orchestrates control flow only —
every DB write and every external API call happens inside an Activity, since Temporal workflow code
must stay deterministic.

The orchestrator (this workflow) is **Java**, running on Temporal's Java SDK. The research/script/voice/
video activities it calls are implemented by a separate **Python** worker via Temporal's cross-language
support — same task queues, same activity type names/JSON serialization, no shared code required.

```java
@WorkflowInterface
public interface ContentPipelineWorkflow {
    @WorkflowMethod
    void run(String workflowRunId);

    @SignalMethod
    void approveStep(String stepRunId);

    @SignalMethod
    void rejectStep(String stepRunId, String reason);
}

public class ContentPipelineWorkflowImpl implements ContentPipelineWorkflow {
    private final Map<String, String> reviewDecisions = new HashMap<>(); // stepRunId -> "approved" | "rejected"

    private final PipelineActivities controlActivities = Workflow.newActivityStub(
        PipelineActivities.class,
        ActivityOptions.newBuilder().setStartToCloseTimeout(Duration.ofMinutes(1)).build()
    );

    @Override
    public void run(String workflowRunId) {
        List<StepDefinition> stepDefs = controlActivities.loadStepDefinitions(workflowRunId);

        for (StepDefinition stepDef : stepDefs) {
            String stepRunId = controlActivities.createStepRun(workflowRunId, stepDef.id());

            // routed to the step type's own task queue (research-tq, voice-tq, ...) so the
            // Python worker pool serving that queue picks it up regardless of orchestrator language
            PipelineActivities stepActivities = Workflow.newActivityStub(
                PipelineActivities.class,
                ActivityOptions.newBuilder()
                    .setTaskQueue(STEP_TASK_QUEUE.get(stepDef.stepType()))
                    .setStartToCloseTimeout(Duration.ofMinutes(30))
                    .setRetryOptions(RetryOptions.newBuilder()
                        .setMaximumAttempts(5)
                        .setDoNotRetry("InvalidCredentialsException", "ContentPolicyException")
                        .build())
                    .build()
            );
            stepActivities.runStep(stepDef.stepType(), stepRunId);

            if (stepDef.requiresReview()) {
                controlActivities.markAwaitingReview(stepRunId);
                Workflow.await(() -> reviewDecisions.containsKey(stepRunId));
                if ("rejected".equals(reviewDecisions.remove(stepRunId))) {
                    controlActivities.markRunFailed(workflowRunId);
                    return;
                }
            }

            controlActivities.markStepCompleted(stepRunId);
        }

        controlActivities.markRunCompleted(workflowRunId);
        controlActivities.scheduleAnalyticsPolling(workflowRunId);
    }

    @Override
    public void approveStep(String stepRunId) {
        reviewDecisions.put(stepRunId, "approved");
    }

    @Override
    public void rejectStep(String stepRunId, String reason) {
        reviewDecisions.put(stepRunId, "rejected");
    }
}
```

- `WorkflowRun.temporal_workflow_id` is set deterministically (e.g. `content-run-{workflow_run_id}`) so
  the API can always map a DB row to its Temporal execution and vice versa.
- Review gates use `Workflow.await(...)` on a signal — the workflow blocks durably (no polling, no cost
  while waiting) until the API delivers `approveStep`/`rejectStep` in response to a user action in the
  web/mobile client.
- Retries are handled by Temporal's built-in `RetryOptions` per activity — `StepRun.attempt_count` just
  mirrors Temporal's own attempt counter for display, the app doesn't implement retry logic itself.
  Errors like bad credentials or a content-policy rejection are raised as non-retryable so they fail
  straight to `awaiting_review`/`failed` instead of burning retry attempts.

### Activities (one per step type)

| step_type | Activity | Implemented by | Wraps existing script |
|---|---|---|---|
| research | `runStep("research", ...)` | Python worker | `scripts/research.py` |
| script | `runStep("script", ...)` | Python worker | `scripts/script.py` |
| voice | `runStep("voice", ...)` | Python worker | `scripts/generate_voice.py` |
| video | `runStep("video", ...)` | Python worker | `scripts/generate_video.py` |
| repurpose | `runStep("repurpose", ...)` | Python worker | `scripts/repurpose.py` |
| publish | `runStep("publish", ...)` | Java worker | new — YouTube/TikTok publish provider |

`controlActivities` (load/create/mark-status calls) run on the Java side, close to the database, since
they're plain persistence operations with no AI/media provider dependency — no reason to cross the
language boundary for those. `publish` runs on the Java side too: it's not an AI/media generation step,
just an API call to YouTube/TikTok plus writing a `PublishedPost` row, so it stays with the core rather
than crossing into the Python worker.

Each activity is assigned its own **task queue** (`research-tq`, `script-tq`, `voice-tq`, `video-tq`, ...)
so worker pools can scale independently per step type later (e.g. more video workers than research
workers) without changing workflow code — a single worker binary can still serve every task queue to
start, per the local-dev stack in section 5.

### Analytics is a separate, decoupled workflow

Analytics doesn't fit the linear step model — it's a recurring pull over time (multiple
`AnalyticsSnapshot` rows per `PublishedPost`), not a one-shot generate-and-stop step. Rather than
keeping the parent `ContentPipelineWorkflow` alive to poll, it hands off:

- `schedule_analytics_polling` (called once, after publish succeeds) creates a **Temporal Schedule**
  — one per `PublishedPost` — that starts an `AnalyticsPollingWorkflow` on a recurring interval
  (e.g. daily) for a bounded window (e.g. 30 days), then auto-deletes itself.
- Each `AnalyticsPollingWorkflow` run is a single activity call: fetch metrics from the platform API,
  write one `AnalyticsSnapshot` row.
- This keeps the parent `ContentPipelineWorkflow`'s history short-lived and bounded (it completes once
  publish succeeds) instead of needing `continue-as-new` to stay alive indefinitely for analytics.

## 7. Product tiers and target audiences

Two target audiences, confirmed as both in scope: **agencies/teams** and a **determined solo user**.
The multi-tenant data model already supports both without a fork — a solo user is just an
`Organization` with one `OrganizationMember` and one `Project`; an agency is an `Organization` with
many members, many Projects, and role-based access (`OrganizationMember.role`: owner/admin/editor/viewer).
What differs is the value story and which features are worth gating, not the underlying architecture.

### Solo user

- **Value story**: labor replacement — one person doing research, script, voice, video, publish, and
  analytics work that would otherwise take a small team.
- **Price sensitivity**: high — they compare cost against their own time, not a department budget.
- **Doesn't need**: audit trail (they're the only approver), cross-project rollups (they have one Project).

### Agency/team

- **Value story**: scaled quality control — knowing every piece of content published under the
  agency's name cleared a compliance-aware review gate, and knowing which channel/loan officer's
  content is actually working so the pattern can be replicated across the team.
- **Price anchor**: compliance/quality-control value, not "cheaper than hiring help" — a different
  number than the solo tier, not one price trying to work for both.
- **Team-specific features worth building as the paid tier**:
  - **Role-gated approval** — extend `WorkflowStepDefinition.requires_review` (currently a flat
    boolean) to specify *which role* must approve a given step, so e.g. only an "admin" can approve
    the publish step rather than any org member.
  - **Cross-project analytics rollup** — a dashboard aggregating `AnalyticsSnapshot` across every
    `Project` in an `Organization`, surfacing which channel/loan officer is outperforming the others.
    Meaningless for a solo user with a single Project.
  - **Audit trail export** — surfacing the `StepRun` review history (who approved what, when) as a
    compliance artifact, not just internal workflow-engine bookkeeping.

### Sequencing relative to monetization

Both audiences get the core pipeline free/cheap long enough to feel the value (compliance-aware
generation, the analytics-informed feedback loop) before any payment ask — "keep the thing that's
already been working for you" sells better than pricing upfront. The team-specific features above
are the natural paid tier for agencies once that ask comes.

**Decision: split timing strategy per audience**, rather than one blanket policy:

- **Solo tier — permanent freemium (option C)**: free/cheap forever with capped usage (protects
  AI-provider cost exposure regardless of billing timing), no artificial trial deadline. The paywall is
  the team-tier feature set above, not a calendar date — "when to start monetizing solo users" resolves
  itself as "whenever those features ship," not as a date to schedule.
- **Agency tier — design-partner pilot (option E)**: free or heavily discounted access for a small
  cohort of agencies in exchange for feedback, specifically to validate the compliance/audit-trail value
  proposition before setting real team-tier pricing. Closer to a consulting/enterprise sales motion than
  self-serve, which fits how agencies actually evaluate and buy software better than a time-boxed trial
  would.

Rejected for now: charging from day one (option B, too much adoption risk before the product's proven),
a blanket free-beta-then-flip-the-switch policy (option A, doesn't distinguish the two audiences' buying
behavior), and a standard time-boxed trial (option D, natural fit for the solo tier but not for agencies,
who want a longer, relationship-based pilot before committing budget).

## 8. Future direction — explicitly deferred, not driving current design

Idea considered: generalize this platform's infrastructure (multi-tenant, project-oriented, workflow-driven,
multi-client) into a reusable "cookie-cutter" template — a system for building other systems, in the vein
of OutSystems or Salesforce's Force.com platform, that could be white-labeled into other verticals beyond
real estate/lending content (e.g. the hospital billing example this came from).

**Decision: not now.** Companies that succeeded at "one platform, many verticals" (Salesforce, Monday.com,
Airtable, Notion) generalized *after* nailing one vertical first — the generic engine emerged from
refactoring what already worked for real customers, not from architecting generically against
hypothetical future products. Building the reusable template before this product has one real customer
means designing abstractions against guesses instead of requirements, and directly conflicts with this
project's own stated engineering principle of not designing for hypothetical future requirements.

Nothing currently designed forecloses this direction later: Temporal + the `Organization`/`Project`/
`Workflow`/`StepRun` schema + the provider-registry plugin pattern is already the right shape for a
future multi-vertical substrate. The one genuinely vertical-specific piece is `step_type`/`asset_type`
being a fixed enum rather than a pluggable metadata layer — a contained change to make later, if and when
a real second vertical asks for it, not a speculative one to make now.

## 9. Open questions (not yet decided)

None currently — every decision point raised in this whiteboard session is recorded above. Revisit this
section as new questions surface during implementation.
