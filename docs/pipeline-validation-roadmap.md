# Ingestion Pipeline Validation Roadmap

**Document Version**: 1.0
**Created**: 2025-10-02
**Status**: Planning Phase
**Estimated Total Effort**: 44-60 hours

---

## Executive Summary

This document provides a comprehensive roadmap for validating and updating the TTRPG Center ingestion pipeline (Pass 0 + A-G) to match the AI prompt specification defined in `MVP-Version-2/Ingestion-Pipeline-AI-Prompts.md`.

### Validation Scope

The current implementation has gaps in:
1. **Output Format Standardization**: Missing spec-compliant JSON outputs
2. **OCR Strategy**: Missing retry logic, hard failures, mandatory scanned page handling
3. **Processing Strategy**: Pass A processes full PDF instead of TOC-only
4. **Persistence Layer**: Missing Neo4j, Mongo proposals integration
5. **Validation Gates**: Missing comprehensive validation in Pass F

---

## Gap Analysis by Pass

### Pass 0 (Gate 0) - Preflight & OCR Readiness

**Current Status**: ✅ Basic implementation exists
**Spec Compliance**: 🟡 60% compliant

| Feature | Status | Priority | Effort |
|---------|--------|----------|--------|
| SHA256 computation | ✅ Complete | - | 0h |
| Page count extraction | ✅ Complete | - | 0h |
| Duplicate detection | ✅ Complete | - | 0h |
| **Scanned page detection** | 🔄 In Progress | HIGH | 2h |
| **Standard gate0.report.json** | ❌ Missing | HIGH | 2h |
| **OCR readiness validation** | 🟡 Partial | HIGH | 1h |
| **Hard fail on missing OCR** | ❌ Missing | HIGH | 1h |
| tessdata language detection | ❌ Missing | MEDIUM | 1h |

**Total Effort**: 7 hours

---

### Pass A - TOC Harvest & Dictionary Seed

**Current Status**: 🟡 Partial implementation
**Spec Compliance**: 🔴 40% compliant

| Feature | Status | Priority | Effort |
|---------|--------|----------|--------|
| **TOC-only processing** | ❌ Missing | CRITICAL | 4h |
| **TOC page detection** | ❌ Missing | CRITICAL | 3h |
| **Hierarchical parsing** | 🟡 Partial | HIGH | 3h |
| **Standard passA.toc.json** | ❌ Missing | HIGH | 2h |
| **Dictionary seeding** | 🟡 Partial | HIGH | 2h |
| **Confidence scoring** | ❌ Missing | MEDIUM | 2h |
| Stable section_id (SHA1) | ❌ Missing | MEDIUM | 1h |
| TOC-specific heuristics | ❌ Missing | HIGH | 3h |

**Total Effort**: 20 hours

**Critical Changes Required**:
```python
# Current: Processes entire PDF with Unstructured.io
# Required: Detect TOC pages (first 2-5) → Process only those

# Detection indicators:
# - Headings: "Table of Contents", "Contents"
# - High density of page numbers (right-aligned)
# - Dot leaders (.....)
# - Hierarchical numbering (1, 1.1, I, A)
```

---

### Pass B - Smart Page Splitting

**Current Status**: 🟡 Partial implementation
**Spec Compliance**: 🔴 30% compliant

| Feature | Status | Priority | Effort |
|---------|--------|----------|--------|
| **TOC-based splitting** | ❌ Missing | CRITICAL | 4h |
| **Sub-heading detection** | ❌ Missing | HIGH | 3h |
| **Table/statblock preservation** | ❌ Missing | HIGH | 3h |
| **Similarity trough detection** | ❌ Missing | MEDIUM | 4h |
| **passB.parts.jsonl format** | 🟡 Partial | MEDIUM | 2h |
| Token-based sizing (3-8k) | 🟡 Partial | MEDIUM | 2h |
| Safe boundary detection | ❌ Missing | HIGH | 3h |

**Total Effort**: 21 hours

