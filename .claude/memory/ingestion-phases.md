# Memory: Six Ingestion Phase Contract

The ingestion pipeline must execute these **6 phases** in order, with status events published for each phase.

## Phase Definitions

### 1. Upload ’ Temp Storage
- **Purpose**: Receive file, validate, store temporarily
- **Status Updates**: File size progress, ETA
- **Outputs**: Temp file path, file metadata

### 2. Chunking  
- **Purpose**: Parse and segment content into searchable chunks
- **Status Updates**: Chunk count progress, last 2-3 chunk previews in natural language
- **Outputs**: Structured chunks with positional metadata

### 3. Dictionary/Metadata Extraction
- **Purpose**: Extract title, publisher, ISBN, system, chapter/section/sub-section
- **Status Updates**: Terms discovered, dynamic tags like `spell/school`
- **Outputs**: Enriched metadata, normalized terminology

### 4. Embeddings + Upsert ’ AstraDB
- **Purpose**: Generate embeddings and store in vector database
- **Status Updates**: Batch progress, retry attempts
- **Outputs**: Vector embeddings stored in AstraDB

### 5. Enrichment
- **Purpose**: Optional classifiers, record provenance
- **Status Updates**: Classification progress
- **Outputs**: Enhanced chunk metadata, provenance records

### 6. Verify & Commit
- **Purpose**: Write summary manifest, mark job complete
- **Status Updates**: Verification checks, final manifest
- **Outputs**: Job completion status, summary manifest

## Status Publishing Requirements
For each phase, publish:
- `status` (queued|running|stalled|error|done)
- `progress` 0100
- `updated_at` timestamp
- Recent logs (last 10-20 lines)
- Actionable error details if applicable

## Admin UI Integration
- Separate progress bars per phase
- Rolling log tail display
- Error surfacing with remediation hints
- Global "Shutdown" capability to safely cancel jobs