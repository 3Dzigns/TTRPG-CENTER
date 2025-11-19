# Middleware Execution Plan – FastAPI Implementation
**Version:** 1.0
**Date:** October 19, 2025
**Target Production Date:** January 27, 2026
**Reference:** TTRPG Center – Middleware Requirements v1.0

---

## Executive Summary

This document provides a comprehensive, date-sequenced plan to implement the FastAPI middleware system described in the specification (sections 2–15), mapping Milestones M0–M5 to epics, tasks, and artifacts over a 14-week period using 2-week sprint cycles.

**Key Metrics:**
- **Duration:** 14 weeks (7 sprints)
- **Team Size:** 4 roles (Middleware Lead, DB Engineer, Ingestion Specialist, Frontend Developer)
- **Major Milestones:** 6 (M0-M5)
- **API Endpoints:** 20+ across 8 route groups
- **Databases:** 5 (Postgres, Redis, Cassandra, MongoDB, Neo4j)

---

## 1. Work Breakdown Structure (WBS)

### M0 – Foundation (Sprint 1: Oct 21 - Nov 3, 2025)

**Epic 0.1: Environment Setup**
- **Story 0.1.1:** Docker Swarm cluster initialization
  - Task: Configure Docker Swarm manager + 2 workers
  - Task: Set up overlay network for service mesh
  - Task: Configure secrets management
  - **Spec Reference:** §2.1 Infrastructure
  - **Owner:** Middleware Lead
  - **Estimate:** 3 days

- **Story 0.1.2:** Database initialization
  - Task: Deploy Postgres 15 with RLS support
  - Task: Deploy Redis cluster (3 nodes)
  - Task: Deploy Cassandra 5.x with vector search extensions
  - Task: Deploy MongoDB replica set
  - Task: Deploy Neo4j cluster
  - **Spec Reference:** §3.1 Data Layer
  - **Owner:** DB Engineer
  - **Estimate:** 5 days

**Epic 0.2: Transfer Station Volume**
- **Story 0.2.1:** Shared volume configuration
  - Task: Create NFS/GlusterFS shared volume
  - Task: Mount Transfer_Station in all middleware containers
  - Task: Verify read/write permissions across containers
  - Task: Test file locking and concurrent access
  - **Spec Reference:** §14.2 File Ingestion
  - **Owner:** Ingestion Specialist
  - **Estimate:** 2 days

**Epic 0.3: FastAPI Scaffold**
- **Story 0.3.1:** Application bootstrap
  - Task: Initialize FastAPI project structure
  - Task: Configure dependency injection (DI) container
  - Task: Set up environment variable management (.env)
  - Task: Implement /health/live endpoint
  - **Spec Reference:** §4.1 Application Bootstrap
  - **Owner:** Middleware Lead
  - **Estimate:** 2 days

**M0 Definition of Done:**
- ✅ All 5 databases running with health checks passing
- ✅ Transfer_Station volume mounted and writable from all containers
- ✅ Environment variables configured (no hardcoded secrets)
- ✅ FastAPI app responds to GET /health/live with 200 OK
- ✅ Docker Swarm services auto-restart on failure

---

### M1 – Core Infrastructure (Sprint 2: Nov 4 - Nov 17, 2025)

**Epic 1.1: Database Models & Migrations**
- **Story 1.1.1:** SQLAlchemy 2.x models
  - Task: Define User model (id, email, oidc_sub, created_at)
  - Task: Define Organization model (id, name, created_at)
  - Task: Define Role model (id, org_id, user_id, role_name)
  - Task: Define Membership junction table (user_id, org_id)
  - **Spec Reference:** §5.1 User Management
  - **Owner:** DB Engineer
  - **Estimate:** 3 days

- **Story 1.1.2:** Alembic migrations
  - Task: Initialize Alembic with asyncpg
  - Task: Create initial migration for users/orgs/roles
  - Task: Add indexes on foreign keys
  - Task: Test migration rollback
  - **Spec Reference:** §5.2 Data Migrations
  - **Owner:** DB Engineer
  - **Estimate:** 2 days

**Epic 1.2: Row-Level Security (RLS)**
- **Story 1.2.1:** RLS policy implementation
  - Task: Create RLS policy for organizations table
  - Task: Create RLS policy for roles table
  - Task: Create helper function get_current_user_orgs()
  - Task: Test RLS with multiple users/orgs
  - **Spec Reference:** §6.3 RLS Policies
  - **Owner:** DB Engineer
  - **Estimate:** 3 days

**Epic 1.3: Middleware & Logging**
- **Story 1.3.1:** CORS middleware
  - Task: Configure allowed origins (env-based)
  - Task: Set allowed methods (GET, POST, PUT, DELETE)
  - Task: Enable credentials for JWT cookies
  - **Spec Reference:** §7.1 CORS
  - **Owner:** Middleware Lead
  - **Estimate:** 1 day

