# Memory: Ingestion Phases (Contract)

The ingestion pipeline is divided into six distinct, ordered phases.  
Each phase must emit structured status events (`status-schema.md`) and be resumable if interrupted.

## Phases

1. **Upload → Temp Storage**
   - Accept single or bulk file uploads.
   - Save securely in environment-specific temp storage.
   - Emit file size, progress %, and ETA.

2. **Chunking**
   - Parse into single-concept chunks.
   - Preserve page numbers and section references.
   - Emit last 2–3 chunks in plain language preview.

3. **Dictionary / Metadata Extraction**
   - Populate required metadata:
     - title, publisher, ISBN, system, chapter/section/sub-section
   - Dynamically add tags when needed (e.g., spell.school, feat.type).
   - Update dictionary for cross-system normalization.

4. **Embeddings + Upsert → AstraDB**
   - Generate embeddings (OpenAI).
   - Upsert chunks into AstraDB with metadata.
   - Batch writes, retry on failures.

5. **Enrichment**
   - Optional classifiers or advanced enrichment (spell schools, archetypes, etc.).
   - Provenance and audit trail recorded.

6. **Verify & Commit**
   - Write manifest (counts, metadata summary, errors).
   - Confirm job complete.
   - Unlock any file handles.

## Rules
- Each phase emits `status=queued|running|stalled|error|done`.
- Progress should be visible in Admin UI with per-phase bars.
- Errors must be actionable and logged.
- Phases must be independent: restarting one does not repeat prior completed phases unnecessarily.

## Definition of Done
- Ingestion runs reliably end-to-end with all six phases.
- Admin UI shows live progress for each phase.
- Dictionary is inspectable in **natural language** (not raw JSON/MD).
- Chunks + metadata appear in AstraDB with accurate provenance.
