# Ingestion Pipeline Requirements Analysis

**Analysis Date**: 2025-10-30
**Requirements Document**: `Prompt Lib/P01_Fully_Async_Ingestion_Pipeline_Plan.md`
**Implementation Location**: `ingestion/`

---

## Executive Summary

This analysis compares the implemented async ingestion pipeline against the requirements document. The implementation represents a **strong foundation** with ~70% requirement coverage, but has **critical gaps** in worker completeness, schema alignment, and operational tooling.

**Key Findings**:
- ✅ Core architecture correctly implemented (RabbitMQ, Celery, Job Registry)
- ❌ Missing workers: haystack, llamaindex, cassandra_upsert, graph_upsert workers incomplete
- ❌ Schema misalignment: Cassandra schema doesn't match requirements
- ⚠️ Partial implementation: CLI tools exist but lack full functionality
- ⚠️ Missing features: Worker Supervisor, removal jobs, DLQ inspection

---

## Part 1: Requirements Compliance Analysis

### 🔴 CRITICAL MISMATCHES (Must Fix)

#### 1.1 Cassandra Schema Mismatch
**Requirement** (lines 142-156):
```sql
CREATE TABLE IF NOT EXISTS ttrpg_vectors.embeddings (
  source_id       text,
  document_id     text,
  chunk_id        text,
  chunk_index     int,
  text            text,
  metadata        text,                   -- JSON
  vector          vector<float, 1536>,
  PRIMARY KEY ((source_id), document_id, chunk_index)
) WITH clustering order by (document_id ASC, chunk_index ASC);
```

**Implementation** (ingestion/core/db/cassandra_store.py:177-190):
```python
CREATE TABLE IF NOT EXISTS embeddings (
    source_id TEXT,
    chunk_id TEXT,
    chunk_index INT,
    text TEXT,
    page_number INT,
    section_title TEXT,
    text_hash TEXT,
    metadata_hash TEXT,
    vector_hash TEXT,
    embedding vector<float, {dimension}>,
    facets TEXT,
    PRIMARY KEY ((source_id), chunk_index, chunk_id)
)
```

**Issues**:
- ❌ Missing `document_id` column (required for multi-document sources)
- ❌ Wrong primary key clustering: should be `(document_id, chunk_index)` not `(chunk_index, chunk_id)`
- ❌ Missing `metadata` JSON column
- ❌ Extra columns not in spec: `text_hash`, `metadata_hash`, `vector_hash`, `page_number`, `section_title`, `facets`
- ⚠️ Column named `embedding` instead of `vector` (minor deviation)

**Impact**: High - breaks multi-document source support and query patterns

---

#### 1.2 Worker Completeness - Pass B1 (Haystack Chunking)
**Requirement** (lines 119-122):
- Container: `haystack`
- Action: Use Haystack components for chunking/cleaning
- Output: `/Transfer_Station/artifacts/{job_id}/haystack/chunks.json`

**Implementation** (ingestion/workers/haystack/tasks.py:20-36):
```python
def _chunk_placeholder(metadata: List[dict]) -> List[dict]:
    """Placeholder chunking logic until real Haystack integration."""
    chunks = []
    for idx, item in enumerate(metadata, start=1):
        chunks.append({
            "chunk_id": f"chunk-{idx}",
            "chunk_index": idx,
            "text": item.get("text", ""),
            # ...
        })
    return chunks
```

**Issues**:
- ❌ Stub implementation only - no real Haystack integration
- ❌ Missing semantic chunking strategy
- ❌ No document boundaries or overlap handling
- ❌ Placeholder chunking instead of Haystack DocumentSplitter/PreProcessor

**Impact**: Critical - chunks will be low quality, affecting embeddings and retrieval

---

#### 1.3 Worker Completeness - Pass C1 (LlamaIndex Graph Build)
**Requirement** (lines 159-164):
- Container: `llamaindex`
- Action: Build knowledge graph from elements/chunks
- Output: `/Transfer_Station/artifacts/{job_id}/graph/graph.json`

**Implementation** (ingestion/workers/llamaindex/tasks.py:13-44):
```python
def _build_stub_indices(job_id: str) -> dict:
    """Stub implementation for LlamaIndex graph building."""
    # ...placeholder logic...
    return {
        "document_id": job_id,
        "chunks": [],
        # ...
    }
```

