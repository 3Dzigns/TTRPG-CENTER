# FR-027 — Answer + Provenance

## Goal
Ensure answers include only context packs with explicit path traces and chunk citations, and render a compact UI trace.

## User Stories

**US-0271: Provenance-preserving answers**
- As a user, I want answers that include citations and path traces, so that I can trust the response.

**US-0272: UI trace rendering**
- As a user, I want to see the pipeline trace (Classifier → Plan → Graph paths → Chunks used), so that reasoning steps are transparent.

## Test Cases

### Unit
- Answer includes `sources` block with chunk IDs and page refs.  
- Trace object lists classifier decision, plan, and retrieval path.  

### Functional
- UI shows compact trace panel with steps collapsed/expandable.  

### Regression
- Golden answers maintain provenance blocks.  

### Security
- No sensitive data leaks in trace (sanitized IDs only).  
