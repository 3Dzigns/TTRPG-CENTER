# FR-025 — Graph-Augmented Retrieval (GAR)

## Goal
Augment retrieval by expanding from vector/BM25 hits into the graph, building enriched context packs.

## User Stories

**US-0251: Seed with vector/BM25**
- As the retriever, I want to seed candidates from vector search and BM25, so that initial matches are relevant.

**US-0252: Expand graph neighborhood**
- As the retriever, I want to traverse graph neighbors (typed edges, k hops), so that related entities are included.

**US-0253: Build context packs**
- As the retriever, I want to bundle `[path explanation] + [chunks] + [page refs]`, so that provenance is preserved.

## Test Cases

### Unit
- Verify graph expansion stops at hop budget.  
- Ensure only typed edges are followed.  

### Functional
- Query for “Fireball vs Lightning Bolt scaling” expands to spell nodes and scaling rules.

### Regression
- Golden queries yield same path-chunk-page bundles.

### Security
- Guardrails prevent depth >3 or >200 nodes.  