**Issues**:
- ❌ Complete stub - no LlamaIndex integration
- ❌ Missing entity extraction
- ❌ Missing relationship extraction
- ❌ No PropertyGraphIndex usage

**Impact**: Critical - no knowledge graph data will be generated

---

#### 1.4 Missing Worker: Worker Supervisor (Node-Local Guardian)
**Requirement** (lines 81-87):
- Deployment: tiny agent on each non-DB node
- Function: Check worker health every 60s
- Restart dead workers
- Emit heartbeats

**Implementation**:
- ❌ Completely missing - no worker supervisor implemented
- ❌ No process monitoring
- ❌ No auto-restart capability
- ❌ No heartbeat telemetry

**Impact**: High - workers can die silently without recovery

---

#### 1.5 Docker Compose Services Missing
**Requirement** (lines 384-387):
- Keep: unstructured, haystack, llamaindex, ingestion_engine
- Remove: MongoDB, Stargate

**Implementation** (docker/docker-compose-async.yml):

**Missing Services**:
- ❌ `haystack` container - not defined
- ❌ `llamaindex` container - not defined
- ❌ `cassandra_upsert` container - not defined (requirement line 132 specifies separate container)
- ❌ `graph_upsert` container - mentioned in requirements but deployment unclear

**Present But Incomplete**:
- ✅ `unstructured_worker` - exists but uses placeholder processing
- ✅ `ingestion_engine` - exists but hosts multiple responsibilities
- ⚠️ MongoDB/Stargate removal status: not verified (not in docker-compose-async.yml)

**Impact**: High - core processing stages cannot execute

---

### 🟡 IMPORTANT MISMATCHES (Should Fix)

#### 2.1 Job ID Generation - Determinism
**Requirement** (line 48):
> JobId: deterministic UUIDv5 generated from normalized source path + last modified time

**Implementation** (ingestion/core/pipeline.py - needs verification):
```python
def deterministic_job_id(source_path: Path) -> str:
    """Generate a deterministic job ID from source path."""
    # Implementation not fully verified for UUIDv5 + mtime
```

**Issues**:
- ⚠️ Need to verify if implementation includes `mtime` in hash
- ⚠️ Need to verify UUIDv5 vs other hash methods
- ⚠️ Normalization strategy unclear

**Impact**: Medium - affects refresh detection and duplicate prevention

---

#### 2.2 Removal Jobs Not Implemented
**Requirement** (lines 371-378):
- Remove dictionary rows, Cassandra embeddings, Neo4j nodes/edges
- Remove artifacts
- Write REMOVED state
- Requires `--yes` confirmation

**Implementation**:
- ❌ `job_management remove` command stub only (ingestion/cli/job_management.py:118-134)
- ❌ No full-delete orchestration logic
- ❌ No confirmation prompts implemented
- ❌ Housekeeping worker has partial removal (ingestion/workers/housekeeping/tasks.py:62-90) but not complete

**Impact**: Medium - cannot cleanly remove sources from system

---

#### 2.3 Health Check - Nightly Verification Incomplete
**Requirement** (lines 281-291):
- Recompute Cassandra checksum per-source
- Compare against expected_checksum
- Validate Neo4j node/edge counts
- Validate Postgres term counts
- Mark UNHEALTHY and queue refresh on mismatch

**Implementation** (ingestion/workers/health_verifier/tasks.py:74-116):
```python
def verify(self) -> Dict[str, int]:
    # Only validates from artifacts, not live DB recomputation
    chunks = load_embeddings(job.job_id, _settings)
    checksum, row_count = compute_checksum(job.job_id, chunks)
```

**Issues**:
- ⚠️ Checksum computed from artifacts, not from Cassandra live data
- ❌ No Neo4j node/edge count validation
- ❌ No Postgres dictionary term count validation
- ⚠️ "Live DB verification" requirement not met

**Impact**: Medium - health checks less reliable, miss DB corruption

---

#### 2.4 CLI Tools - Partial Implementation

##### status_monitor
**Requirement** (lines 308-317):
- Show state + stage + next worker
- Display chunks count, dictionary term count
- Show expected vs verified checksum
- Health status: OK | UNHEALTHY | PENDING

