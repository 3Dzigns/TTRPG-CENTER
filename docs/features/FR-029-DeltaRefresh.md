# FR-029 — Delta/Refresh

## Goal
Support delta ingestion and targeted cache/graph refresh, so that updates do not require full rebuilds.

## User Stories

**US-0291: Targeted invalidation**
- As the system, I want to invalidate affected neighborhoods (edges/nodes, cached packs) when dictionary or graph changes, so that retrieval remains consistent.

**US-0292: Delta ingestion**
- As a data engineer, I want only updated content re-ingested, so that the pipeline runs faster.

## Test Cases

### Unit
- Graph cache invalidation correctly clears only affected neighborhoods.  
- Delta ingestion skips unchanged files.  

### Functional
- Dictionary update triggers invalidation and query returns updated results.  

### Regression
- Historical queries remain stable when unrelated nodes change.  

### Security
- Invalidation cannot delete unrelated cache entries.  
