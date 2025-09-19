# Ingestion Pipeline Runbook: Pass A-G Architecture

**Document Type:** Operational Runbook
**Last Updated:** 2025-09-19
**Status:** Active
**Scope:** TTRPG Center Ingestion Pipeline

---

## Overview

The TTRPG Center ingestion pipeline processes TTRPG PDFs through a seven-pass architecture (Pass A-G) that transforms raw documents into structured, searchable content with vector embeddings and knowledge graphs.

**Pipeline Flow:**
```
PDF Input → Pass A → Pass B → Pass C → Pass D → Pass E → Pass F → Pass G → Complete
```

---

## Pass Architecture Detail

### Pass A: TOC Parser
**Module:** `src_common/pass_a_toc_parser.py`
**Function:** `process_pass_a(job_id, file_path, config)`
**Purpose:** Extract Table of Contents structure using OpenAI API

**Input:** Raw PDF file
**Output:** Structured TOC metadata with chapters and sections
**Dependencies:** OpenAI API client, PDF parsing utilities
**Typical Duration:** 30-60 seconds depending on document complexity

**Key Operations:**
- PDF text extraction for TOC identification
- OpenAI API calls for structure recognition
- Chapter/section hierarchy mapping
- Metadata generation for downstream passes

**Success Criteria:**
- `processed_count > 0` (chapters/sections identified)
- `artifact_count > 0` (TOC structure artifacts created)
- `success = True`

---

### Pass B: Logical Splitter
**Module:** `src_common/pass_b_logical_splitter.py`
**Function:** `process_pass_b(job_id, toc_data, config)`
**Purpose:** Split PDF into logical sections based on TOC structure

**Input:** PDF file + TOC metadata from Pass A
**Output:** Split PDF parts preserving original document IDs
**Dependencies:** PDF manipulation libraries, TOC structure
**Typical Duration:** 15-45 seconds depending on document size

**Key Operations:**
- PDF section boundary identification
- Document splitting while preserving linkage
- Original `doc_id` preservation across parts
- Chapter metadata attachment to parts

**Success Criteria:**
- `processed_count` equals number of logical sections
- `artifact_count` matches split parts created
- All parts retain original document ID linkage

---

### Pass C: Content Extraction
**Module:** `src_common/pass_c_extraction.py`
**Function:** `process_pass_c(job_id, split_parts, config)`
**Purpose:** Extract structured content using unstructured.io

**Input:** Split PDF parts from Pass B
**Output:** Structured document elements and text chunks
**Dependencies:** unstructured.io v0.18.15, Poppler, Tesseract
**Typical Duration:** 2-10 minutes depending on document size and complexity

**Key Operations:**
- unstructured.io element extraction
- Text chunking with size optimization
- Image and table detection
- Element type classification (title, paragraph, list, etc.)

**Success Criteria:**
- `processed_count` reflects pages/sections processed
- `artifact_count` shows extracted elements
- Serialized artifacts stored in job artifacts directory

---

### Pass D: Vector Enrichment
**Module:** `src_common/pass_d_vector_enrichment.py`
**Function:** `process_pass_d(job_id, extracted_content, config)`
**Purpose:** Generate vector embeddings using Haystack framework

**Input:** Structured content from Pass C
**Output:** Vector embeddings and enriched metadata
**Dependencies:** Haystack framework, embedding models, vector store
**Typical Duration:** 3-15 minutes depending on content volume

**Key Operations:**
- Text chunk vectorization
- Metadata enrichment with semantic tags
- Vector store preparation
- Embedding quality validation

**Success Criteria:**
- `processed_count` equals chunks processed
- `artifact_count` shows vectors generated
- Vector store receives embeddings

---

### Pass E: Graph Builder
**Module:** `src_common/pass_e_graph_builder.py`
**Function:** `process_pass_e(job_id, enriched_content, config)`
**Purpose:** Build knowledge graph using LlamaIndex

**Input:** Enriched content from Pass D
**Output:** Knowledge graph nodes and relationships
**Dependencies:** LlamaIndex framework, graph database
**Typical Duration:** 5-20 minutes depending on content complexity

**Key Operations:**
- Entity extraction and recognition
- Relationship identification
- Graph node creation
- Edge relationship mapping

**Success Criteria:**
- `processed_count` reflects entities processed
- `artifact_count` shows nodes/edges created
- Graph database contains new structures

---

### Pass F: Finalizer
**Module:** `src_common/pass_f_finalizer.py`
**Function:** `process_pass_f(job_id, graph_data, config)`
**Purpose:** Cleanup and finalization operations

**Input:** Complete processing artifacts from previous passes
**Output:** Consolidated artifacts and cleanup confirmations
**Dependencies:** Storage systems, cleanup utilities
**Typical Duration:** 30-90 seconds

**Key Operations:**
- Artifact consolidation
- Temporary file cleanup
- Index updates
- Final validation checks

**Success Criteria:**
- All temporary artifacts cleaned
- Consolidated outputs properly stored
- Index systems updated

---

### Pass G: HGRN Validation
**Module:** HGRN validation via `HGRNRunner::run_pass_d_validation()`
**Purpose:** Quality validation of processed content

**Input:** All processing outputs from Passes A-F
**Output:** Validation results and quality metrics
**Dependencies:** HGRN validation framework
**Typical Duration:** 1-3 minutes

**Key Operations:**
- Content quality validation
- Structural integrity checks
- Metadata consistency validation
- Performance metrics collection

