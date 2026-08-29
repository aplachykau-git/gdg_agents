# Future Development Plan
## Community AI Studio — Roadmap & Technical Debt

> **Document Version:** 1.0.0
> **Status:** Living Document
> **Audience:** Lead Engineers, Platform Architects

---

## Overview

This document captures identified gaps between the approved architecture baseline and the current implementation, plus the Phase 2 roadmap. Items are ordered by risk impact, not complexity.

```mermaid
mindmap
  root((Future Work))
    Critical Gaps
      GCS 60-day Lifecycle Rule
      Cloud Run Autoscaling Config
      Rate Limiting & Quota Guard
      Session Persistence
    Security Hardening
      Guardrails & Input Validation
      Drive OAuth Model Decision
      Firebase App Check Enforcement
    Phase 2 Features
      Multi-Tenancy
      RBAC
      RAG Memory
      Audit Logging
    Observability
      Distributed Tracing
      Cost Attribution
      SLO Dashboards
```

---

## 1. Critical Infrastructure Gaps

### 1.1 GCS Lifecycle Rule — 60-Day Auto-Delete (NFR-04.1)

**Current state:** `terraform/storage.tf` creates the bucket with no lifecycle rule. Storage grows unbounded.

**Fix:** Add to `google_storage_bucket.assets_bucket`:

```hcl
lifecycle_rule {
  condition { age = 60 }
  action    { type = "Delete" }
}
```

**Effort:** 30 minutes. Zero risk — only affects objects older than 60 days.

---

### 1.2 Cloud Run Concurrency & Autoscaling (NFR-01.2)

**Current state:** `terraform/cloudrun.tf` sets no concurrency or instance scaling annotations. All three services use Cloud Run defaults (80 concurrency, unbounded instances).

**Target configuration** (derived from load model below):

| Service | `max_concurrency` | `min_instance_count` | `max_instance_count` |
|:---|:---:|:---:|:---:|
| `community-root-agent` | 80 | 0 | 2 |
| `video-editor-a2a` | 2 | 0 | 4 |
| `receipt-scanner-a2a` | 10 | 0 | 2 |

**Load model (Europe organizer-tool traffic, not participant traffic):**
- Baseline: ~25 sessions/day; peak burst (conference season) = 5× → 125 sessions/day
- Spread over 8h workday, ~20min session duration → **~15 concurrent sessions at burst peak**
- Safety margin: **2× peak** (standard for non-critical stateless services)

| Service | Peak concurrent | × 2× safety | Per-instance capacity | Max instances |
|:---|:---:|:---:|:---:|:---:|
| `community-root-agent` | 15 SSE streams | 30 | 80 concurrency | 2 |
| `video-editor-a2a` | 3 renders (20% of sessions) | 6 | 2 concurrency | 4 (+1 cold-start) |
| `receipt-scanner-a2a` | 5 OCR jobs (30% of sessions) | 10 | 10 concurrency | 2 |

**Fix:** Add `scaling` block and `max_instance_request_concurrency` to each service template in `cloudrun.tf`:

```hcl
template {
  scaling {
    min_instance_count = 0
    max_instance_count = 75
  }
  max_instance_request_concurrency = 2
  ...
}
```

**Risk note:** At max=4 instances × concurrency=2, maximum simultaneous Veo API calls = 8. Verify Veo API quota supports this before deploying.

---

### 1.3 Video Render Quota (NFR-02.2)

**Current state:** No render quota exists. A single session can trigger unlimited video renders, exhausting `video-editor-a2a` Cloud Run compute.

**Quota principle:** Only limit features that cost the platform (Cloud Run compute for video rendering). Do not limit LLM usage — BYOK means the user's own API key absorbs those costs and Google's own quota enforcement applies.

**Target limit:** Max 5 video renders per session.

**Implementation:** Session state counter in root agent — zero infra required.

```python
# In agents/root_agent/agent.py, before delegating to video-editor-a2a:
render_count = tool_context.session.state.get("video_render_count", 0)
if render_count >= 5:
    return "Video render limit reached for this session (max 5)."
tool_context.session.state["video_render_count"] = render_count + 1
```

**Limitation:** Counter is in-memory and resets on Cloud Run instance restart. Acceptable — "per session" is inherently ephemeral. If persistent enforcement is needed later, move counter to Firestore keyed by `session_id`.

---

### 1.4 Session State Persistence (NFR-04.2)

**Current state:** ADK uses in-memory session state. Session history is lost when a Cloud Run instance restarts or scales to zero.

**Impact:** Users lose conversation context between sessions; no cross-session memory; state inconsistency during scale-out.

**Requirements:** Session state backed by GCS objects (`gs://${project_id}-storage/sessions/`) or Serverless Redis (Upstash) with 60-day TTL.

**Options:**

