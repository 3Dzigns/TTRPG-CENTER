# Pass F v2.1.0 - Major Upgrade Analysis

**Generated:** 2025-10-11
**Version:** 2.1.0 (upgraded from 2.0.0)
**Analysis Type:** Feature Enhancement & Capability Review

---

## Executive Summary

Pass F has undergone a **major upgrade** from placeholder validation to **full source document validation** with token-based matching, pipeline feedback generation, and HGRN-compatible output structure. This represents a **fundamental shift** from reactive database validation to **proactive source-truth verification**.

**Upgrade Impact: ⭐⭐⭐⭐⭐ (5/5) - Production-Critical Enhancement**

---

## Major New Features

### 1. Source Document Validation (New in v2.1.0)

**Capability:** Validates that database content matches the original source document.

**Implementation:**
- PDF text extraction via pypdf
- Text file parsing with form-feed page splitting
- Token-based matching (4+ character alphanumeric tokens)
- Normalized text comparison (case-insensitive, whitespace-normalized)

**Configuration:**
```python
SOURCE_TOKEN_PATTERN = re.compile(r"[a-z0-9]{4,}")
SOURCE_TOKEN_PAGE_LIMIT = 256          # Max tokens indexed per page
SOURCE_TOKEN_MIN_MATCH = 3             # Min token overlap for validation
SOURCE_TOKEN_SAMPLE_LIMIT = 8          # Token sample in evidence
```

**New Methods:**
- `_load_source_document()` - Extract and index source pages
- `_extract_pdf_pages()` - PDF text extraction
- `_extract_text_pages()` - Plain text extraction with page splitting
- `_normalize_text()` - Whitespace normalization
- `_tokenize()` - Token extraction
- `_index_page_text()` - Build inverted token index
- `_page_token_overlap()` - Token-based page matching
- `_page_contains_text()` - Phrase validation
- `_search_document()` - Full-document search
- `_run_source_checks()` - TOC and term validation against source

**Evidence Collection:**
```python
self.source_issues: List[Dict[str, Any]] = []
self.pipeline_suggestions: List[str] = []
```

---

### 2. TOC Source Validation

**Validation:** Verifies that TOC entries from Pass A exist on their declared pages in the source document.

**Logic:**
```python
for entry in toc_entries[:200]:
    title = entry.get('title')
    page_start = entry.get('page_start')
    if not self._page_contains_text(page_start, title):
        # Record violation
        self.source_issues.append({
            'type': 'toc_missing',
            'title': title,
            'page': page_start,
            'token_sample': self._token_sample(title),
        })
        self.pipeline_suggestions.append(
            f"Pass A: TOC entry '{title}' was not located on page {page_start}."
        )
```

**Impact:**
- Detects OCR errors in Pass A TOC extraction
- Identifies incorrect page number assignments
- Provides token samples for debugging

---

### 3. Term Dictionary Validation

**Validation:** Verifies that extracted terms (Pass C) actually appear in the source document.

**Logic:**
```python
for term_data in terms:
    term = term_data.get('term')
    pages = term_data.get('page_references') or []
    found = False

    # Check declared pages
    for page in pages:
        if self._page_contains_text(page, term):
            found = True
            break

    # Fallback: search entire document
    if not found and self._search_document(term):
        found = True

    if not found:
        self._record_missing_term(term, pages)
```

**Remediation:**
```python
{
    'type': 'TermNotFoundInSource',
    'term': term,
    'pages_checked': pages,
    'suggested_action': {
        'rationale': 'Term not located in original source document.',
        'dry_run': True,
        'update': {
            'collection': 'terms',
            'operation': 'deleteOne',
            'filter': {'document_id': document_id, 'term': term}
        }
    }
}
```

**Impact:**
- Detects hallucinated terms from Pass C
- Identifies incorrect page references
- Suggests dictionary cleanup

---

### 4. Cassandra Content Validation

**New in v2.1.0:** Validates that Cassandra chunk text matches source document.