**Critical Changes Required**:
```python
# Current: Size-based splitting (25MB threshold)
# Required: TOC section boundary splitting

# Strategy:
# 1. Split on passA.toc.json section boundaries
# 2. Use sub-headings if section > 8k tokens
# 3. Never split mid-table/code/statblock
# 4. Use similarity troughs for safe split points
# 5. Target 3-8k tokens, cap 30 pages at boundaries
```

---

### Pass C - Extraction & OCR

**Current Status**: 🟡 Partial implementation
**Spec Compliance**: 🟡 55% compliant

| Feature | Status | Priority | Effort |
|---------|--------|----------|--------|
| Unstructured.io integration | ✅ Complete | - | 0h |
| **Mandatory OCR for scanned** | ❌ Missing | CRITICAL | 2h |
| **OCR retry logic** | ❌ Missing | HIGH | 3h |
| **Hard fail on empty OCR** | ❌ Missing | HIGH | 1h |
| **passC.ocr.report.json** | ❌ Missing | HIGH | 2h |
| **No empty placeholders** | ❌ Missing | HIGH | 1h |
| gate0 scanned_pages integration | ❌ Missing | HIGH | 1h |

**Total Effort**: 10 hours

**Critical Changes Required**:
```python
# Current: OCR optional, no retry logic
# Required: Mandatory OCR for scanned pages with retry

# Logic:
# 1. Read gate0.report.json → scanned_pages array
# 2. For each scanned page: OCR is MANDATORY
# 3. If OCR returns empty → retry with alternate params
# 4. After retries fail → emit errors.jsonl (OCR_TEXT_EMPTY) → STOP
# 5. Track all OCR operations in passC.ocr.report.json
```

---

### Pass D - Normalize & Embeddings

**Current Status**: 🟡 Partial implementation
**Spec Compliance**: 🟡 60% compliant

| Feature | Status | Priority | Effort |
|---------|--------|----------|--------|
| Text normalization | ✅ Complete | - | 0h |
| Semantic chunking (≤800 tokens) | ✅ Complete | - | 0h |
| Haystack embeddings | ✅ Complete | - | 0h |
| **dict.delta.passD.json** | ❌ Missing | HIGH | 2h |
| **Explicit upsert policy** | 🟡 Partial | HIGH | 2h |
| **Upsert logging (upsert\|noop)** | ✅ Complete | - | 0h |
| Cassandra schema validation | 🟡 Partial | MEDIUM | 1h |
| Dictionary candidate extraction | 🟡 Partial | MEDIUM | 2h |

**Total Effort**: 7 hours

**Critical Changes Required**:
```python
# Current: Upserts to Cassandra but policy unclear
# Required: Explicit policy + dict delta output

# Upsert Policy:
# - PK: (doc_id, norm_id)
# - If hash changed → OVERWRITE (log "upsert")
# - If hash unchanged → NOOP (log "noop")
# - Track NEW/CHANGED/UNCHANGED in dict.delta.passD.json
```

---

### Pass E - Graph Build

**Current Status**: 🟡 Partial implementation
**Spec Compliance**: 🔴 35% compliant

| Feature | Status | Priority | Effort |
|---------|--------|----------|--------|
| LlamaIndex graph building | ✅ Complete | - | 0h |
| **Neo4j upserts (MERGE)** | ❌ Missing | CRITICAL | 6h |
| **Mongo dictionary proposals** | ❌ Missing | CRITICAL | 5h |
| **dict.delta.passE.json** | ❌ Missing | HIGH | 2h |
| Node types (Sections, Blocks, Terms) | 🟡 Partial | HIGH | 2h |
| Edge types (4 types) | 🟡 Partial | HIGH | 2h |
| Status='open' for proposals | ❌ Missing | HIGH | 1h |

**Total Effort**: 18 hours

**Critical Changes Required**:
```python
# Current: Builds graph in memory, no Neo4j/Mongo
# Required: Neo4j MERGE + Mongo proposals

# Neo4j Upserts:
# MERGE (n:Section {id: section_id})
# MERGE (n1)-[:ContainedIn]->(n2)
# Edge types: ContainedIn, Mentions, RefersTo, PrereqOf

# Mongo Proposals:
# db.dictionary_proposals.insertMany([
#   {term: "Fireball", status: "open", confidence: 0.9, ...}
# ])
# NEVER update canonicals directly
```

---

### Pass F - Validation & Manifest

**Current Status**: 🟡 Partial implementation
**Spec Compliance**: 🔴 40% compliant

| Feature | Status | Priority | Effort |
|---------|--------|----------|--------|
| **Page coverage validation** | ❌ Missing | CRITICAL | 3h |
| **OCR coverage check (<100%)** | ❌ Missing | CRITICAL | 2h |
| **Orphan node/edge detection** | 🟡 Partial | HIGH | 2h |
| **validation.report.json** | ❌ Missing | HIGH | 2h |
| **Artifact checksums** | 🟡 Partial | MEDIUM | 1h |
| **Hard fail on broken lineage** | ❌ Missing | HIGH | 2h |
| Comprehensive validation gates | ❌ Missing | HIGH | 3h |

**Total Effort**: 15 hours

**Critical Changes Required**:
```python
# Current: Basic validation
# Required: Comprehensive validation with hard fails

# Validations:
# 1. Every page covered exactly once (from passB)
# 2. Every scanned page has OCR text (from passC.ocr.report.json)
# 3. No orphan nodes/edges (from passE graph)
# 4. All artifact checksums match
# 5. FAIL if OCR coverage < 100%
# 6. FAIL if lineage broken
```

---

### Pass G - HGRN Consistency & Dictionary Remediation

**Current Status**: 🟡 Partial implementation
**Spec Compliance**: 🟡 50% compliant

| Feature | Status | Priority | Effort |
|---------|--------|----------|--------|
| Graph consistency checks | ✅ Complete | - | 0h |
| **Alias drift detection** | 🟡 Partial | HIGH | 4h |
| **Merge proposals with confidence** | ❌ Missing | HIGH | 3h |
| **hgrn.actions.json** | 🟡 Partial | MEDIUM | 2h |
| **dict.delta.passG.json** | ✅ Complete | - | 0h |
| **Mongo proposals (not canonicals)** | ❌ Missing | CRITICAL | 4h |
| Evidence-based proposals | ❌ Missing | MEDIUM | 3h |

**Total Effort**: 16 hours

**Critical Changes Required**:
```python
# Current: Detects issues, writes reports
# Required: Mongo proposals with confidence

# Alias Detection:
# - Edit distance scoring
# - Context similarity
# - Confidence: 0.0-1.0

# Proposals:
# db.dictionary_proposals.insertMany([
#   {
#     action: "merge",
#     terms: ["Fireball", "Fire Ball"],
#     confidence: 0.85,
#     evidence: ["doc_id:section_id", ...],
#     status: "open"
#   }
# ])
# NEVER touch canonicals
```

---

## Cross-Pass Integration Requirements

### Error Handling Standard

**File**: `errors.jsonl` (emitted by all passes on failure)

```json
{
  "code": "OCR_DEPENDENCY_MISSING|OCR_TEXT_EMPTY|VALIDATION_FAILED",
  "message": "Human-readable error description",
  "page": 42,  // Optional
  "chunk_id": "chunk_abc123",  // Optional
  "retriable": false,
  "timestamp": "2025-10-02T12:34:56Z",
  "pass": "C"
}
```

**Implementation**: 2 hours

---

### JSON Logging Standard

**Format**: Every pass emits structured logs

```json
{
  "doc_id": "doc_abc123",
  "pass": "D",
  "status": "complete|failed|in_progress",
  "action": "upsert|noop|skip",
  "counts": {
    "chunks_processed": 150,
    "vectors_created": 145,
    "upserts": 120,
    "noops": 25
  },
  "timestamp": "2025-10-02T12:34:56Z"
}
```

**Implementation**: 3 hours (standardize across all passes)

---

## Implementation Phases