```mermaid
flowchart TD
    subgraph GCS_Option["GCS-backed sessions (simpler)"]
        G1["ADK custom SessionService\nreads/writes JSON to GCS"]
        G2["Natural 60-day TTL\naligns with existing lifecycle rule"]
        G3["Higher latency per turn\n(GCS object read on every request)"]
        G1 --- G2 --- G3
    end

    subgraph Redis_Option["Upstash Serverless Redis (recommended)"]
        R1["ADK InMemorySessionService\n+ Upstash Redis as external TTL store"]
        R2["Sub-10ms session reads"]
        R3["True serverless pay-per-request\n$0 idle cost"]
        R4["Requires UPSTASH_URL + UPSTASH_TOKEN\nin Cloud Run env vars"]
        R1 --- R2 --- R3 --- R4
    end
```

**Action items:**
- Provision Upstash Redis instance (or use GCS alternative)
- Implement `RedisSessionService` adapter wrapping ADK `BaseSessionService`
- Wire into `agents/root_agent/agent.py` initialization
- Add `UPSTASH_REDIS_URL` and `UPSTASH_REDIS_TOKEN` secret vars to `terraform/cloudrun.tf` (via `google_secret_manager_secret`)

---

## 2. Security Hardening

### 2.1 Agent Guardrails & Input Validation

**Current state:** No input sanitization or output guardrails exist on agent prompts. The system trusts all user input passed directly to Gemini.

**Identified risks:**

```mermaid
flowchart LR
    subgraph THREATS["Threat Vectors"]
        PI["Prompt Injection\nUser crafts input to override\nagent instructions"]
        LE["LLM Exfiltration\nAgent leaks session state\nor system prompt"]
        PII["PII Leakage\nRegistration roster data\nin chat output"]
        RL["Resource Exhaustion\nUnbounded tool loops\nor recursive delegation"]
    end

    subgraph MITIGATIONS["Required Mitigations"]
        M1["Input sanitization layer\nbefore prompt construction"]
        M2["Output filter on chat messages\n(regex + Gemini safety settings)"]
        M3["Max tool call depth limit\nper agent turn"]
        M4["registration_manager output\nforced to DOCX card only"]
    end

    PI --> M1
    LE --> M2
    PII --> M4
    RL --> M3
```

**Implementation targets:**
- `agents/common/guardrails.py` — shared sanitizer + output filter module
- Per-agent `max_tool_calls` parameter in ADK agent config
- Extend `registration_manager` agent instruction to enforce DOCX-only output (currently enforced by prompt — should be enforced by code)
- Enable Gemini safety settings: `HARM_BLOCK_THRESHOLD_UNSPECIFIED → BLOCK_LOW_AND_ABOVE` for harassment/hate categories

**Priority: HIGH** — PII redaction is partially enforced by prompt instruction only. Code-level enforcement is needed before production traffic.

---

### 2.2 Google Drive Auth Model Clarification (FR-03.3 / GAP-05)

**Current implementation:** SA-sharing model — users share their Drive folder with `studio_sa` email; SA authenticates via ADC workload identity.

**Requirements specify:** Incremental OAuth `drive.file` scope delegation at sign-in.

These are fundamentally different trust models:

```mermaid
flowchart TD
    subgraph SA_MODEL["Current: SA Sharing Model"]
        A1["User manually shares folder\nwith SA email in Drive UI"]
        A2["SA uses ADC workload identity\nto access any shared file"]
        A3["Simpler auth\nNo OAuth consent flow"]
        A4["Risk: SA has broad access\nto all shared folders across users"]
        A1 --> A2 --> A3
        A2 --> A4
    end

    subgraph OAUTH_MODEL["Required: OAuth drive.file Delegation"]
        B1["Firebase Auth requests\ndrive.file scope at sign-in"]
        B2["User grants consent\nfor specific files only"]
        B3["Token stored per user\nUsed to write to their Drive"]
        B4["Safer: user controls exactly\nwhich files SA can access"]
        B1 --> B2 --> B3 --> B4
    end
```

**Decision required from stakeholder:** The SA-sharing model is live and working. Migrating to OAuth delegation requires:
- Firebase Auth scope update (`auth/drive.file` added to sign-in provider)
- Token storage and refresh in the backend (cannot use ADC; need per-user `google.oauth2.credentials.Credentials`)
- Significant changes to `agents/receipt_scanner/google_auth.py` and `tools.py`

**Decision:** Keep SA-sharing for Phase 1. Implement OAuth delegation in Phase 2 alongside RBAC. **Priority: Low.**

---

### 2.3 Firebase App Check Enforcement Gaps

**Current state:** App Check is initialized in `frontend/src/lib/firebase.js` with reCAPTCHA v3. However, App Check enforcement is only effective if the backend Cloud Run service validates App Check tokens.