**Implementation** (ingestion/cli/status_monitor.py):
- ✅ Job registry display working
- ✅ `--deep` flag fetches live counts
- ❌ Missing "next worker" derivation from routing plan
- ⚠️ No explicit "Health: OK | UNHEALTHY | PENDING" field
- ✅ Checksum display present

**Impact**: Low-Medium - monitoring less effective

---

##### log_monitor
**Requirement** (lines 319-323):
- Tail consolidated logs
- `--errors` flag: show 10 most recent errors with job_id, stage, message
- Multi-file tail from /Transfer_Station/logs

**Implementation** (ingestion/cli/log_monitor.py:7-54):
```python
def main(argv: list[str] | None = None) -> int:
    # Stub implementation
    print("Log monitoring not yet implemented.")
    return 1
```

**Issues**:
- ❌ Complete stub - no log tailing
- ❌ No error filtering
- ❌ No multi-file aggregation

**Impact**: Medium - operational visibility severely limited

---

##### job_management
**Requirement** (lines 325-330):
- `start --file "<filename.pdf>" [--refresh]` - manual enqueue
- `mark-unhealthy --file "<filename.pdf>"` - flag + queue refresh
- `remove --file "<filename.pdf>"` - removal job with `--yes` confirmation

**Implementation** (ingestion/cli/job_management.py:7-161):
- ✅ `start` command implemented (lines 41-82)
- ✅ `mark-unhealthy` command implemented (lines 85-110)
- ⚠️ `remove` command stub only (lines 113-134) - no actual orchestration
- ⚠️ Missing `--yes` safety confirmations on destructive operations

**Impact**: Medium - limited manual control over jobs

---

#### 2.5 Message Contract - Incomplete Fields
**Requirement** (lines 334-352):
- All tasks must include: job_id, source_id, source_path, refresh, artifacts_dir, status_file, trace_id
- Stage-specific additions for A1, B2, B3, C2

**Implementation** (various workers):
```python
# Current task signatures only pass job_id or (job_id, source_path)
@shared_task(bind=True, name="unstructured.process", queue="unstructured")
def process_document(self, job_id: str, source_path: str) -> str:
```

**Issues**:
- ⚠️ Most tasks only receive `job_id`
- ❌ Missing explicit `trace_id` in payloads
- ⚠️ `artifacts_dir` and `status_file` derived internally, not passed
- ❌ Stage-specific options not in task signatures

**Impact**: Low-Medium - harder to debug and trace

---

### 🟢 MINOR DEVIATIONS (Nice to Have)

#### 3.1 Postgres Schema - Minor Naming Differences
**Requirement** (lines 222-276):
- Schema: `dictionary.sources` and `dictionary.terms`
- Schema: `jobs.registry` and `jobs.history`

**Implementation**:
- Dictionary: `ingestion_dictionary` table (flat, no schema) - ingestion/core/db/dictionary.py:95
- Jobs: `ingestion_jobs` and `ingestion_jobs_history` (flat, no schema) - ingestion/core/job_registry.py:189-214

**Issues**:
- ⚠️ No separate schemas created (`dictionary`, `jobs`)
- ⚠️ Table names prefixed instead: `ingestion_dictionary`, `ingestion_jobs`
- ✅ Column structure mostly matches

**Impact**: Low - functional but organizational

---

#### 3.2 Retry Policy Configuration
**Requirement** (lines 362-367):
- Default max 5 attempts: 30s, 2m, 5m, 15m, 45m + jitter
- Exponential backoff with specific timings

**Implementation** (ingestion/core/celery_app.py:46-54):
```python
task_annotations={
    "*": {
        "autoretry_for": (Exception,),
        "retry_kwargs": {"max_retries": cfg.retry_max_retries},  # 5
        "retry_backoff": cfg.retry_backoff,  # 2.0
        "retry_backoff_max": cfg.retry_max_wait,  # 900s
        "retry_jitter": cfg.retry_jitter,  # 15s
    }
}
```