**Success Criteria:**
- Validation passes quality thresholds
- No structural inconsistencies detected
- Quality metrics within acceptable ranges

---

## Pipeline Execution Flow

### Normal Execution Path

1. **Job Initialization**
   - Job ID assignment
   - Artifact directory creation
   - Configuration loading

2. **Sequential Pass Execution**
   - Each pass validates previous pass outputs
   - Structured logging for each operation
   - Error propagation on failures

3. **Gate 0 Optimization**
   - SHA-based file deduplication
   - Skip processing for identical files
   - Bypass marker creation for audit

4. **Result Aggregation**
   - Pass results collected
   - Overall job status determination
   - Artifact finalization

### Error Handling

**Pass Failure Protocol:**
- Immediate pipeline halt on pass failure
- Error details logged with context
- Partial artifacts preserved for debugging
- Job marked as failed with specific pass indicated

**Recovery Mechanisms:**
- Individual pass retry capability
- Partial completion resume support
- Artifact cleanup on failure
- Error reporting to monitoring systems

---

## Operational Procedures

### Monitoring and Observability

**Key Metrics to Monitor:**
- Pass execution times (SLA: see typical durations above)
- Success/failure rates per pass
- Artifact counts and storage growth
- Resource utilization (CPU, memory, storage)

**Alert Conditions:**
- Pass execution time exceeding 3x typical duration
- Pass failure rate > 5% over 1-hour window
- Missing artifacts after successful pass completion
- Resource utilization > 85% sustained

### Troubleshooting Guide

**Common Issues:**

1. **Pass A Failures (TOC Parser)**
   - Check OpenAI API connectivity and quota
   - Verify PDF is text-extractable (not pure image)
   - Validate file format and corruption

2. **Pass B Failures (Logical Splitter)**
   - Ensure TOC data from Pass A is valid
   - Check PDF manipulation library dependencies
   - Verify sufficient disk space for split parts

3. **Pass C Failures (Content Extraction)**
   - Confirm unstructured.io service availability
   - Check Poppler and Tesseract installation
   - Validate input file formats and sizes

4. **Pass D Failures (Vector Enrichment)**
   - Verify Haystack framework configuration
   - Check embedding model availability
   - Validate vector store connectivity

5. **Pass E Failures (Graph Builder)**
   - Confirm LlamaIndex dependencies
   - Check graph database connectivity
   - Validate input data structure

6. **Pass F/G Failures (Finalization/Validation)**
   - Check storage system availability
   - Verify cleanup permissions
   - Validate previous pass outputs

### Performance Optimization

**Optimization Strategies:**
- Gate 0 SHA bypassing for duplicate files
- Parallel processing for independent operations
- Resource pooling for external API calls
- Intelligent chunking for large documents

**Capacity Planning:**
- Monitor average processing times per document size
- Track resource utilization patterns
- Plan for peak load scenarios
- Consider horizontal scaling for high volume

---

## Configuration Management

### Environment-Specific Settings

**Development (env/dev/):**
- Shorter timeouts for faster feedback
- Detailed logging enabled
- Test document processing

**Test (env/test/):**
- Production-like processing
- Comprehensive validation
- Performance benchmarking

**Production (env/prod/):**
- Optimized timeouts
- Essential logging only
- Maximum performance configuration

### Key Configuration Parameters

**Pass-Specific Settings:**
- Timeout values per pass
- Retry attempts and backoff
- Resource allocation limits
- Quality thresholds

**Integration Settings:**
- API endpoints and credentials
- Database connection strings
- Storage locations and permissions
- Monitoring and alerting hooks

---

## Maintenance Procedures

### Regular Maintenance Tasks

**Daily:**
- Monitor pipeline health metrics
- Review error logs for patterns
- Check storage utilization

**Weekly:**
- Artifact cleanup of old jobs
- Performance trend analysis
- Dependency version checks

**Monthly:**
- Full pipeline performance review
- Capacity planning assessment
- Security and compliance validation

### Upgrade Procedures

**Dependency Updates:**
1. Test in development environment
2. Validate with representative documents
3. Performance regression testing
4. Staged rollout to test then production

**Code Updates:**
1. Unit and integration testing
2. End-to-end pipeline validation
3. Performance impact assessment
4. Rollback plan preparation

---

## Emergency Procedures

### Pipeline Failure Response

**Immediate Actions:**
1. Assess impact scope (single job vs. systemic)
2. Preserve error logs and artifacts
3. Determine if immediate rollback needed
4. Communicate status to stakeholders

**Investigation Process:**
1. Review recent changes to pipeline
2. Analyze error patterns and logs
3. Test with known-good documents
4. Isolate problematic components

**Recovery Steps:**
1. Apply fixes or rollback as appropriate
2. Resume processing from failure point
3. Validate fix with test documents
4. Monitor for stability

### Data Integrity Issues

**Detection:**
- Inconsistent artifact counts
- Missing vector embeddings
- Broken graph relationships
- Failed validation checks

**Response:**
1. Halt pipeline immediately
2. Preserve current state
3. Identify affected documents
4. Plan reprocessing strategy

---

## References

- **Implementation Modules:** `src_common/pass_[a-g]_*.py`
- **Test Suite:** `tests/unit/test_bug_032_ingestion_stubs.py`
- **Configuration:** `env/{ENV}/config/.env`
- **Monitoring:** Admin Dashboard - Ingestion section
- **Bug Resolution:** `docs/BUG-032-resolution-analysis.md`