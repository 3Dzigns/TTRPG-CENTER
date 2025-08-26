
# Command: Features (Requests & Admin Workflow)

## Purpose

Handle new feature requests from CLI or Web UI, log them properly, and provide Admin controls for approval or removal. Integrates with thumbs-down feedback flow (promote to bug or feature).

---

## Directory Layout

```
features/
  pending/     # New submissions awaiting Admin decision
  approved/    # Requests approved for development
  removed/     # Requests rejected or withdrawn
```

---

## Workflow

### 1. Create New Feature Request

* **Source:** CLI (`new_feature`) or Web UI form.
* **Validate:** Must conform to `docs/requirements/feature_request.schema.json`.
* **File Format:** JSON, ID = `FR-YYYYMMDD-###` (e.g. `FR-20250826-001`).
* **Location:** Save in `features/pending/FR-…_<slug>.json`.
* **Commit:**

  ```
  git add features/pending/FR-…  
  git commit -m "feat(features): add <short title> [FR-…]"
  git push
  ```

### 2. Admin Approval

* **Action:** Move file to `features/approved/`.
* **Update Fields:**

  ```json
  "status": "approved",
  "approved_by": "<admin>",
  "approved_at": "<ISO8601 timestamp>"
  ```
* **Commit:**

  ```
  git mv features/pending/FR-… features/approved/FR-…
  git commit -m "chore(features): approve FR-…"
  git push
  ```

### 3. Admin Removal

* **Action:** Move file to `features/removed/`.
* **Update Fields:**

  ```json
  "status": "rejected",
  "rejected_reason": "<reason>",
  "removed_by": "<admin>",
  "removed_at": "<ISO8601 timestamp>"
  ```
* **Commit:**

  ```
  git mv features/pending/FR-… features/removed/FR-…
  git commit -m "chore(features): remove FR-…"
  git push
  ```

---

## Integration with Feedback

* **Thumbs Down Feedback (👎):**

  * Admin UI presents option → “Promote to Bug” OR “Promote to Feature”.
  * If **Bug:** create entry in `bugs/` backlog.
  * If **Feature:** convert feedback into schema-compliant JSON and log under `features/pending/`.

---

## Commit Message Rules

* All feature requests, approvals, and removals must reference the **FR-ID**.
  Example:

