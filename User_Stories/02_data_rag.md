# Data Model & RAG Implementation — User Stories & Test Plan

**Scope:** Hybrid RAG system with AstraDB integration and multi-pass ingestion

## User Stories

- As a **stakeholder**, I want **Multi-pass ingestion pipeline (Parse → Enrich → Graph Compile)** (**RAG-001**, priority=critical), so that we meet the MVP acceptance criteria.
- As a **stakeholder**, I want **Metadata preservation with page-accurate references** (**RAG-002**, priority=critical), so that we meet the MVP acceptance criteria.
- As a **stakeholder**, I want **Dynamic dictionary system for cross-system normalization** (**RAG-003**, priority=high), so that we meet the MVP acceptance criteria.

## Acceptance Criteria

### RAG-001: Multi-pass ingestion pipeline (Parse → Enrich → Graph Compile)
- [ ] Pass A: Parse PDF to chunks with primary metadata
- [ ] Pass B: Dictionary normalization and secondary metadata
- [ ] Pass C: Graph workflow compilation and updates
### RAG-002: Metadata preservation with page-accurate references
- [ ] Chunk metadata includes page, section, source identifiers
- [ ] Page numbering matches original print versions
- [ ] Table/diagram chunks are self-contained
### RAG-003: Dynamic dictionary system for cross-system normalization
- [ ] Admin-editable dictionary interface
- [ ] Organic growth from ingested content
- [ ] Cross-system term mapping (e.g., D&D vs Pathfinder)

## Test Plan

### Unit Tests

- RAG-001: Unit tests for core logic/config implementing 'Multi-pass ingestion pipeline (Parse → Enrich → Graph Compile)'.
- RAG-002: Unit tests for core logic/config implementing 'Metadata preservation with page-accurate references'.
- RAG-003: Unit tests for core logic/config implementing 'Dynamic dictionary system for cross-system normalization'.

### Functional (E2E) Tests

- RAG-001: End-to-end scenario demonstrating all acceptance criteria.
- RAG-002: End-to-end scenario demonstrating all acceptance criteria.
- RAG-003: End-to-end scenario demonstrating all acceptance criteria.

### Regression Tests

- RAG-001: Snapshot/behavioral checks to prevent future regressions.
- RAG-002: Snapshot/behavioral checks to prevent future regressions.
- RAG-003: Snapshot/behavioral checks to prevent future regressions.

### Security Tests

- Reject MIME/type-mismatch and oversized PDFs; sandbox parsers.
- All chunks include provenance; optional PII scrubbing enabled.
- Rate limit ingestion; backpressure on embeddings upserts.

## Example Snippet

```python
# Three-pass ingestion sketch
def pass_a_parse(pdf_path): return [{"page": 1, "text": "Example", "section": "Intro"}]
def pass_b_enrich(chunks): 
    for c in chunks: c["norm"] = c["text"].lower()
    return chunks
def pass_c_graph_compile(chunks): 
    # Update workflow graphs based on sections
    return {"updated_nodes": 3}
```