**Issues**:
- ✅ Max retries: 5 ✓
- ⚠️ Backoff multiplier: 2.0 (generic exponential)
- ⚠️ Initial wait: 30s configurable ✓
- ⚠️ Not exact timing sequence from requirements (30s, 2m, 5m, 15m, 45m)
- ✅ Jitter present ✓

**Impact**: Very Low - retry behavior close enough

---

#### 3.3 DLQ Inspection Tool
**Requirement** (lines 367):
- Provide `dlq_inspect` subcommand in `job_management`

**Implementation**:
- ❌ No DLQ inspection subcommand
- ✅ DLQ worker exists (ingestion/workers/dlq/tasks.py) but inspection missing

**Impact**: Low - DLQ messages can't be easily inspected

---

#### 3.4 Observability - OpenTelemetry Integration
**Requirement** (lines 55-59):
- Tracing: OpenTelemetry (trace job across passes)
- Metrics: Prometheus endpoints
- Structured logging: JSON to `/Transfer_Station/logs`

**Implementation**:
- ✅ Tracing framework exists (ingestion/core/tracing.py) with `start_span`
- ✅ Metrics framework exists (ingestion/core/metrics.py)
- ✅ Structured logging (ingestion/core/observability/logging.py)
- ⚠️ OpenTelemetry exporters not configured (traces stay in-memory)
- ⚠️ Prometheus endpoint setup not verified
- ⚠️ Log collector integration (ELK/Vector) not configured

**Impact**: Low - framework exists, needs configuration

---

#### 3.5 Neo4j Constraints
**Requirement** (lines 174-183):
```cypher
CREATE CONSTRAINT source_unique IF NOT EXISTS
FOR (s:Source) REQUIRE s.source_id IS UNIQUE;

CREATE CONSTRAINT entity_unique IF NOT EXISTS
FOR (e:Entity) REQUIRE e.entity_id IS UNIQUE;

CREATE CONSTRAINT chunk_unique IF NOT EXISTS
FOR (c:Chunk) REQUIRE c.chunk_id IS UNIQUE;
```

**Implementation** (ingestion/core/db/graph_store.py:132-141):
```python
self._session.run(
    "CREATE CONSTRAINT document_document_id IF NOT EXISTS "
    "FOR (d:Document) REQUIRE d.document_id IS UNIQUE"
)
```

**Issues**:
- ✅ Document constraint implemented
- ❌ Missing Source constraint
- ❌ Missing Entity constraint
- ❌ Missing Chunk constraint

**Impact**: Low-Medium - can cause duplicate nodes

---

## Part 2: Best Practices & Improvements

### 4.1 Architecture & Design

#### 4.1.1 Separation of Concerns - Database Clients
**Current Issue**: `ingestion_engine` worker hosts dictionary upsert logic

**Recommendation**:
```
✅ BETTER:
- Dictionary upsert → dedicated `dictionary_worker` container
- Neo4j upsert → dedicated `graph_worker` container
- Cassandra upsert → dedicated `cassandra_worker` container (partially done)
- ingestion_engine → orchestration + metadata enrichment only

RATIONALE:
- Clearer queue routing (req line 43: "named queues by domain")
- Easier scaling per bottleneck
- Matches requirement intent (lines 109, 132, 167)
```

---

#### 4.1.2 Worker Task Naming Consistency
**Current Issue**: Inconsistent naming patterns

**Current**:
```python
# Mixed patterns
"unstructured.process"              # good
"ingestion_engine.orchestrate"      # orchestration task
"ingestion_engine.elements_to_metadata"  # processing task
"ingestion_engine.dictionary_upsert"     # database task
"cassandra_upsert.write"            # good
```

**Recommendation**:
```python
# Consistent pattern: <domain>.<action>
"unstructured.process"
"ingestion_engine.orchestrate"
"ingestion_engine.enrich_metadata"   # renamed
"dictionary.upsert"                  # moved to dictionary worker
"embeddings.generate"                # clearer than haystack.generate_embeddings
"cassandra.upsert"
"llamaindex.build_graph"
"graph.upsert"
"housekeeping.cleanup"
"health.verify"
```

---

#### 4.1.3 Job State Transitions - Explicit State Machine
**Current Issue**: State transitions implicit in worker code