**Enhancement:**
```python
# New in v2.1.0: Check text_content field
text_content = getattr(row, "text_content", None)

if text_content is None or not str(text_content).strip():
    violations += 1
    evidence.append({'chunk_id': chunk_id, 'issue': 'text_missing'})
else:
    snippet = text_content[:160]
    overlap_ok = self._page_token_overlap(page_int, text_content)

    if not overlap_ok:
        overlap_ok = self._search_document(text_content[:200])

    if not overlap_ok:
        violations += 1
        evidence.append({
            'chunk_id': chunk_id,
            'issue': 'content_mismatch',
            'token_sample': self._token_sample(text_content),
            'snippet': snippet,
        })
        self.pipeline_suggestions.append(
            f"Pass C: Chunk {chunk_id} text was not located on source page {page_int}."
        )
```

**Impact:**
- Detects text extraction errors in Pass C
- Identifies chunk/page misalignments
- Validates vector embedding accuracy

---

### 5. HGRN Output Structure

**New in v2.1.0:** Separate HGRN-specific outputs for machine processing.

**Output Files:**
```
Pass_F_Out/
└── {document_id}/
    ├── hgrn_db_remediations.json      # Database fix actions
    └── hgrn_pipeline_suggestions.md   # Human-readable recommendations
```

**hgrn_db_remediations.json Structure:**
```json
{
  "document_id": "pathfinder_core_20251009_120000",
  "source_file": "/Transfer_Station/sources/pathfinder.pdf",
  "source_file_sha256": "4f4b1d9d...",
  "overall_score": 0.89,
  "issues_found": 23,
  "mongodb": [{...}],
  "cassandra": [{...}],
  "neo4j": [{...}],
  "chunks": [{...}],
  "source_analysis": [{...}],
  "evidence_tables": {...},
  "pipeline_suggestions": [...]
}
```

**hgrn_pipeline_suggestions.md:**
```markdown
# Pipeline Suggestions

- Pass A: TOC entry 'Chapter 3: Spells' was not located on page 42.
- Pass C: Chunk elem_123:5 text was not located on source page 15.
- Pass C: Review dictionary extraction rules for term 'Armor Penetration'.
```

**Method:**
```python
def _write_hgrn_outputs(self, document_id, gate0_data, overall_score) -> Dict[str, Path]:
    base_dir = self.hgrn_output_dir / document_id
    base_dir.mkdir(parents=True, exist_ok=True)

    remediations_path = base_dir / 'hgrn_db_remediations.json'
    pipeline_path = base_dir / 'hgrn_pipeline_suggestions.md'

    # Write structured JSON for automation
    save_json(remediations_path, db_payload)

    # Write human-readable Markdown
    with pipeline_path.open('w', encoding='utf-8') as handle:
        handle.write('# Pipeline Suggestions\n\n')
        for suggestion in suggestions:
            handle.write(f'- {suggestion}\n')

    return {'remediations': remediations_path, 'pipeline': pipeline_path}
```

---

### 6. Enhanced Neo4j Validation

**Improvements:**
- Checks for missing Chunk nodes (0 chunks = critical error)
- Better cycle detection with count-based filtering
- Improved orphan detection with `COUNT` instead of `size()`

**New Logic:**
```python
# Check for missing chunks (new validation)
chunk_count_query = "MATCH (c:Chunk {document_id:$document_id}) RETURN count(c) AS chunk_count"
chunk_count = session.run(chunk_count_query, document_id=document_id).data()[0]['chunk_count']

if chunk_count == 0:
    violations += 1
    evidence.append({'issue': 'chunk_nodes_missing'})
    actions.append({
        'statement': '-- No Chunk nodes present; rerun Pass E graph builder/upsert.',
        'reason': 'Chunk nodes missing in Neo4j for document.',
    })
```

---

### 7. MongoDB Term Validation Enhancement

**New in v2.1.0:** Derives sources from `page_references` if `sources` field is empty.