### Phase 1: Pass 0 + A Foundation (10-14 hours)

**Goal**: Establish TOC detection and preflight validation foundation

**Tasks**:
1. ✅ Pass 0.1: Scanned page detection (2h) - **IN PROGRESS**
2. Pass 0.2: Standard gate0.report.json output (2h)
3. Pass 0.3: Hard fail on missing OCR dependencies (1h)
4. Pass 0.4: Pass 0 regression tests (2h)
5. Pass A.1: TOC-only processing (4h)
6. Pass A.2: Standard passA.toc.json output (2h)
7. Pass A.3: Dictionary seeding (2h)
8. Pass A.4: TOC-specific heuristics (3h)
9. Pass A.5: Pass A regression tests (2h)

**Deliverables**:
- `gate0.report.json` format implemented
- TOC-only extraction working
- `passA.toc.json` format implemented
- `dict.seed.jsonl` generated
- Regression test suites for Pass 0 and A

---

### Phase 2: Pass B + C Smart Splitting & OCR (16-20 hours)

**Goal**: Implement smart TOC-based splitting and mandatory OCR with retry

**Tasks**:
1. Pass B.1: TOC-based splitting logic (4h)
2. Pass B.2: Similarity trough detection (4h)
3. Pass B.3: Safe boundary detection (3h)
4. Pass B.4: Pass B regression tests (2h)
5. Pass C.1: Mandatory OCR for scanned pages (2h)
6. Pass C.2: OCR retry logic (3h)
7. Pass C.3: passC.ocr.report.json output (2h)
8. Pass C.4: Hard fail enforcement (1h)
9. Pass C.5: Pass C regression tests (3h)

**Deliverables**:
- Smart splitting based on TOC boundaries
- `passB.parts.jsonl` with reasoning
- Mandatory OCR for all scanned pages
- `passC.ocr.report.json` tracking
- OCR retry logic with hard fails

---

### Phase 3: Pass D + E Persistence Layer (14-18 hours)

**Goal**: Implement Neo4j and Mongo proposals integration

**Tasks**:
1. Pass D.1: dict.delta.passD.json output (2h)
2. Pass D.2: Explicit upsert policy (2h)
3. Pass D.3: Cassandra schema validation (1h)
4. Pass D.4: Pass D regression tests (2h)
5. Pass E.1: Neo4j MERGE upserts (6h)
6. Pass E.2: Mongo dictionary proposals (5h)
7. Pass E.3: dict.delta.passE.json output (2h)
8. Pass E.4: Pass E regression tests (3h)

**Deliverables**:
- Dictionary deltas from Pass D
- Neo4j graph upserts working
- Mongo proposals collection populated
- No canonical dictionary updates

---

### Phase 4: Pass F + G Validation & Remediation (12-16 hours)

**Goal**: Comprehensive validation gates and dictionary remediation

**Tasks**:
1. Pass F.1: Page coverage validation (3h)
2. Pass F.2: OCR coverage validation (2h)
3. Pass F.3: validation.report.json output (2h)
4. Pass F.4: Hard fail conditions (2h)
5. Pass F.5: Pass F regression tests (3h)
6. Pass G.1: Alias drift detection enhancement (4h)
7. Pass G.2: Mongo merge proposals (4h)
8. Pass G.3: hgrn.actions.json enhancement (2h)
9. Pass G.4: Pass G regression tests (2h)

**Deliverables**:
- Comprehensive validation.report.json
- Hard fails on validation failures
- Alias detection with confidence
- Merge proposals in Mongo (not canonicals)

---

### Phase 5: Integration & Testing (6-10 hours)

**Goal**: End-to-end pipeline validation and documentation

**Tasks**:
1. errors.jsonl standard implementation (2h)
2. JSON logging standardization (3h)
3. End-to-end integration test (3h)
4. Pipeline runbook updates (2h)
5. Performance benchmarking (2h)

**Deliverables**:
- Standardized error handling
- Complete E2E test passing
- Updated documentation
- Performance baselines

---

## Testing Strategy

### Unit Tests (Per Pass)