**Recommendation**:
```python
# Add explicit state machine with validation
class JobStateMachine:
    TRANSITIONS = {
        JobState.NEW: [JobState.QUEUED],
        JobState.QUEUED: [JobState.RUNNING, JobState.FAILED],
        JobState.RUNNING: [JobState.STAGED, JobState.FAILED],
        JobState.STAGED: [JobState.UPSERTING, JobState.FAILED],
        JobState.UPSERTING: [JobState.VERIFYING, JobState.FAILED],
        JobState.VERIFYING: [JobState.CLEANUP, JobState.FAILED],
        JobState.CLEANUP: [JobState.COMPLETED, JobState.FAILED],
        JobState.FAILED: [JobState.QUEUED],  # retry
    }

    def transition(self, from_state: JobState, to_state: JobState) -> bool:
        allowed = self.TRANSITIONS.get(from_state, [])
        if to_state not in allowed:
            raise InvalidStateTransition(f"{from_state} → {to_state} not allowed")
        return True
```

**Benefits**:
- Prevents invalid state transitions
- Clear audit trail
- Easier debugging
- Self-documenting workflow

---

### 4.2 Data Quality & Validation

#### 4.2.1 Schema Validation on Artifacts
**Current Issue**: No validation that artifacts match expected schema

**Recommendation**:
```python
# Add Pydantic models for all artifacts
from pydantic import BaseModel, Field
from typing import List, Dict, Any

class UnstructuredElement(BaseModel):
    text: str
    page_number: int | None = None
    element_type: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

class ElementsArtifact(BaseModel):
    elements: List[UnstructuredElement]
    version: str = "1.0"

def validate_elements_artifact(path: Path) -> ElementsArtifact:
    """Validate and parse elements.json"""
    data = json.loads(path.read_text())
    return ElementsArtifact.model_validate(data)
```

**Benefits**:
- Early error detection
- Clear contract between stages
- Version evolution support
- Auto-generated documentation

---

#### 4.2.2 Checksum Algorithm Specification
**Current Issue**: Checksum computation logic not clearly documented

**Current** (ingestion/workers/common/embeddings.py:49-82):
```python
def compute_checksum(job_id: str, chunks: List[dict]) -> Tuple[str, int]:
    hasher = hashlib.sha256()
    for chunk in sorted(chunks, key=lambda c: (c["chunk_index"], c["chunk_id"])):
        # ... hash individual fields
```

**Recommendation**:
```python
# Document algorithm clearly
"""
Cassandra Checksum Algorithm v1:

1. Sort chunks by (chunk_index ASC, chunk_id ASC)
2. For each chunk:
   a. Concatenate: chunk_id|text_hash|metadata_hash|vector_hash
   b. Update running SHA-256
3. Return hexdigest

Requirements: Deterministic, collision-resistant, supports refresh validation
Specified in: P01 requirements line 288-290
"""
```

---

#### 4.2.3 Input Validation on Enqueue
**Current Issue**: No validation that source files are processable

**Recommendation**:
```python
# Add pre-flight validation
def validate_source(path: Path) -> ValidationResult:
    """Validate source file before enqueueing"""
    checks = [
        check_file_exists(path),
        check_file_readable(path),
        check_file_size(path, max_mb=500),  # configurable
        check_mime_type(path, allowed=['application/pdf', 'application/zip']),
        check_not_corrupted(path),
    ]
    return ValidationResult.from_checks(checks)

# In source_sentinel.py
if not validate_source(path).is_valid:
    _LOG.warning("Skipping invalid source", extra={"path": str(path)})
    continue
```

**Benefits**:
- Fail fast on bad inputs
- Clear error messages
- Reduced wasted processing
- DLQ pollution prevention

---

### 4.3 Performance & Scalability

#### 4.3.1 Batch Size Configuration Per Stage
**Current Issue**: Single global `EMBEDDING_BATCH_SIZE=64`

**Recommendation**:
```python
# Per-stage batch configuration
class BatchConfig:
    unstructured_pages_per_batch: int = 10
    embedding_chunks_per_batch: int = 128  # OpenAI limit
    cassandra_upsert_batch_size: int = 50  # CQL batch size
    neo4j_upsert_batch_size: int = 100
    dictionary_upsert_batch_size: int = 200

# Allows independent tuning per bottleneck
```