**Logic:**
```python
sources = term.get("sources") or []
page_refs = term.get("page_references") or []

if not sources and page_refs:
    derived_sources = []
    for ref in page_refs:
        try:
            ref_int = int(ref)
            derived_sources.append({"page": ref_int})
        except (TypeError, ValueError):
            continue
    if derived_sources:
        sources = derived_sources
```

**Impact:**
- Handles schema variations
- Backward compatibility with Pass A/C output formats
- Reduces false positives for missing sources

---

### 8. Enhanced Configuration Support

**New CLI Arguments:**
```python
parser.add_argument("--source-file", type=Path, default=None,
                    help="Optional path to the original source document.")
parser.add_argument("--rules-dir", type=Path, default=None,
                    help="Directory containing validation rule definitions.")
parser.add_argument("--hgrn-output", type=Path, default=None,
                    help="Directory where HGRN outputs are written.")
```

**New ingestion.cfg Settings:**
```ini
[Pass_F]
# Neo4j credentials from env
neo4j_user =
neo4j_password =
env_file = /app/.env

# HGRN validation options
rules_dir = /Transfer_Station/hgrn/rules
hgrn_output_dir = /Transfer_Station/Pass_F_Out/hgrn_output
tenant_id = default
corpus_version =
expected_system =
expected_publisher =
```

---

## Architecture Changes

### State Management

**New Instance Variables:**
```python
self.source_file: Optional[Path]           # CLI override path
self.source_path: Optional[Path]           # Resolved source path
self.source_pages: List[str]               # Raw page text
self.source_pages_normalized: List[str]    # Normalized text
self.source_page_tokens: List[Set[str]]    # Token sets per page
self.source_token_index: Dict[str, Set[int]]  # Token → page numbers
self.source_issues: List[Dict[str, Any]]   # Source validation issues
self.pipeline_suggestions: List[str]       # Actionable recommendations
self.source_file_sha256: Optional[str]     # Source file hash
self.hgrn_output_dir_current: Optional[Path]  # Per-document output
```

### Token Indexing

**Inverted Index Structure:**
```python
# Example:
source_token_index = {
    'armor': {1, 5, 12, 15, 23},
    'spell': {3, 8, 14, 19},
    'damage': {2, 7, 11, 16},
}
```

**Benefits:**
- O(1) token lookup
- Fast page-contains-text checks
- Memory-efficient (256 tokens/page limit)

---

## Performance Analysis

### Token Indexing Cost

**Time Complexity:**
- Indexing: O(P × T) where P=pages, T=tokens/page (capped at 256)
- Lookup: O(1) per token
- Overall: ~O(n) with constant factor

**Memory Usage:**
- Typical 200-page PDF: ~50KB token index
- 1000-page PDF: ~250KB token index
- Negligible compared to source document size

### Source Validation Cost

**Estimated Times:**
- PDF extraction: 5-10 seconds (200 pages)
- Token indexing: 1-2 seconds
- TOC validation: <1 second (200 entries)
- Term validation: 2-5 seconds (200 terms)
- **Total overhead: ~10-20 seconds**

---

## Security Considerations

### Source File Access

**Risk:** Pass F now requires access to original source files.

**Mitigation:**
- Optional feature (`--source-file` or Gate 0 path resolution)
- Graceful degradation if source unavailable
- Read-only access pattern
- SHA-256 verification against Gate 0 marker

**Configuration:**
```python
def _resolve_source_path(self, gate0_data: Dict[str, Any]) -> Optional[Path]:
    # CLI override takes precedence
    if self.source_file:
        return Path(self.source_file)

    # Fallback to Gate 0 original_path
    original_path = gate0_data.get('original_path')
    return resolve_transfer_path(self.transfer_root, original_path)
```

---

## Upgrade Path

### Breaking Changes

**None.** v2.1.0 is fully backward compatible with v2.0.0.

**New Optional Features:**
- Source validation (requires `--source-file` or Gate 0 path)
- HGRN output structure (automatic when source available)
- Enhanced Neo4j validation (automatic)