Each pass requires dedicated unit tests:

```
tests/unit/
├── test_pass_0_preflight.py
│   ├── test_scanned_page_detection
│   ├── test_gate0_report_format
│   ├── test_ocr_dependency_validation
│   └── test_duplicate_detection
├── test_pass_a_toc_parser.py
│   ├── test_toc_page_detection
│   ├── test_hierarchical_parsing
│   ├── test_passA_toc_json_format
│   └── test_dictionary_seeding
...
```

### Integration Tests

```
tests/integration/
├── test_pass_0_to_a_integration.py
├── test_pass_a_to_b_integration.py
├── test_full_pipeline_e2e.py
└── test_error_propagation.py
```

### Regression Tests

```
tests/regression/
├── test_spec_compliance_pass_0.py
├── test_spec_compliance_pass_a.py
...
└── test_output_format_stability.py
```

---

## Success Metrics

### Output Format Compliance

| Pass | Expected Output | Status |
|------|----------------|--------|
| 0 | gate0.report.json | 🔄 In Progress |
| A | passA.toc.json, dict.seed.jsonl | ❌ Not Started |
| B | passB.parts.jsonl | ❌ Not Started |
| C | passC.chunks.jsonl, passC.ocr.report.json | ❌ Not Started |
| D | passD.normalized.jsonl, passD.embeddings.jsonl, dict.delta.passD.json | ❌ Not Started |
| E | graph.json, dict.delta.passE.json | ❌ Not Started |
| F | validation.report.json | ❌ Not Started |
| G | hgrn.report.json, hgrn.actions.json, dict.delta.passG.json | 🟡 Partial |

### Functional Compliance

- [ ] Pass 0: Scanned page detection accuracy >95%
- [ ] Pass A: TOC-only processing (not full PDF)
- [ ] Pass B: TOC-based splitting (not size-based)
- [ ] Pass C: 100% OCR coverage for scanned pages
- [ ] Pass D: Upsert policy explicit and logged
- [ ] Pass E: Neo4j + Mongo integration complete
- [ ] Pass F: Hard fails on validation failures
- [ ] Pass G: Proposals to Mongo (not canonicals)

### Test Coverage

- [ ] Unit test coverage: >80% per pass
- [ ] Integration tests: All pass-to-pass transitions
- [ ] Regression tests: All output formats stable
- [ ] E2E test: Full pipeline (0→A→B→C→D→E→F→G)

---

## Risk Assessment

### High-Risk Changes

1. **Pass A: TOC-only processing** (CRITICAL)
   - Risk: May break existing pipelines expecting full PDF processing
   - Mitigation: Feature flag for old/new behavior, parallel testing

2. **Pass E: Neo4j integration** (CRITICAL)
   - Risk: New dependency, requires infrastructure
   - Mitigation: Docker service addition, connection pooling

3. **Pass C: Hard fail on OCR** (HIGH)
   - Risk: May reject valid PDFs with OCR issues
   - Mitigation: Comprehensive retry logic, clear error messages

### Medium-Risk Changes

1. **Pass B: Smart splitting** (MEDIUM)
   - Risk: Different split boundaries may affect downstream
   - Mitigation: Validation in Pass F ensures coverage

2. **Pass F: Validation gates** (MEDIUM)
   - Risk: May fail legitimate jobs with edge cases
   - Mitigation: Detailed error reporting, manual override capability

---

## Dependencies & Prerequisites

### Infrastructure

- ✅ Docker (existing)
- ✅ Cassandra/AstraDB (existing)
- ❌ **Neo4j** (NEW - requires Docker service)
- ✅ MongoDB (existing)
- ✅ Redis (existing)

### Python Libraries

- ✅ PyMuPDF/fitz (existing)
- ✅ Unstructured.io (existing)
- ✅ Haystack (existing)
- ✅ LlamaIndex (existing)
- ❌ **Neo4j Python driver** (NEW)
- ✅ pymongo (existing)

### Configuration