---

#### 4.3.2 Idempotency Markers - TTL
**Current Issue**: Idempotency markers persist indefinitely

**Current** (ingestion/core/idempotency.py):
```python
def mark_stage_completed(...):
    marker_path = idempotency_dir / f"{stage}.done"
    marker_path.write_text(...)  # no TTL
```

**Recommendation**:
```python
# Add configurable TTL
def mark_stage_completed(
    settings: Settings,
    job_id: str,
    stage: str,
    fingerprint: str | None = None,
    details: dict | None = None,
    ttl_days: int = 30,  # configurable
) -> None:
    marker_data = {
        "fingerprint": fingerprint,
        "details": details,
        "expires_at": (datetime.now() + timedelta(days=ttl_days)).isoformat(),
    }
    # ...
```

**Benefits**:
- Automatic cleanup of stale markers
- Prevents disk bloat
- Forces re-validation after TTL

---

#### 4.3.3 Connection Pooling Configuration
**Current Issue**: Pool sizes not configurable

**Recommendation**:
```python
# Add pool configuration
class DatabaseConfig:
    postgres_pool_min: int = 2
    postgres_pool_max: int = 10
    cassandra_pool_size: int = 5
    neo4j_pool_size: int = 5

# Allows tuning for high-concurrency scenarios
```

---

### 4.4 Operational Excellence

#### 4.4.1 Structured Logging - Trace Context Propagation
**Current Issue**: `trace_id` not consistently propagated

**Recommendation**:
```python
# Add trace context to all log calls
import contextvars

trace_context = contextvars.ContextVar("trace_id", default=None)

def _log_with_context(logger, level, msg, **extra):
    trace_id = trace_context.get()
    if trace_id:
        extra["trace_id"] = trace_id
    getattr(logger, level)(msg, extra=extra)

# In each worker task:
@shared_task(bind=True, ...)
def process_document(self, job_id: str, ...):
    trace_context.set(str(uuid4()))  # from message or generate
    _LOG.info("Processing started", extra={"job_id": job_id})
```

**Benefits**:
- End-to-end trace visibility
- Easier debugging across workers
- OpenTelemetry integration readiness

---

#### 4.4.2 Metrics - Standard Labels
**Current Issue**: Inconsistent metric labeling

**Recommendation**:
```python
# Standard metric labels
METRIC_LABELS = {
    "stage": ["unstructured", "metadata", "dictionary", "embeddings", ...],
    "state": ["queued", "running", "completed", "failed"],
    "worker": ["source_sentinel", "unstructured", "ingestion_engine", ...],
    "refresh": ["true", "false"],
}

# Use in all metrics
task_duration.labels(
    stage=stage,
    state="completed",
    worker=worker_name,
).observe(duration)
```

---

#### 4.4.3 Health Endpoints Per Worker
**Current Issue**: No per-worker health checks

**Recommendation**:
```python
# Add /health and /ready endpoints to each worker container
from flask import Flask, jsonify

health_app = Flask("health")

@health_app.route("/health")
def health():
    """Liveness check"""
    return jsonify({"status": "healthy"}), 200

@health_app.route("/ready")
def ready():
    """Readiness check - verify dependencies"""
    checks = {
        "rabbitmq": check_rabbitmq_connection(),
        "postgres": check_postgres_connection(),
        "disk_space": check_disk_space(),
    }
    all_ready = all(checks.values())
    return jsonify(checks), 200 if all_ready else 503

# Run alongside Celery worker in each container
```

**Benefits**:
- Kubernetes/Docker health check compatibility
- Early problem detection
- Graceful degradation

---

#### 4.4.4 Artifact Retention Policy
**Current Issue**: No cleanup of old artifacts

**Recommendation**:
```python
# Add retention policy configuration
class RetentionPolicy:
    completed_job_artifacts_days: int = 7
    failed_job_artifacts_days: int = 30
    cleanup_schedule: str = "0 3 * * *"  # daily at 3am

# Implement in housekeeping worker
@shared_task(name="housekeeping.cleanup_old_artifacts")
def cleanup_old_artifacts():
    """Remove artifacts older than retention policy"""
    # Scan artifacts dir
    # Delete based on policy
    # Log cleanup stats
```

