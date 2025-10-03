# Pass A TOC-Only Refactor Plan

## Current Status

Pass A currently:
- Uses PyMuPDF (fitz) to parse **entire PDF**
- Extracts document structure via `toc_parser.parse_document_structure()`
- Generates dictionary entries from ToC
- Creates artifacts: `{job_id}_pass_a_dict.json`, `{job_id}_pass_a_categories.json`, manifest

## AI Prompt Spec Requirements (Gate 0 + Pass A)

### Pass A Must:
1. **Identify TOC page range** (typically first 2-5 pages)
   - Indicators: "Table of Contents" heading, page numbers aligned right, dot leaders (`....`)
   - If ambiguous, mark confidence in results

2. **Use Unstructured.io ONLY on TOC pages**
   - Extract blocks (heading, paragraph, etc.) with text, bbox, page
   - If TOC page is scanned, OCR must run via Unstructured.io

3. **Apply TOC-specific heuristics:**
   - Look for patterns: `title … page_number`
   - Parse hierarchical structure (indentation, numbering: 1, 1.1, I, A, etc.)
   - Assign stable `section_id = sha1(title+start_page)`

4. **Create passA.toc.json:**
   ```json
   {
     "doc_id": "...",
     "sections": [
       {
         "section_id": "A1",
         "title": "Chapter 1: Character Creation",
         "start_page": 1,
         "end_page": 12,
         "level": 1
       }
     ]
   }
   ```

5. **Seed dictionary** for system/edition names and major sections

## Implementation Plan

### Phase 1: TOC Page Detection (Pass 0.5 enhancement)
- Add `detect_toc_pages()` function to `pass_0_preflight.py`
- Detect pages with TOC indicators (first 10 pages max)
- Return: `(toc_page_range: tuple[int, int], confidence: float)`
- Include in `gate0.report.json` as `toc_pages: {start, end, confidence}`

### Phase 2: Unstructured.io TOC Extraction
- Create `pass_a_toc_extraction.py` (new module)
- Use Unstructured.io `partition_pdf()` with page range parameter
- Extract only TOC pages specified from Pass 0
- Parse extracted elements for TOC structure

### Phase 3: TOC-Specific Heuristics
- Implement `TocHeuristicParser` class
- Pattern matching: `title … page_number` with regex
- Hierarchical structure detection (indentation, numbering schemes)
- Section ID generation: `sha1(title + start_page)`
- End page inference (next section's start_page - 1)

### Phase 4: passA.toc.json Output
- Generate spec-compliant JSON structure
- Fields: doc_id, sections[{section_id, title, start_page, end_page, level}]
- Write to `pass_a/passA.toc.json`

### Phase 5: Dictionary Seeding (keep existing logic)
- Seed from passA.toc.json sections
- System/edition name detection
- Major section categorization
- Write to `pass_a/{job_id}_pass_a_dict.json`

### Phase 6: Regression Tests
- Test TOC page detection with various PDFs
- Test Unstructured.io integration
- Test heuristic parsing accuracy
- Test passA.toc.json format compliance
- Integration test: Pass 0 → Pass A flow

## File Changes

### New Files:
- `src_common/pass_a_toc_extraction.py` - Unstructured.io TOC extraction
- `tests/regression/test_pass_a_toc_only.py` - Regression test suite

### Modified Files:
- `src_common/pass_0_preflight.py` - Add TOC page detection
- `src_common/pass_a_toc_parser.py` - Refactor to use TOC-only approach
- `src_common/admin/ingestion.py` - Pass TOC pages from Pass 0 to Pass A
- `tests/regression/test_pass_0_gate0.py` - Add TOC detection tests

## Backwards Compatibility

Maintain both approaches:
- New: TOC-only extraction via Unstructured.io (spec-compliant)
- Legacy: Full document parse via PyMuPDF (fallback)
- Config flag: `USE_TOC_ONLY_EXTRACTION=true` (default: true)

## Success Criteria

1. ✅ TOC pages detected with >90% accuracy on test corpus
2. ✅ Unstructured.io successfully extracts TOC-only content
3. ✅ passA.toc.json format matches AI spec exactly
4. ✅ Hierarchical structure parsed correctly (levels 1-3+)
5. ✅ Section IDs stable (sha1-based)
6. ✅ Dictionary seeding works from new format
7. ✅ Regression tests pass with 100% success rate
8. ✅ Integration with Pass B (logical splitting uses passA.toc.json)

## Timeline Estimate

- Phase 1 (TOC detection): 2 hours
- Phase 2 (Unstructured.io): 3 hours
- Phase 3 (Heuristics): 4 hours
- Phase 4 (JSON format): 1 hour
- Phase 5 (Dict seeding): 2 hours
- Phase 6 (Tests): 3 hours

**Total: ~15 hours**

## Risk Mitigation

**Risk**: Unstructured.io may not parse TOC accurately
**Mitigation**: Implement PyMuPDF fallback for TOC parsing

**Risk**: TOC page detection false positives/negatives
**Mitigation**: Manual override option in configuration, confidence scoring

**Risk**: Breaking existing Pass A workflows
**Mitigation**: Feature flag for gradual rollout, maintain legacy mode