- [ ] Neo4j connection settings
- [ ] Mongo proposals collection schema
- [ ] OCR retry parameters
- [ ] Validation thresholds

---

## Session Planning

### Recommended Session Breakdown

**Session 1** (4-6 hours): Phase 1 Part 1
- Complete Pass 0 validation (tasks 0.1-0.4)
- Start Pass A TOC detection

**Session 2** (4-6 hours): Phase 1 Part 2
- Complete Pass A implementation (tasks A.1-A.5)
- Regression tests for Pass 0 + A

**Session 3** (4-6 hours): Phase 2 Part 1
- Pass B smart splitting (tasks B.1-B.4)

**Session 4** (4-6 hours): Phase 2 Part 2
- Pass C OCR enhancements (tasks C.1-C.5)

**Session 5** (4-6 hours): Phase 3 Part 1
- Pass D dictionary deltas
- Neo4j setup and integration

**Session 6** (4-6 hours): Phase 3 Part 2
- Pass E Neo4j + Mongo implementation
- Regression tests

**Session 7** (4-6 hours): Phase 4 Part 1
- Pass F validation gates

**Session 8** (4-6 hours): Phase 4 Part 2
- Pass G remediation enhancements

**Session 9** (3-4 hours): Phase 5
- Integration testing
- Documentation

---

## Current Progress

### Completed
- ✅ Gap analysis and specification review
- ✅ Comprehensive roadmap document
- ✅ Pass 0.1: Scanned page detection function (90% complete)

### In Progress
- 🔄 Pass 0.1: Integration of scanned page detection into run_preflight_checks
- 🔄 Pass 0.2: gate0.report.json format design

### Next Steps
1. Complete Pass 0.1 integration
2. Implement gate0.report.json output (Pass 0.2)
3. Add hard fail logic for missing OCR (Pass 0.3)
4. Create Pass 0 regression test suite (Pass 0.4)

---

## References

- **Specification**: `MVP-Version-2/Ingestion-Pipeline-AI-Prompts.md`
- **Current Implementation**: `src_common/pass_[0a-g]_*.py`
- **Runbook**: `docs/ingestion-pipeline-runbook.md`
- **Regression Tests**: `tests/regression/test_observability_logging.py`

---

## Appendix: Output Format Specifications

### gate0.report.json

```json
{
  "doc_id": "doc_abc123",
  "filename": "pathfinder_core_rulebook.pdf",
  "file_sha256": "a1b2c3d4...",
  "filesize_bytes": 52428800,
  "page_count": 640,
  "scanned_pages": [1, 2, 5, 15],
  "has_text_layer": true,
  "ocr_readiness": {
    "tesseract": true,
    "poppler": true,
    "tessdata_langs": ["eng"],
    "ready": true
  },
  "prior_ingest_match": {
    "matched": false
  }
}
```

### passA.toc.json

```json
{
  "doc_id": "doc_abc123",
  "sections": [
    {
      "section_id": "sha1_abc",
      "title": "Chapter 1: Character Creation",
      "start_page": 10,
      "end_page": 45,
      "level": 1
    },
    {
      "section_id": "sha1_def",
      "title": "Ability Scores",
      "start_page": 12,
      "end_page": 18,
      "level": 2
    }
  ],
  "toc_pages": [1, 2, 3],
  "confidence": 0.95
}
```

### passC.ocr.report.json

```json
{
  "doc_id": "doc_abc123",
  "pages_processed": 640,
  "ocr_operations": [
    {
      "page": 1,
      "scanned": true,
      "ocr_attempted": true,
      "ocr_success": true,
      "text_length": 2450,
      "retries": 0
    },
    {
      "page": 2,
      "scanned": true,
      "ocr_attempted": true,
      "ocr_success": false,
      "text_length": 0,
      "retries": 2,
      "error": "OCR_TEXT_EMPTY"
    }
  ],
  "summary": {
    "total_scanned": 4,
    "ocr_success": 3,
    "ocr_failed": 1,
    "coverage_pct": 75.0
  }
}
```

---

**End of Roadmap Document**