---

### 4.5 Testing & Quality

#### 4.5.1 Integration Test Coverage
**Current Issue**: Integration tests mentioned but not verified

**Recommendation**:
```python
# End-to-end test scenarios
def test_full_pipeline_pdf_ingest():
    """Test complete pipeline from source to completion"""
    # 1. Place PDF in sources/
    # 2. Wait for source_sentinel scan
    # 3. Verify job created
    # 4. Wait for completion (with timeout)
    # 5. Assert dictionary rows exist
    # 6. Assert Cassandra embeddings exist
    # 7. Assert Neo4j graph nodes exist
    # 8. Verify checksum matches
    # 9. Verify artifacts cleaned

def test_refresh_flow():
    """Test refresh preserves dictionary availability"""
    # 1. Complete initial ingest
    # 2. Verify dictionary accessible
    # 3. Trigger refresh job
    # 4. Verify dictionary still accessible during refresh
    # 5. Verify embeddings updated
    # 6. Verify final checksum updated

def test_removal_flow():
    """Test complete removal across all stores"""
    # 1. Complete ingest
    # 2. Trigger removal job
    # 3. Verify dictionary rows deleted
    # 4. Verify Cassandra partition deleted
    # 5. Verify Neo4j nodes deleted
    # 6. Verify artifacts deleted
    # 7. Verify job state = REMOVED
```

---

#### 4.5.2 Chaos Testing
**Current Issue**: No resilience testing

**Recommendation**:
```python
# Chaos test scenarios (mentioned in requirements line 406)
def test_worker_killed_mid_stage():
    """Verify retry/resume after worker death"""
    # 1. Start job
    # 2. Kill worker during processing
    # 3. Verify job retried
    # 4. Verify idempotency (no duplicates)
    # 5. Verify completion

def test_database_connection_loss():
    """Verify graceful handling of DB outage"""
    # 1. Start job
    # 2. Disconnect Cassandra
    # 3. Verify retry backoff
    # 4. Reconnect
    # 5. Verify completion

def test_disk_full_scenario():
    """Verify handling of disk space exhaustion"""
    # ...
```

---

#### 4.5.3 Load Testing Benchmarks
**Current Issue**: No performance baseline

**Recommendation**:
```python
# Load test scenarios
def benchmark_concurrent_ingestion():
    """Test throughput with N concurrent jobs"""
    sources = generate_test_pdfs(count=100)
    start = time.time()
    # Enqueue all
    # Wait for all completions
    duration = time.time() - start
    throughput = len(sources) / duration
    assert throughput > TARGET_THROUGHPUT  # e.g., 10 docs/min

def benchmark_single_large_pdf():
    """Test handling of large document"""
    pdf = generate_large_pdf(pages=500, mb=50)
    # Test within time/memory limits
```

---

### 4.6 Security & Compliance

#### 4.6.1 Secret Management
**Current Issue**: Secrets in environment variables

**Recommendation**:
```python
# Use Docker secrets or external secret manager
import hvac  # HashiCorp Vault
from pathlib import Path

def load_secrets():
    """Load secrets from vault or Docker secrets"""
    if Path("/run/secrets/postgres_password").exists():
        # Docker Swarm secrets
        return Path("/run/secrets/postgres_password").read_text().strip()
    else:
        # Fallback to env var (dev only)
        return os.getenv("POSTGRES_PASSWORD")
```

---

#### 4.6.2 Input Sanitization
**Current Issue**: No validation of source file names

**Recommendation**:
```python
def sanitize_source_path(path: Path) -> bool:
    """Validate source path against path traversal"""
    try:
        resolved = path.resolve()
        sources_dir = Settings().sources_dir.resolve()
        # Ensure path is within sources_dir
        resolved.relative_to(sources_dir)
        return True
    except (ValueError, RuntimeError):
        return False
```

---

## Part 3: Implementation Roadmap

### Priority 1: Critical Fixes (Blocking)
1. ✅ Fix Cassandra schema (add document_id, fix primary key)
2. ✅ Implement real Haystack chunking worker
3. ✅ Implement real LlamaIndex graph building worker
4. ✅ Complete removal job orchestration
5. ✅ Add missing Docker services (haystack, llamaindex containers)