- **Story 1.3.2:** Structured logging
  - Task: Integrate structlog with FastAPI
  - Task: Add correlation ID middleware
  - Task: Configure log levels per environment
  - Task: Add request/response logging
  - **Spec Reference:** §13.1 Observability
  - **Owner:** Middleware Lead
  - **Estimate:** 2 days

**M1 Definition of Done:**
- ✅ SQLAlchemy models for users, orgs, roles created
- ✅ Alembic migrations run successfully (forward & backward)
- ✅ RLS policies created and tested with sample data
- ✅ CORS middleware configured with environment-based origins
- ✅ Structured logging with correlation IDs on all requests

---

### M2 – Authentication & Authorization (Sprint 3: Nov 18 - Dec 1, 2025)

**Epic 2.1: OIDC Integration**
- **Story 2.1.1:** OAuth/OIDC flow
  - Task: Implement GET /auth/oidc/authorize (redirect to provider)
  - Task: Implement GET /auth/oidc/callback (exchange code for tokens)
  - Task: Validate id_token signature (JWKS)
  - Task: Extract user claims (sub, email, name)
  - **Spec Reference:** §8.1 OIDC Authentication
  - **Owner:** Middleware Lead
  - **Estimate:** 4 days

**Epic 2.2: JWT & Refresh Token Management**
- **Story 2.2.1:** JWT generation
  - Task: Create JWT with 15min expiry (claims: user_id, orgs, roles)
  - Task: Sign JWT with RS256 (rotating keys)
  - Task: Set httpOnly, secure, sameSite cookies
  - **Spec Reference:** §8.2 JWT Tokens
  - **Owner:** Middleware Lead
  - **Estimate:** 2 days

- **Story 2.2.2:** Refresh token rotation
  - Task: Store refresh tokens in Redis (hash: user_id -> token)
  - Task: Implement POST /auth/refresh endpoint
  - Task: Rotate refresh token on each use (delete old, create new)
  - Task: Set Redis TTL to 15 minutes
  - **Spec Reference:** §8.3 Token Rotation
  - **Owner:** Middleware Lead
  - **Estimate:** 3 days

**Epic 2.3: Auth Middleware & Rate Limiting**
- **Story 2.3.1:** Token validation middleware
  - Task: Extract JWT from cookie
  - Task: Verify signature and expiry
  - Task: Attach user context to request state
  - **Spec Reference:** §8.4 Middleware
  - **Owner:** Middleware Lead
  - **Estimate:** 2 days

