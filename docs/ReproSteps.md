# Reproduction Steps - Ingestion Pipeline Failures

**Issue**: gate_1_log_analyzer.py OpenAI response parsing error
**Date**: 2025-10-17
**Reproducibility**: 100% (occurs on every Gate 1 analysis invocation)

---

## Issue #1: gate_1_log_analyzer OpenAI Parsing Bug

### Prerequisites
- Docker environment running
- OpenAI API key configured in secrets
- At least one failed ingestion log file available

### Reproduction Steps

#### Method 1: Direct Script Execution

1. **Navigate to ingestion directory**:
   ```bash
   cd E:/n8n_TTRPG_Center/ingestion
   ```

2. **Locate a test log file**:
   ```bash
   ls E:/n8n_TTRPG_Transfer_Station/Ingestion_Logs/20251017_*.log
   ```

3. **Execute gate_1_log_analyzer directly**:
   ```bash
   python gate_1_log_analyzer.py \
     E:/n8n_TTRPG_Transfer_Station/Ingestion_Logs/20251017_205214_ingestion.log \
     --output /tmp/test_output
   ```

4. **Expected Failure**:
   ```
   Gate 1 Log Analyzer v1.0.0
   Log file: E:/n8n_TTRPG_Transfer_Station/Ingestion_Logs/20251017_205214_ingestion.log
   Model: gpt-4o
   Output directory: /tmp/test_output

   Loading log file...
   ✓ Loaded 129,547 characters

   Analyzing log with OpenAI...
   Calling OpenAI API with model: gpt-4o
   Error: OpenAI API error: Unexpected response format: <class 'dict'>
   ```

5. **Exit Code**: 1 (error)

#### Method 2: Via Ingestion Pipeline

1. **Prepare a document that will fail Pass F**:
   - Any document where Cassandra or Neo4j validation will fail
   - Example: Documents already in `sources/` that failed in the 2025-10-17 run

2. **Run ingestion pipeline**:
   ```bash
   docker exec n8n_TTRPG_ingestion python ingestion_wrapper.py \
     --source /Transfer_Station/sources/test_document.pdf \
     --passes C,D,E,F
   ```

3. **Wait for Pass F failure**:
   - Pipeline will detect validation score < 0.9
   - Triggers Gate 1 analysis in safe mode

4. **Observe Gate 1 failure**:
   - Check ingestion log for:
     ```
     [INFO] [gate_1_log_analyzer] Starting
     [WARNING] [gate_1_log_analyzer] stderr: Error: OpenAI API error: Unexpected response format: <class 'dict'>
     [ERROR] [gate_1_log_analyzer] stderr: Error: OpenAI API error: Unexpected response format: <class 'dict'>
     ```

#### Method 3: Minimal Reproduction (Unit Test)

Create `test_openai_parse.py`:

```python
#!/usr/bin/env python3
import json
from gate_1_log_analyzer import analyze_log_with_openai

# Minimal log content to trigger analysis
log_content = """
2025-10-17 10:00:00 [ERROR] Test error message
2025-10-17 10:00:01 [WARNING] Test warning
"""

try:
    issues = analyze_log_with_openai(log_content, "gpt-4o")
    print(f"Success! Found {len(issues)} issues")
except Exception as e:
    print(f"ERROR: {e}")
```

Run:
```bash
python test_openai_parse.py
```

Expected output:
```
Calling OpenAI API with model: gpt-4o
ERROR: OpenAI API error: Unexpected response format: <class 'dict'>
```

---

## Issue #2: Pass F Validation Failures (Cassandra/Neo4j)

### Prerequisites
- MongoDB, Cassandra, Neo4j all running
- Document processed through Pass A-E
- Pass F validation script available

### Reproduction Steps

1. **Identify a document with Pass F failures**:
   ```bash
   ls E:/n8n_TTRPG_Transfer_Station/Pass_F_Out/*remediation_plan.json
   ```

2. **Run Pass F validation manually**:
   ```bash
   docker exec n8n_TTRPG_ingestion python /app/scripts/pass_f_consistency_check.py \
     /Transfer_Station/Gate_0_Out/cyberpunk_v3_cp4110_core_rulebook_4f81185e7057.json \
     --output /Transfer_Station/Pass_F_Out \
     --threshold 0.90
   ```