### Priority 2: Important Improvements
6. ✅ Complete health verification (live DB checksums)
7. ✅ Implement log_monitor CLI
8. ✅ Add Worker Supervisor implementation
9. ✅ Complete Neo4j constraints
10. ✅ Implement DLQ inspection tool

### Priority 3: Best Practices
11. ⚡ Add schema validation with Pydantic
12. ⚡ Implement per-worker health endpoints
13. ⚡ Add comprehensive integration tests
14. ⚡ Implement artifact retention policy
15. ⚡ Add chaos/load testing suite

### Priority 4: Polish
16. 💡 Refactor queue routing for cleaner separation
17. 💡 Add trace context propagation
18. 💡 Implement secret management
19. 💡 Add input sanitization
20. 💡 Optimize connection pooling

---

## Part 4: Positive Aspects

The implementation demonstrates several **strong architectural decisions**:

### ✅ Excellent Foundations
1. **Celery + RabbitMQ**: Correct choice for async orchestration
2. **Job Registry**: Well-designed with Postgres backend + history
3. **Idempotency**: Fingerprint-based stage completion tracking
4. **Observability Framework**: Tracing, metrics, logging scaffolds in place
5. **Configuration Management**: Clean Settings dataclass pattern
6. **Type Safety**: Modern Python with type hints throughout
7. **Testing Structure**: Test skeleton exists (needs completion)

### ✅ Smart Design Patterns
- **Plugin Architecture**: Dictionary/Cassandra/Graph stores have clean interfaces
- **Fallback Logic**: In-memory backends for testing
- **Error Handling**: Try-catch with fallbacks to inline execution
- **Status Snapshots**: Human-readable JSON files alongside DB records

---

## Summary Table

| Category | Required | Implemented | Missing | Notes |
|----------|----------|-------------|---------|-------|
| **Core Architecture** | ✓ | ✓ | - | RabbitMQ, Celery, Job Registry solid |
| **Pass A (Unstructured)** | ✓ | ⚠️ | Real processing | Stub only |
| **Pass A (Metadata)** | ✓ | ✓ | - | Working |
| **Pass A (Dictionary)** | ✓ | ✓ | - | Working |
| **Pass B (Haystack)** | ✓ | ⚠️ | Real chunking | Stub only |
| **Pass B (Embeddings)** | ✓ | ✓ | - | Working (OpenAI) |
| **Pass B (Cassandra)** | ✓ | ⚠️ | Schema fix | Wrong PK |
| **Pass C (LlamaIndex)** | ✓ | ⚠️ | Real graph build | Stub only |
| **Pass C (Neo4j)** | ✓ | ⚠️ | Full constraints | Partial |
| **Health Verification** | ✓ | ⚠️ | Live DB checks | Artifact-based only |
| **Cleanup Worker** | ✓ | ✓ | - | Working |
| **Worker Supervisor** | ✓ | ❌ | Complete | Not started |
| **Removal Jobs** | ✓ | ⚠️ | Orchestration | Stub only |
| **CLI: status_monitor** | ✓ | ⚠️ | Next worker | Mostly working |
| **CLI: log_monitor** | ✓ | ❌ | Complete | Stub only |
| **CLI: job_management** | ✓ | ⚠️ | Remove command | Partial |
| **DLQ Inspection** | ✓ | ❌ | Complete | Not implemented |
| **Docker Services** | ✓ | ⚠️ | haystack, llamaindex | Missing containers |

**Overall Completion**: ~65-70% of requirements implemented

---

## Conclusion

The ingestion pipeline implementation is a **solid foundation** with correct architectural choices, but requires **critical completions** in worker logic and schema alignment before production readiness.

**Recommended Next Steps**:
1. Address Priority 1 critical fixes (especially Cassandra schema)
2. Complete worker implementations (Haystack, LlamaIndex)
3. Add comprehensive integration tests
4. Deploy Worker Supervisor for resilience
5. Gradually add best practice improvements from Priority 2-4

**Estimated Effort to Production-Ready**:
- Priority 1 fixes: 2-3 weeks
- Priority 2 improvements: 1-2 weeks
- Testing & validation: 1 week
- **Total**: ~4-6 weeks to full requirements compliance
