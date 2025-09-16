# FR-026 — Hybrid Rerank

## Goal
Combine embeddings, BM25, graph path weights, and recency into a hybrid reranking score.

## User Stories

**US-0261: Multi-factor scoring**
- As the retriever, I want scores that combine α·embedding + β·BM25 + γ·graph-path + δ·recency, so that the best context rises to the top.

**US-0262: Deduplicate and budget**
- As the retriever, I want to keep only top N packs and dedupe by page/section, so that context is clean and efficient.

## Test Cases

### Unit
- Test weighted scoring function produces higher rank for closer matches.  
- Deduplication removes duplicates by section ID.  

### Functional
- Mixed query returns balanced results (not just vector or graph).  

### Regression
- Canonical queries produce stable top-3 results.  

### Security
- Prevent unbounded weights (α..δ must be 0–1).  