3. **Observe validation scores**:
   ```
   [Pass F] MongoDB validation complete - checked=1391, violations=0, score=1.0
   [Pass F] Cassandra validation complete - checked=7654, violations=15308, score=0.0
   [Pass F] Neo4j validation complete - checked=1, violations=1, score=0.0
   [Pass F] Overall score: 0.4443 (threshold 0.9)
   ```

4. **Check remediation plan**:
   ```bash
   cat /Transfer_Station/Pass_F_Out/cyberpunk_v3_cp4110_core_rulebook_4f81185e7057_remediation_plan.json | jq
   ```

5. **Expected Pattern**:
   - Cassandra violations = 2x checked count
   - Neo4j score always 0.0
   - MongoDB score 1.0 (working correctly)

---

## Issue #3: Pass C Unstructured API Timeout

### Prerequisites
- Large PDF document (>200 pages)
- Unstructured API service running
- Document split into multiple parts via Pass B

### Reproduction Steps

1. **Use large document**:
   - Example: "Pathfinder RPG - Core Rulebook (6th Printing).pdf" (575+ pages)

2. **Run Pass C parsing**:
   ```bash
   docker exec n8n_TTRPG_ingestion python /app/scripts/pass_c_parsing.py \
     /Transfer_Station/Pass_B_Out/pathfinder_rpg_core_rulebook_6th_printing_4f4b1d9d2b6c_manifest.json \
     --output /Transfer_Station/Pass_C_Out
   ```

3. **Monitor processing time**:
   - Each part should process in < 300 seconds
   - Some parts exceed timeout limit
   - Error: `HTTPConnectionPool(host='n8n_ttrpg_unstructured', port=8000): Read timed out. (read timeout=300)`

4. **Observe partial completion**:
   - Some parts process successfully (e.g., part01-part09)
   - Later parts timeout (e.g., part10+)
   - Overall Pass C exit code: 1 (failure)

---

## Environment Details

### System Information
- **OS**: Windows (via WSL/Docker)
- **Docker**: Running containers for MongoDB, Cassandra, Neo4j, Unstructured API
- **Python**: 3.x (in ingestion container)
- **OpenAI SDK**: Version in use (check `pip list | grep openai`)

### Configuration Files
- **Docker Secrets**: `/run/secrets/openai_api_key`
- **Environment**: `/app/.env` (in container)
- **Log Directory**: `E:/n8n_TTRPG_Transfer_Station/Ingestion_Logs/`
- **Output Directories**: Pass_F_Out, Pass_C_Out, etc.

### Database States
- **MongoDB**: `ttrpg_ingestion` database, collections: documents, terms, categories
- **Cassandra**: `ttrpg_vectors` keyspace, table: embeddings
- **Neo4j**: Graph database with Document, Chunk, Term, Category nodes

---

## Verification Checklist

Before reporting as reproduced, verify:

- [ ] OpenAI API key is valid and has credits
- [ ] All required Docker containers are running (`docker ps`)
- [ ] Log file exists and has content (not empty)
- [ ] Error message matches exactly: "Unexpected response format: <class 'dict'>"
- [ ] Exit code is 1 (not 0 or other)
- [ ] No network connectivity issues to OpenAI API

---

## Debugging Tips

### Enable Verbose Logging
```bash
export LOG_LEVEL=DEBUG
python gate_1_log_analyzer.py <log_file>
```

### Test OpenAI API Connection
```python
from openai import OpenAI
client = OpenAI(api_key="sk-...")
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Test"}],
    response_format={"type": "json_object"}
)
print(response.choices[0].message.content)
```

### Inspect OpenAI Response Structure
Add debugging at line 224 in `gate_1_log_analyzer.py`:
```python
response_content = response.choices[0].message.content
print(f"DEBUG RAW RESPONSE: {response_content}", file=sys.stderr)
result = json.loads(response_content)
print(f"DEBUG PARSED TYPE: {type(result)}", file=sys.stderr)
print(f"DEBUG KEYS: {result.keys() if isinstance(result, dict) else 'N/A'}", file=sys.stderr)
```

---

**Document Version**: 1.0
**Last Updated**: 2025-10-17
**Reproduction Rate**: 100% (deterministic bug)
**Related Documents**: `RCA.md`, `FixPlan.md`
