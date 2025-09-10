# TTRPG Center — Master Requirements (Expanded)

This document consolidates requirements, user stories, test cases, admin/user UI specs, and governance.

(See prior sections for full details. This version includes a traceability matrix.)

---

## Section 8: Traceability Matrix

The following matrix links Requirements → User Stories → Test Cases → Bugs/Features.

| Requirement ID | User Story ID | Test Case ID | Related Bug(s) | Related Feature(s) |
|----------------|---------------|--------------|----------------|--------------------|
| ARCH-001 (Env Isolation) | US-ARCH-001 | TST-ARCH-001 | BUG-010 | - |
| ARCH-002 (Immutable Builds) | US-ARCH-002 | TST-ARCH-002 | - | - |
| ARCH-004 (Cache Control) | US-ARCH-004 | TST-ARCH-004 | - | - |
| RAG-001 (Pass A) | US-RAG-001 | TST-RAG-001 | BUG-018 | FR-INGEST-201 |
| RAG-002 (Pass B) | US-RAG-002 | TST-RAG-002 | BUG-018 | FR-INGEST-201 |
| RAG-003 (Pass C) | US-RAG-003 | TST-RAG-003 | BUG-018 | FR-INGEST-201 |
| RAG-004 (Pass D) | US-RAG-004 | TST-RAG-004 | BUG-006 | FR-INGEST-201 |
| RAG-005 (Pass E) | US-RAG-005 | TST-RAG-005 | BUG-005, BUG-008 | FR-REASON-502 |
| RAG-006 (Pass F) | US-RAG-006 | TST-RAG-006 | BUG-018 | FR-INGEST-201 |
| RAG Retrieval | US-RAG-007 | TST-RAG-007 | BUG-002 | FR-ARCH-501 |
| Graph Workflow | US-WF-001 | TST-WF-001 | BUG-012 | FR-REASON-502 |
| Graphwalk Reasoning | US-WF-002 | TST-WF-002 | BUG-005, BUG-012 | FR-REASON-502 |
| Admin Dashboard | US-ADM-001 | TST-ADM-001 | BUG-013 | - |
| Ticketing System | US-ADM-003 | TST-ADM-003 | BUG-014 | - |
| User UI Submit/Stop | US-UI-001/002 | TST-UI-001 | - | FR-ARCH-602 |
| Feedback Capture | US-UI-003 | TST-UI-003 | BUG-016 | - |
| Feedback to Bug/Feature | US-TEST-001/002 | TST-TEST-001 | BUG-011 | - |
| Immutable Req Store | US-REQ-001 | TST-REQ-001 | - | - |
| Feature Approval | US-REQ-002 | TST-REQ-002 | - | - |
| JWT Authentication | US-SEC-401 | TST-SEC-401 | BUG-003 | FR-SEC-401 |
| CORS Security | US-SEC-402 | TST-SEC-402 | BUG-004, BUG-007 | FR-SEC-402, FR-SEC-407 |
| HTTPS/TLS | US-SEC-403 | TST-SEC-403 | BUG-017 | FR-SEC-403 |
| API Rate Limiting | US-SEC-406 | TST-SEC-406 | BUG-013 | FR-SEC-406 |
| Redis Caching | US-REDIS-001–007 | TST-REDIS-001 | BUG-006 | FR-PERF-404 |
| Async DB Ops | US-ASYNC-001 | TST-ASYNC-001 | BUG-006 | FR-PERF-405 |
| Local DB Store | US-DB-001–004 | TST-DB-001 | BUG-010 | FR-DB-001 |

---