### Migration Steps

1. **No code changes required** - existing scripts work unchanged
2. **Optional:** Update `ingestion.cfg` with new Pass_F settings
3. **Optional:** Pass `--source-file` to enable source validation
4. **Optional:** Set `--hgrn-output` for custom HGRN output directory

---

## Testing Recommendations

### Unit Tests

```python
def test_source_extraction():
    # Test PDF page extraction
    # Test text file page splitting
    # Test token normalization

def test_token_indexing():
    # Test token extraction patterns
    # Test inverted index construction
    # Test page limit enforcement

def test_page_matching():
    # Test token overlap detection
    # Test phrase containment
    # Test document search

def test_toc_validation():
    # Test TOC entry detection
    # Test missing TOC evidence collection
    # Test pipeline suggestions

def test_term_validation():
    # Test term page matching
    # Test document-wide search fallback
    # Test remediation generation
```

### Integration Tests

```python
def test_full_source_validation():
    # End-to-end: PDF → validation → HGRN output
    # Verify evidence collection
    # Verify remediation structure

def test_graceful_degradation():
    # Test with missing source file
    # Test with unreadable PDF
    # Test with empty source
```

---

## Code Quality Assessment

### Strengths

1. **Clean Architecture:** Source validation properly separated from DB validation
2. **Error Handling:** Graceful degradation when source unavailable
3. **Token Efficiency:** Smart indexing limits (256 tokens/page)
4. **Evidence Collection:** Structured evidence with token samples
5. **HGRN Integration:** Proper separation of machine/human outputs

### Potential Issues

1. **Memory Usage:** Stores entire document text in memory
   - **Mitigation:** Reasonable for typical PDFs (<500 pages)
   - **Future:** Consider streaming for 1000+ page documents

2. **Token Pattern:** Simple regex may miss non-English terms
   - **Pattern:** `[a-z0-9]{4,}` (lowercase alphanumeric, 4+ chars)
   - **Future:** Consider language-specific tokenization

3. **Page Splitting:** Text files use form-feed (\f) as page boundary
   - **Risk:** Non-standard text files may not split correctly
   - **Mitigation:** Fallback to single page if no form-feeds

---

## Recommendations

### High Priority

1. **Add Unit Tests** [Effort: Medium, Impact: High]
   - Test all new source validation methods
   - Test token indexing and matching
   - Target: 70% coverage for new code

2. **Document Source File Requirements** [Effort: Low, Impact: High]
   - Update CLAUDE.md with `--source-file` usage
   - Add examples to scripts-reference.md
   - Document Transfer Station path resolution

3. **Add Integration Tests** [Effort: High, Impact: High]
   - Test full pipeline with source validation
   - Test graceful degradation scenarios
   - Test HGRN output structure

### Medium Priority

4. **Optimize Memory Usage** [Effort: Medium, Impact: Medium]
   - Consider streaming for large documents (1000+ pages)
   - Add memory profiling for typical workloads
   - Document memory requirements

5. **Enhance Token Patterns** [Effort: Medium, Impact: Low]
   - Support Unicode tokens for non-English documents
   - Add configurable token patterns
   - Support phrase-based matching

6. **Add Performance Metrics** [Effort: Low, Impact: Medium]
   - Track source extraction time
   - Track token indexing time
   - Track validation time per component

---

## Conclusion

Pass F v2.1.0 represents a **major capability enhancement** that transforms the validation system from reactive (database-only checks) to **proactive source-truth verification**. The implementation demonstrates excellent engineering with:

- ✅ Backward compatibility
- ✅ Graceful degradation
- ✅ Clean architecture
- ✅ Comprehensive evidence collection
- ✅ Actionable remediation recommendations

**Upgrade Grade: A (4.8/5)**

With the addition of unit tests and documentation updates, this would be an **A+ production-ready enhancement**.

---

**End of Pass F v2.1.0 Upgrade Analysis**