- **Story 2.3.2:** Rate limiting
  - Task: Implement Redis-based rate limiter (100 req/min per IP)
  - Task: Apply to /auth/* endpoints
  - Task: Return 429 with Retry-After header
  - **Spec Reference:** §9.1 Rate Limiting
  - **Owner:** Middleware Lead
  - **Estimate:** 1 day

**M2 Definition of Done:**
- ✅ /auth/oidc/* endpoints functional with real OIDC provider
- ✅ JWT generation with 15min expiry and proper claims
- ✅ Refresh token rotation in Redis with TTL
- ✅ Token validation middleware applied to protected routes
- ✅ Rate limiting (100 req/min) on auth endpoints

---

### M3 – Core APIs (Sprint 4: Dec 2 - Dec 15, 2025)

**Epic 3.1: User Profile API**
- **Story 3.1.1:** GET /me endpoint
  - Task: Return authenticated user profile
  - Task: Include organizations and roles
  - Task: Apply RLS (only user's own data)
  - **Spec Reference:** §10.1 User Profile
  - **Owner:** Middleware Lead
  - **Estimate:** 2 days

**Epic 3.2: Organizations API**
- **Story 3.2.1:** GET /orgs endpoint
  - Task: List organizations for authenticated user
  - Task: Apply RLS (only user's orgs)
  - Task: Include member count and metadata
  - **Spec Reference:** §10.2 Organizations
  - **Owner:** Middleware Lead
  - **Estimate:** 2 days

- **Story 3.2.2:** POST /orgs endpoint
  - Task: Create new organization
  - Task: Assign creator as admin role
  - Task: Validate org name uniqueness
  - **Spec Reference:** §10.2 Organizations
  - **Owner:** Middleware Lead
  - **Estimate:** 2 days

**Epic 3.3: Roles API**
- **Story 3.3.1:** GET /roles endpoint
  - Task: List roles for user in specific org
  - Task: Apply RBAC validation (admin can see all, users see own)
  - Task: Return role hierarchy (admin > editor > viewer)
  - **Spec Reference:** §10.3 Roles
  - **Owner:** Middleware Lead
  - **Estimate:** 2 days

- **Story 3.3.2:** POST /roles endpoint (admin only)
  - Task: Assign role to user in org
  - Task: Validate user membership in org
  - Task: Prevent self-demotion of last admin
  - **Spec Reference:** §10.3 Roles
  - **Owner:** Middleware Lead
  - **Estimate:** 2 days

**Epic 3.4: API Documentation**
- **Story 3.4.1:** OpenAPI spec generation
  - Task: Configure FastAPI OpenAPI endpoint
  - Task: Add Pydantic schemas for request/response models
  - Task: Document authentication requirements
  - Task: Add example requests/responses
  - **Spec Reference:** §15.1 Documentation
  - **Owner:** Middleware Lead
  - **Estimate:** 2 days

**M3 Definition of Done:**
- ✅ GET /me returns user profile with RLS enforcement
- ✅ GET /orgs lists user organizations
- ✅ POST /orgs creates new organization
- ✅ GET /roles returns user roles per org
- ✅ POST /roles assigns roles (admin only)
- ✅ RBAC validation on all endpoints
- ✅ OpenAPI spec published at /docs

---

### M4 – Data APIs (Sprints 5-6: Dec 16 - Jan 12, 2026)

**Epic 4.1: Retrieval API (Cassandra Vector Search)**
- **Story 4.1.1:** POST /retrieve endpoint
  - Task: Accept query text and filters (org_id, source_ids)
  - Task: Generate embedding vector (call embedding service)
  - Task: Perform ANN search in Cassandra (top_k=10)
  - Task: Filter results by user's orgs (RLS)
  - Task: Return ranked results with scores
  - **Spec Reference:** §11.1 Retrieval
  - **Owner:** Middleware Lead
  - **Estimate:** 4 days

- **Story 4.1.2:** Cassandra schema validation
  - Task: Verify vector dimensions match embedding model
  - Task: Test ANN index performance (>1000 QPS)
  - Task: Add org_id to partition key for isolation
  - **Spec Reference:** §11.1 Retrieval
  - **Owner:** DB Engineer
  - **Estimate:** 2 days

**Epic 4.2: Dictionary API (Neo4j Graph)**
- **Story 4.2.1:** GET /dictionary/{term} endpoint
  - Task: Query Neo4j for term node and relationships
  - Task: Return related terms (synonyms, antonyms, hyponyms)
  - Task: Include org-specific custom terms
  - Task: Apply graph-level RLS (org isolation)
  - **Spec Reference:** §11.2 Dictionary
  - **Owner:** Middleware Lead
  - **Estimate:** 3 days

- **Story 4.2.2:** POST /dictionary endpoint (admin only)
  - Task: Create custom term node for org
  - Task: Link to existing terms via relationships
  - Task: Validate term uniqueness within org
  - **Spec Reference:** §11.2 Dictionary
  - **Owner:** Middleware Lead
  - **Estimate:** 2 days

**Epic 4.3: Ingestion Jobs API**
- **Story 4.3.1:** POST /ingestion/jobs endpoint
  - Task: Accept multipart file upload
  - Task: Validate file type (PDF, TXT, DOCX)
  - Task: Write file to Transfer_Station volume
  - Task: Create job record in MongoDB (status: pending)
  - Task: Enqueue job_id to processing queue
  - Task: Return 202 Accepted with job_id
  - **Spec Reference:** §14.1 Ingestion
  - **Owner:** Ingestion Specialist
  - **Estimate:** 4 days

- **Story 4.3.2:** GET /ingestion/jobs/{job_id} endpoint
  - Task: Return job status (pending, processing, completed, failed)
  - Task: Include progress percentage
  - Task: Return error message if failed
  - Task: Apply org-level isolation (user can only see own jobs)
  - **Spec Reference:** §14.2 Job Status
  - **Owner:** Ingestion Specialist
  - **Estimate:** 2 days

**Epic 4.4: Metadata Enrichment (MongoDB)**
- **Story 4.4.1:** MongoDB integration
  - Task: Store document metadata (title, author, page_count)
  - Task: Link metadata to Cassandra vectors via document_id
  - Task: Implement GET /documents/{id}/metadata
  - **Spec Reference:** §11.3 Metadata
  - **Owner:** Middleware Lead
  - **Estimate:** 2 days

**M4 Definition of Done:**
- ✅ POST /retrieve performs vector search in Cassandra
- ✅ GET /dictionary/{term} queries Neo4j graph
- ✅ POST /dictionary creates custom terms (admin only)
- ✅ POST /ingestion/jobs accepts file uploads
- ✅ GET /ingestion/jobs/{job_id} returns job status
- ✅ All endpoints enforce org-level isolation
- ✅ Integration tests with real data in all 5 databases

---

### M5 – Production Readiness (Sprint 7: Jan 13 - Jan 26, 2026)

**Epic 5.1: Audit Logging**
- **Story 5.1.1:** Audit log implementation
  - Task: Create audit_logs table (user_id, action, resource, timestamp)
  - Task: Add audit middleware for all POST/PUT/DELETE requests
  - Task: Implement GET /audit endpoint (admin only)
  - Task: Add search/filter by user, action, date range
  - **Spec Reference:** §12.1 Audit Logs
  - **Owner:** Middleware Lead
  - **Estimate:** 3 days

**Epic 5.2: Observability (OTel + Prometheus)**
- **Story 5.2.1:** OpenTelemetry integration
  - Task: Configure OTel SDK for FastAPI
  - Task: Export traces to Jaeger
  - Task: Export metrics to Prometheus
  - Task: Add custom spans for DB queries
  - **Spec Reference:** §13.1 Observability
  - **Owner:** Middleware Lead
  - **Estimate:** 3 days

- **Story 5.2.2:** Metrics endpoint
  - Task: Implement GET /metrics (Prometheus format)
  - Task: Expose request count, latency, error rate
  - Task: Add business metrics (active users, jobs/day)
  - **Spec Reference:** §13.2 Metrics
  - **Owner:** Middleware Lead
  - **Estimate:** 2 days

**Epic 5.3: Health Checks**
- **Story 5.3.1:** Advanced health checks
  - Task: Enhance /health/live (check FastAPI process)
  - Task: Implement /health/ready (check DB connections)
  - Task: Add /health/startup (one-time initialization check)
  - **Spec Reference:** §13.3 Health
  - **Owner:** Middleware Lead
  - **Estimate:** 1 day

**Epic 5.4: Security Hardening**
- **Story 5.4.1:** Security headers
  - Task: Add Content-Security-Policy header
  - Task: Add Strict-Transport-Security (HSTS)
  - Task: Add X-Frame-Options, X-Content-Type-Options
  - **Spec Reference:** §9.2 Security Headers
  - **Owner:** Middleware Lead
  - **Estimate:** 1 day

- **Story 5.4.2:** Rate limiting (global)
  - Task: Apply rate limiting to all endpoints (1000 req/min per user)
  - Task: Whitelist internal services
  - Task: Add rate limit headers (X-RateLimit-*)
  - **Spec Reference:** §9.1 Rate Limiting
  - **Owner:** Middleware Lead
  - **Estimate:** 1 day

**Epic 5.5: Load Testing & Go/No-Go**
- **Story 5.5.1:** Performance testing
  - Task: Run load test (1000 req/s sustained for 10 min)
  - Task: Verify p95 latency <200ms
  - Task: Verify error rate <5%
  - Task: Test failover scenarios (DB restart, network partition)
  - **Spec Reference:** §15.2 Performance
  - **Owner:** Middleware Lead + DB Engineer
  - **Estimate:** 3 days

- **Story 5.5.2:** Go/No-Go checklist
  - Task: 100% critical tests passing
  - Task: Security scan clean (no high/critical vulns)
  - Task: All 5 databases with replication/backups
  - Task: Monitoring dashboards configured
  - Task: Runbook documented
  - **Spec Reference:** §15.3 Go/No-Go
  - **Owner:** All
  - **Estimate:** 1 day

**M5 Definition of Done:**
- ✅ /audit logs all mutations with searchable history
- ✅ OTel traces exported to Jaeger
- ✅ GET /metrics exposes Prometheus metrics
- ✅ Security headers on all responses
- ✅ Rate limiting on all endpoints (1000 req/min per user)
- ✅ Load test: 1000 req/s sustained, <5% error rate, <200ms p95
- ✅ Go/No-Go checklist: 100% pass

---

## 2. Resource Plan

### Team Roles & Responsibilities

| Role | Primary Responsibilities | Sprints | FTE |
|------|-------------------------|---------|-----|
| **Middleware Lead** | FastAPI development, API endpoints, auth, observability | 1-7 | 1.0 |
| **DB Engineer** | Database setup, migrations, RLS, schema optimization | 1-5 | 1.0 |
| **Ingestion Specialist** | Transfer_Station, file uploads, job processing | 1, 5-6 | 0.5 |
| **Frontend Developer** | API contract validation, integration testing | 3-7 | 0.5 |

**Total Team:** 3 FTE

### Sprint Allocation

| Sprint | Milestone | Middleware Lead | DB Engineer | Ingestion | Frontend |
|--------|-----------|----------------|-------------|-----------|----------|
| 1 | M0 | Setup FastAPI | Init 5 DBs | Transfer_Station | — |
| 2 | M1 | CORS, Logging | Models, RLS | — | — |
| 3 | M2 | Auth, JWT | RLS Testing | — | OIDC Testing |
| 4 | M3 | Core APIs | — | — | API Contracts |
| 5 | M4 (Part 1) | /retrieve, /dictionary | Cassandra, Neo4j | — | Integration Tests |
| 6 | M4 (Part 2) | Metadata API | MongoDB | /ingestion/jobs | Integration Tests |
| 7 | M5 | Audit, OTel, Metrics | Performance | — | Load Testing |

---

## 3. Risk Register

| Risk ID | Description | Impact | Probability | Detection | Mitigation | Owner |
|---------|-------------|--------|-------------|-----------|------------|-------|
| **R1** | Cassandra vector dimension mismatch | High | Medium | Validate dims in M0 | Early prototype with embedding service, document expected dims | DB Engineer |
| **R2** | RLS policy complexity causes perf degradation | High | Medium | Load test in M1 | Index foreign keys, use materialized views if needed | DB Engineer |
| **R3** | JWT 15min expiry UX issues | Medium | High | User feedback in M3 | Implement seamless refresh flow, pre-emptive token refresh in UI | Middleware + Frontend |
| **R4** | Redis failover during token operations | High | Low | Simulate failover in M5 | Implement retry with exponential backoff, use Redis Sentinel | Middleware Lead |
| **R5** | Neo4j schema evolution breaks queries | Medium | Medium | Integration tests in M4 | Version graph schema, plan migrations in M1 | DB Engineer |
| **R6** | Transfer_Station volume permissions | Medium | Medium | Test in M0 | Use Docker volume with correct UID/GID, document in runbook | Ingestion Specialist |
| **R7** | OIDC provider downtime | High | Low | /health checks in M5 | Cache user profiles, implement degraded mode (read-only) | Middleware Lead |
| **R8** | Rate limiting false positives | Low | Medium | Monitor in M5 | Whitelist internal IPs, add bypass header for ops | Middleware Lead |
| **R9** | OTel overhead impacts latency | Medium | Low | Performance test in M5 | Tune sampling rate, use async exporters | Middleware Lead |
| **R10** | Database connection pool exhaustion | High | Medium | Load test in M5 | Configure pool sizes per DB, add connection metrics | DB Engineer |

**Rollback Strategy:**
- All sprints have Alembic migrations (forward/backward)
- Docker Swarm allows instant rollback to previous image
- Feature flags for new endpoints (disable via env var)
- Database backups before each sprint

---

## 4. Sequence Diagrams

### 4.1 Login/OIDC → Token Exchange

```
┌──────┐         ┌──────┐         ┌────────────┐         ┌──────────────┐         ┌──────────┐
│ User │         │WebUI │         │ Middleware │         │OIDC Provider │         │Postgres  │
└──┬───┘         └──┬───┘         └─────┬──────┘         └──────┬───────┘         └────┬─────┘
   │                │                   │                       │                      │
   │ Click "Login"  │                   │                       │                      │
   ├───────────────►│                   │                       │                      │
   │                │ GET /auth/oidc/authorize                  │                      │
   │                ├──────────────────►│                       │                      │
   │                │                   │ Redirect (client_id, scope)                  │
   │                │                   ├──────────────────────►│                      │
   │                │                   │                       │                      │
   │                │◄──────────────────┴───────────────────────┤                      │
   │                │ Auth prompt                               │                      │
   │◄───────────────┤                                           │                      │
   │                │                                           │                      │
   │ Enter credentials                                          │                      │
   ├───────────────────────────────────────────────────────────►│                      │
   │                │                                           │                      │
   │                │ Callback (auth_code)                      │                      │
   │                │◄──────────────────────────────────────────┤                      │
   │                │                   │                       │                      │
   │                │ GET /auth/oidc/callback?code=XXX          │                      │
   │                ├──────────────────►│                       │                      │
   │                │                   │ POST /token (auth_code)                      │
   │                │                   ├──────────────────────►│                      │
   │                │                   │                       │                      │
   │                │                   │ {id_token, access_token, refresh_token}      │
   │                │                   │◄──────────────────────┤                      │
   │                │                   │                       │                      │
   │                │                   │ Store refresh_token in Redis (15min TTL)     │
   │                │                   ├────────────────────────────────────────┐     │
   │                │                   │                                        │     │
   │                │                   │◄───────────────────────────────────────┘     │
   │                │                   │                       │                      │
   │                │                   │ Upsert user, check/create roles (RLS)        │
   │                │                   ├─────────────────────────────────────────────►│
   │                │                   │                       │                      │
   │                │                   │ User/roles data       │                      │
   │                │                   │◄─────────────────────────────────────────────┤
   │                │                   │                       │                      │
   │                │ Set-Cookie: JWT (httpOnly, secure, 15min)│                      │
   │                │◄──────────────────┤                       │                      │
   │                │ Redirect to /app  │                       │                      │
   │◄───────────────┤                   │                       │                      │
   │                │                   │                       │                      │
```

### 4.2 /retrieve Path (Vector Search)

```
┌──────┐         ┌────────────┐         ┌──────────┐         ┌───────────┐         ┌─────────┐
│WebUI │         │ Middleware │         │ Postgres │         │ Cassandra │         │ MongoDB │
└──┬───┘         └─────┬──────┘         └────┬─────┘         └─────┬─────┘         └────┬────┘
   │                   │                     │                     │                    │
   │ POST /retrieve {query, filters, top_k} │                     │                    │
   ├──────────────────►│                     │                     │                    │
   │                   │                     │                     │                    │
   │                   │ Validate JWT (check Redis if near expiry)│                    │
   │                   ├────────────────────────────────────────┐  │                    │
   │                   │                                        │  │                    │
   │                   │◄───────────────────────────────────────┘  │                    │
   │                   │                     │                     │                    │
   │                   │ Get user orgs/roles (RLS applied)         │                    │
   │                   ├────────────────────►│                     │                    │
   │                   │                     │                     │                    │
   │                   │ [user_orgs: [1, 5]]│                     │                    │
   │                   │◄────────────────────┤                     │                    │
   │                   │                     │                     │                    │
   │                   │ ANN vector search (WHERE org_id IN [1,5])│                    │
   │                   ├─────────────────────────────────────────►│                    │
   │                   │                     │                     │                    │
   │                   │ Top K results [doc_ids, scores, embeddings]                   │
   │                   │◄─────────────────────────────────────────┤                    │
   │                   │                     │                     │                    │
   │                   │ Fetch metadata for doc_ids                │                    │
   │                   ├──────────────────────────────────────────────────────────────►│
   │                   │                     │                     │                    │
   │                   │ {title, author, page_count, ...}          │                    │
   │                   │◄──────────────────────────────────────────────────────────────┤
   │                   │                     │                     │                    │
   │ 200 OK {results: [{id, score, title, ...}, ...]}             │                    │
   │◄──────────────────┤                     │                     │                    │
   │                   │                     │                     │                    │
```

### 4.3 Upload → /ingestion/jobs

```
┌──────┐    ┌────────────┐    ┌─────────────────┐    ┌─────────┐    ┌──────────────┐    ┌────────┐
│WebUI │    │ Middleware │    │Transfer_Station │    │ MongoDB │    │Message Queue │    │ Worker │
└──┬───┘    └─────┬──────┘    └────────┬────────┘    └────┬────┘    └──────┬───────┘    └───┬────┘
   │              │                    │                  │                │                │
   │ POST /ingestion/jobs (multipart) │                  │                │                │
   ├─────────────►│                    │                  │                │                │
   │              │                    │                  │                │                │
   │              │ Validate JWT, check org permissions  │                │                │
   │              ├───────────────────────────────────┐   │                │                │
   │              │                                   │   │                │                │
   │              │◄──────────────────────────────────┘   │                │                │
   │              │                    │                  │                │                │
   │              │ Write file to shared volume           │                │                │
   │              ├───────────────────►│                  │                │                │
   │              │                    │                  │                │                │
   │              │ File written       │                  │                │                │
   │              │◄───────────────────┤                  │                │                │
   │              │                    │                  │                │                │
   │              │ Create job record {status: pending, file_path, org_id}│                │
   │              ├─────────────────────────────────────►│                │                │
   │              │                    │                  │                │                │
   │              │ {job_id: 123, ...} │                  │                │                │
   │              │◄─────────────────────────────────────┤                │                │
   │              │                    │                  │                │                │
   │              │ Enqueue job_id to processing queue   │                │                │
   │              ├──────────────────────────────────────────────────────►│                │
   │              │                    │                  │                │                │
   │ 202 Accepted {job_id: 123}        │                  │                │                │
   │◄─────────────┤                    │                  │                │                │
   │              │                    │                  │                │                │
   │              │                    │                  │                │ Dequeue job_id │
   │              │                    │                  │                │◄───────────────┤
   │              │                    │                  │                │                │
   │              │                    │                  │                │ Read file      │
   │              │                    │                  │                ├───────────────►│
   │              │                    │ File content     │                │                │
   │              │                    ├──────────────────────────────────────────────────►│
   │              │                    │                  │                │                │
   │              │                    │                  │                │ Process (chunk, embed, store)
   │              │                    │                  │                │                ├───┐
   │              │                    │                  │                │                │   │
   │              │                    │                  │                │                │◄──┘
   │              │                    │                  │                │                │
   │              │                    │                  │ Update job {status: completed} │
   │              │                    │                  │◄───────────────────────────────┤
   │              │                    │                  │                │                │
```

---

## 5. Definition of Done (DOD) & Go/No-Go Checklist

### Per-Milestone DOD

See detailed DOD criteria under each milestone section (M0-M5) above.

### Final Go/No-Go Checklist (Sprint 7, Jan 26, 2026)

**Critical Criteria (Must Pass):**
- [ ] **Security:**
  - [ ] No high/critical vulnerabilities in dependency scan
  - [ ] All endpoints require authentication (except /health/*)
  - [ ] RLS policies enforce org isolation
  - [ ] JWT expiry ≤15 minutes
  - [ ] Refresh token rotation working
  - [ ] Security headers on all responses (CSP, HSTS, etc.)
  - [ ] Rate limiting active on all endpoints

- [ ] **Functionality:**
  - [ ] 100% of critical tests passing
  - [ ] All 20+ API endpoints functional
  - [ ] OIDC flow working end-to-end
  - [ ] Vector search returns accurate results
  - [ ] File uploads stored in Transfer_Station
  - [ ] Audit logs capturing all mutations

- [ ] **Performance:**
  - [ ] Load test sustained 1000 req/s for 10 minutes
  - [ ] p95 latency <200ms
  - [ ] Error rate <5%
  - [ ] Database connections stable under load

- [ ] **Reliability:**
  - [ ] All 5 databases with replication/backups
  - [ ] Health checks passing (/health/live, /health/ready)
  - [ ] Docker Swarm auto-restart working
  - [ ] Failover tested (DB restart, network partition)

- [ ] **Observability:**
  - [ ] OTel traces visible in Jaeger
  - [ ] Prometheus metrics endpoint working
  - [ ] Grafana dashboards configured
  - [ ] Alert rules defined (error rate, latency, down services)

- [ ] **Documentation:**
  - [ ] OpenAPI spec published at /docs
  - [ ] Runbook documented (startup, shutdown, rollback)
  - [ ] Incident response plan
  - [ ] Backup/restore procedures

**Nice-to-Have (Can Defer):**
- [ ] GraphQL endpoint (can add post-launch)
- [ ] WebSocket support for real-time updates
- [ ] Advanced caching (Redis for query results)
- [ ] Multi-region deployment

**Go Decision:**
- ✅ **GO:** All critical criteria pass + ≥80% nice-to-have
- ⚠️ **GO with Caveats:** All critical pass + document known issues
- ❌ **NO-GO:** Any critical criterion fails → fix and re-test

---

## 6. Calendar Schedule

**Start Date:** Monday, October 21, 2025
**Target Production Date:** Monday, January 27, 2026
**Sprint Duration:** 2 weeks (10 working days)

| Sprint | Dates | Milestone | Key Deliverables |
|--------|-------|-----------|------------------|
| **Sprint 1** | Oct 21 - Nov 3 | M0 - Foundation | Docker Swarm, 5 databases, Transfer_Station, FastAPI scaffold |
| **Sprint 2** | Nov 4 - Nov 17 | M1 - Core Infrastructure | SQLAlchemy models, Alembic, RLS, CORS, logging |
| **Sprint 3** | Nov 18 - Dec 1 | M2 - Authentication | OIDC, JWT, refresh tokens, rate limiting |
| **Sprint 4** | Dec 2 - Dec 15 | M3 - Core APIs | /me, /orgs, /roles, OpenAPI docs |
| **Sprint 5** | Dec 16 - Dec 29 | M4 - Data APIs (1) | /retrieve (Cassandra), /dictionary (Neo4j) |
| **Sprint 6** | Dec 30 - Jan 12 | M4 - Data APIs (2) | /ingestion/jobs, metadata (MongoDB) |
| **Sprint 7** | Jan 13 - Jan 26 | M5 - Production | Audit, OTel, metrics, load testing, Go/No-Go |
| **Launch** | Jan 27, 2026 | **Production** | 🚀 Middleware live in production |

### Sprint Ceremonies

**Each Sprint:**
- **Sprint Planning:** Monday 9:00 AM (2 hours)
- **Daily Standups:** Every day 9:30 AM (15 min)
- **Sprint Review:** Friday Week 2, 2:00 PM (1 hour)
- **Sprint Retrospective:** Friday Week 2, 3:30 PM (1 hour)

### Key Milestones & Demos

- **Nov 3:** M0 Demo – Infrastructure ready
- **Nov 17:** M1 Demo – Core models and RLS working
- **Dec 1:** M2 Demo – Full auth flow end-to-end
- **Dec 15:** M3 Demo – Core APIs functional with OpenAPI docs
- **Jan 12:** M4 Demo – All data APIs integrated
- **Jan 26:** M5 Review – Go/No-Go decision
- **Jan 27:** 🎉 **Production Launch**

---

## 7. Dependencies & Integration Points

### External Dependencies

| Dependency | Purpose | Owner | Availability Date | Risk Mitigation |
|------------|---------|-------|-------------------|-----------------|
| OIDC Provider | User authentication | Security Team | Oct 15 (before Sprint 1) | Use mock provider in dev |
| Embedding Service | Vector generation for /retrieve | ML Team | Nov 1 (Sprint 1) | Use pre-computed vectors for testing |
| Transfer_Station | Shared volume for file uploads | DevOps | Oct 21 (Sprint 1 start) | Test with local NFS first |
| Monitoring Stack | Jaeger, Prometheus, Grafana | Platform Team | Jan 6 (Sprint 7) | Use local instances in dev |

### Internal Integration Points

| System | Integration | Direction | Protocol |
|--------|-------------|-----------|----------|
| WebUI | API calls | WebUI → Middleware | REST/JSON over HTTPS |
| Ingestion Worker | File processing | Middleware → Worker | Message queue (Redis) |
| ML Pipeline | Embedding generation | Middleware → ML | gRPC or REST |
| Analytics | Event streaming | Middleware → Analytics | Kafka (future) |

---

## 8. Acceptance Criteria Summary

### Task List Coverage

✅ **M0:** 3 epics, 4 stories, 12 tasks – covers §2.1 Infrastructure, §3.1 Data Layer, §4.1 Bootstrap
✅ **M1:** 3 epics, 5 stories, 11 tasks – covers §5 User Mgmt, §6.3 RLS, §7.1 CORS, §13.1 Logging
✅ **M2:** 3 epics, 5 stories, 12 tasks – covers §8 Auth, §9.1 Rate Limiting
✅ **M3:** 4 epics, 6 stories, 13 tasks – covers §10 Core APIs, §15.1 Documentation
✅ **M4:** 4 epics, 6 stories, 15 tasks – covers §11 Data APIs, §14 Ingestion
✅ **M5:** 5 epics, 7 stories, 12 tasks – covers §12 Audit, §13 Observability, §15 Go/No-Go

**Total:** 22 epics, 33 stories, 75 tasks

### Spec Section Mapping

| Spec Section | Coverage | Milestone(s) |
|--------------|----------|--------------|
| §2 Infrastructure | ✅ | M0 |
| §3 Data Layer | ✅ | M0, M1 |
| §4 Bootstrap | ✅ | M0 |
| §5 User Management | ✅ | M1, M3 |
| §6 RLS | ✅ | M1, M2 |
| §7 CORS | ✅ | M1 |
| §8 Authentication | ✅ | M2 |
| §9 Security | ✅ | M2, M5 |
| §10 Core APIs | ✅ | M3 |
| §11 Data APIs | ✅ | M4 |
| §12 Audit | ✅ | M5 |
| §13 Observability | ✅ | M1, M5 |
| §14 Ingestion | ✅ | M0, M4 |
| §15 Go/No-Go | ✅ | M5 |

---

## 9. Change Management

### Scope Change Process

1. **Request:** Stakeholder submits change request with justification
2. **Impact Analysis:** Middleware Lead assesses timeline, resource, risk impact
3. **Prioritization:** If critical, re-prioritize current sprint; else, add to backlog
4. **Approval:** Product Owner approves (delays launch) or defers to post-launch
5. **Communication:** Update plan, notify team, adjust calendar

### Risk Response Triggers

| Trigger | Response | Owner |
|---------|----------|-------|
| Critical test fails in sprint review | Extend sprint by 2 days, defer nice-to-have features | Middleware Lead |
| Database migration fails in production | Rollback to previous version, investigate offline | DB Engineer |
| Load test fails (<1000 req/s) | Performance sprint (add 1 week), optimize bottlenecks | Middleware Lead + DB Engineer |
| OIDC provider unavailable | Switch to dev mock provider, notify stakeholders | Middleware Lead |
| Vector dimension mismatch discovered | Emergency sprint to re-index Cassandra, coordinate with ML team | DB Engineer |

---

## 10. Success Metrics

### Technical KPIs (Measured at Launch)

- **Availability:** ≥99.9% uptime (8.76 hours downtime/year)
- **Performance:** p95 latency <200ms, p99 <500ms
- **Throughput:** 1000 req/s sustained, 5000 req/s peak
- **Error Rate:** <5% under normal load, <10% under peak
- **Security:** 0 high/critical vulnerabilities
- **Test Coverage:** ≥80% code coverage, 100% critical path

### Business KPIs (Measured at 30 days post-launch)

- **User Adoption:** ≥70% of existing users migrated
- **API Usage:** ≥10,000 /retrieve calls/day
- **Ingestion Jobs:** ≥100 documents processed/day
- **Auth Success Rate:** ≥95% (failed logins <5%)

---

## 11. Appendix

### A. Glossary

- **RLS:** Row-Level Security (Postgres feature for org isolation)
- **JWT:** JSON Web Token (stateless auth token)
- **OIDC:** OpenID Connect (auth protocol)
- **ANN:** Approximate Nearest Neighbor (vector search algorithm)
- **OTel:** OpenTelemetry (observability framework)
- **Transfer_Station:** Shared volume for file uploads between middleware and workers
- **DOD:** Definition of Done
- **WBS:** Work Breakdown Structure

### B. References

- TTRPG Center – Middleware Requirements v1.0 (sections 2–15)
- FastAPI Documentation: https://fastapi.tiangolo.com
- SQLAlchemy 2.x Migration Guide: https://docs.sqlalchemy.org/en/20/changelog/migration_20.html
- Postgres RLS: https://www.postgresql.org/docs/current/ddl-rowsecurity.html
- OpenTelemetry Python: https://opentelemetry.io/docs/instrumentation/python/

### C. Contact Information

| Role | Name | Email | Slack |
|------|------|-------|-------|
| Middleware Lead | TBD | middleware-lead@ttrpg.dev | @middleware-lead |
| DB Engineer | TBD | db-engineer@ttrpg.dev | @db-engineer |
| Ingestion Specialist | TBD | ingestion@ttrpg.dev | @ingestion |
| Product Owner | TBD | product@ttrpg.dev | @product-owner |

---

**Document Version:** 1.0
**Last Updated:** October 19, 2025
**Next Review:** Sprint 3 Retrospective (Dec 1, 2025)
