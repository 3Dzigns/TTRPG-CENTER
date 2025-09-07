# Phase 7 — Requirements & Features

**Goal:** Store immutable requirements, provide a structured feature request workflow, enforce schema validation, and give admins full control with an auditable trail.

---

## Epic E7.1 — Immutable Requirements

### US-701: Store Requirements as Versioned JSON

**As** a System Architect
**I want** requirements stored as immutable, versioned JSON files
**So that** the system always has an authoritative baseline.

**Acceptance Criteria**

* Requirements stored in `/requirements/{version}.json`.
* New version → append-only; old versions never overwritten.
* Version metadata includes `{version_id, timestamp, author}`.
* Admin UI (Phase 4) displays current + historical requirements.

**Testing**

* **Unit:** Saving a new requirement creates new version file.
* **Functional:** Admin UI lists all versions with timestamps.
* **Regression:** Old versions load without errors.
* **Security:** Write-protected — only Admins can add.

**Code Snippet**

```python
import json, pathlib, time
def save_requirements(req: dict, author: str):
    vid = int(time.time())
    path = pathlib.Path(f"requirements/{vid}.json")
    if path.exists(): raise RuntimeError("Immutable — cannot overwrite")
    req["metadata"] = {"version_id": vid, "author": author, "timestamp": time.ctime()}
    path.write_text(json.dumps(req, indent=2))
    return vid
```

---

## Epic E7.2 — Feature Request Workflow

### US-702: Submit Feature Request

**As** a User
**I want** to submit feature requests through the UI
**So that** my ideas are captured in a structured way.

**Acceptance Criteria**

* Feature request form includes `{title, description, priority, requester}`.
* Stored in `features/{request_id}.json`.
* Status defaults to `pending`.

**Testing**

* **Unit:** Submitting request creates JSON entry.
* **Functional:** Request visible in Admin UI.
* **Regression:** Old requests still load correctly.
* **Security:** Input sanitized.

---

### US-703: Approve/Reject Features

**As** an Admin
**I want** to approve or reject submitted feature requests
**So that** only vetted features enter development.

**Acceptance Criteria**

* Admin UI shows list of pending requests.
* Approve → status = `approved`; Reject → status = `rejected`.
* Decision stored in audit log with `{admin, timestamp, decision}`.

**Testing**

* **Unit:** Approve/Reject updates status.
* **Functional:** Decision visible in Admin dashboard.
* **Regression:** Already-approved features unaffected.
* **Security:** Only Admins can change status.

---

### US-704: Audit Trail for Feature Workflow

**As** a Compliance Officer
**I want** all feature request changes logged
**So that** there’s a permanent audit history.

**Acceptance Criteria**

* Audit entries stored in `/audit/features.log`.
* Each entry: `{request_id, old_status, new_status, admin, timestamp}`.
* Read-only once written.

**Testing**

* **Unit:** Audit entries append-only.
* **Functional:** Log entries visible for each feature.
* **Security:** Tamper detection — log checksum validated.

---

## Epic E7.3 — Schema Validation

### US-705: Requirements Schema Validation

**As** a Developer
**I want** requirements JSON validated against a schema
**So that** structure and fields are consistent.

**Acceptance Criteria**

* JSON schema defined in `/schemas/requirements.schema.json`.
* Validation runs automatically in DEV gates (from Phase 6).
* Invalid files rejected with descriptive error.

**Testing**

* **Unit:** Valid JSON passes; invalid JSON fails.
* **Functional:** CI blocks commit with invalid schema.
* **Regression:** Old files remain valid.
* **Security:** Schema prevents injection in JSON fields.

---

### US-706: Feature Request Schema Validation

**As** a Developer
**I want** feature requests validated against a schema
**So that** requests are consistent and parseable.

**Acceptance Criteria**

* JSON schema in `/schemas/feature_request.schema.json`.
* Validation on submit; invalid request rejected with error.
* Schema enforces `title, description, priority`.

**Testing**

* **Unit:** Schema validation works.
* **Functional:** Invalid request form blocked.
* **Regression:** Schema changes versioned; old files compatible.

---

# Phase 7 Test Plan

### Unit Tests

* Save requirements → versioned file created.
* Submit feature request → JSON file created.
* Approve/Reject updates status + audit log.
* Schema validation passes/fails correctly.

### Functional Tests

* Admin adds new requirements → listed in UI.
* User submits feature → visible in Admin dashboard.
* Admin approves feature → audit log updated.
* Invalid JSON schema blocks commit.

### Regression Tests

* Old requirements still visible.
* Old feature requests load without schema errors.

### Security Tests

* Requirements immutable — cannot overwrite.
* Feature requests sanitized (no HTML/JS).
* Audit logs append-only; checksum validation.

---

✅ **Definition of Done (Phase 7):**

* Immutable requirements stored as JSON with version history.
* Feature request workflow live with approval/rejection + audit trail.
* Schema validation enforced for requirements & feature requests.
* Admin UI shows requirements, features, and decisions.
* All unit, functional, regression, and security tests passing in CI.