**Current gap:** The root agent (`adk api_server`) does not validate Firebase App Check tokens. A user with direct access to the Cloud Run URL can bypass App Check entirely.

**Fix options:**
- Add Firebase Admin SDK App Check token verification middleware to `adk api_server` startup
- Or use Firebase Hosting rewrites exclusively and block direct Cloud Run URL access via `ingress=internal-and-cloud-load-balancing` (requires adding a load balancer — adds cost)

---

## 3. Phase 2 Roadmap

### 3.1 Multi-Tenancy (Organization Workspaces)

```mermaid
flowchart TD
    subgraph CURRENT["Phase 1 (Current)"]
        U1["User A"] & U2["User B"] --> RA["Shared root agent\nNo tenant isolation"]
    end

    subgraph PHASE2["Phase 2 (Multi-Tenant)"]
        T1["Tenant: gdg-krakow\nShared folder, team history"] 
        T2["Tenant: gdg-warsaw\nIsolated quota & storage"]
        RA2["Root agent with\ntenant_id context"]
        T1 & T2 --> RA2
    end
```

**Changes required:**
- `tenant_id` claim in Firebase Auth custom token
- Session state namespaced by `tenant_id`
- GCS bucket path prefix: `gs://${bucket}/tenants/${tenant_id}/`
- Quota enforcement per tenant (not just per user)

---

### 3.2 Role-Based Access Control (RBAC)

| Role | Capabilities |
|:---|:---|
| Super Admin | All agents, quota management, tenant config |
| Chapter Lead | All event agents, view all member sessions |
| Event Organizer | All event agents, own sessions only |
| Guest | Read-only, no video generation |

**Implementation:** Firebase Auth custom claims + root agent middleware checking `user.claims.role` before routing.

---

### 3.3 Persistent RAG Memory

**Goal:** Agent retains knowledge across event seasons — past speakers, recurring venues, typical agendas.

**Stack:** Vertex AI Vector Search + Cloud Firestore for metadata. ADK `VertexAiRagMemoryService` as memory backend.

**Scope:**
- Per-tenant memory corpus: past events, speaker profiles, venue contacts
- `event_planner` reads memory to avoid rescheduling past conflicts
- `agenda_generator` reads memory to apply community-standard time slots

---

### 3.4 Observability & Cost Attribution

**Current state:** Logging only via Cloud Logging (`roles/logging.logWriter`). No structured metrics, no per-user cost attribution, no SLO dashboards.

**Target state:**

```mermaid
flowchart LR
    subgraph SIGNALS["Telemetry Signals"]
        Logs["Structured JSON logs\n(user_id, tenant_id, agent, tool, latency)"]
        Traces["Cloud Trace\nfull request trace across A2A hops"]
        Metrics["Custom metrics\nvideo renders/day, OCR latency p95, SSE TTFT"]
    end

    subgraph DASHBOARDS["Dashboards"]
        Cost["Cost Attribution\nper user API key usage estimate"]
        SLO["SLO Dashboard\nSSE TTFT < 1.2s, OCR < 6s, Video < 45s"]
        Quota["Quota Monitor\nvideo renders vs. 5/session limit"]
    end

    Logs & Traces & Metrics --> DASHBOARDS
```

**Action items:**
- Instrument `agents/common/` with `google-cloud-trace` spans wrapping tool calls
- Add `structlog` JSON formatter to all agents
- Create Cloud Monitoring dashboards for the three latency SLOs (NFR-05.1–05.3)
- Tag all logs with `user_id` and `session_id` for cost attribution queries

---

## 4. Technical Debt Register

| ID | Area | Description | Priority |
|:---|:---|:---|:---:|
| TD-01 | `storage.tf` | Missing 60-day GCS lifecycle rule | Critical |
| TD-02 | `cloudrun.tf` | Missing concurrency and autoscaling config | High |
| TD-03 | Root agent | No video render quota (max 5/session); LLM turns intentionally unlimited (BYOK) | High |
| TD-04 | Session state | In-memory only; lost on restart or wrong-instance routing | Critical |
| TD-05 | Guardrails | PII redaction enforced by prompt only | High |
| TD-06 | App Check | Backend does not validate App Check tokens | Medium |
| TD-07 | Drive auth | Migrate to OAuth `drive.file` + Google Drive Picker (Phase 2, requires per-user token infra) | Low |
| TD-08 | IAM | Remove project-level `sa_run_invoker` from `iam.tf`; service-level bindings in `cloudrun.tf` already exist and are correctly scoped | High |
| TD-09 | Docs | `setup_guide.md` §5 references stale `receipt-docs-bot` SA | Low |
| TD-10 | Docs | `DEPLOYMENT_GUIDE.md` §6 references stale SA setup | Low |
| TD-11 | Observability | No distributed tracing across A2A hops | Medium |
