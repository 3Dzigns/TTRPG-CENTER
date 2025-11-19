# How to Start Jobs and Configure the Async Pipeline

**Quick Reference Guide for Job Execution and Configuration**

---

## 🚀 Step 1: One-Command Deployment (Docker-Native)

### Deploy Entire Production Architecture

```bash
cd /e/n8n_TTRPG_Center
docker compose -f docker-compose-ttrpg.yml up -d --build
```

**That's it!** This single command:
- ✅ Builds all 6 custom worker containers
- ✅ Starts all services with health checks
- ✅ Auto-starts 15 workers managed by supervisord
- ✅ Starts source_monitor_worker for zero-touch workflow
- ✅ No manual deployment or start scripts needed

### Verify Workers Are Running

```bash
# Check supervisor status in each container
docker exec ttrpg_ingestion_engine supervisorctl status
docker exec ttrpg_mongodb supervisorctl status
docker exec ttrpg_cassandra supervisorctl status
docker exec ttrpg_hayhooks supervisorctl status
docker exec ttrpg_llamaindex supervisorctl status
docker exec ttrpg_hgrn supervisorctl status

# Check unstructured worker (separate architecture)
docker exec ttrpg_unstructured ps aux | grep worker
```

### View Worker Logs

```bash
# View all supervisor logs for a container
docker exec ttrpg_ingestion_engine supervisorctl tail -f source_monitor stdout

# View specific worker logs
docker exec ttrpg_mongodb supervisorctl tail -f pass_a_mongo_upsert stdout
docker exec ttrpg_cassandra supervisorctl tail -f pass_d_checksum stderr

# Or check Transfer Station logs
ls -lh /e/n8n_TTRPG_Transfer_Station/Logs/
```

---

## 🎯 Step 2: How Jobs Work (Zero-Touch Workflow)

### ✨ Automatic Job Discovery (Recommended)

The **source_monitor_worker** automatically detects PDF changes in `/Transfer_Station/sources/`:

1. **Add PDF to sources directory** (from Windows):
   ```
   Copy your_document.pdf to:
   E:\n8n_TTRPG_Transfer_Station\sources\
   ```

2. **source_monitor_worker detects new PDF** (polls every 5 minutes)
   - Automatically queues ingestion job
   - Job flows through entire pipeline
   - No manual commands needed!

3. **Remove PDF from sources directory** (from Windows):
   ```
   Delete E:\n8n_TTRPG_Transfer_Station\sources\your_document.pdf
   ```

4. **source_monitor_worker detects removal**
   - Automatically queues cleanup job
   - Removes all artifacts from `/Transfer_Station/jobs/`
   - Removes MongoDB, Cassandra, Neo4j entries
   - Complete cleanup!

### 📍 Path Translation

**From Windows**:
- Sources: `E:\n8n_TTRPG_Transfer_Station\sources\your_document.pdf`
- Jobs: `E:\n8n_TTRPG_Transfer_Station\jobs\`
- Output: `E:\n8n_TTRPG_Transfer_Station\output\`
- Logs: `E:\n8n_TTRPG_Transfer_Station\Logs\`

**Inside Containers**:
- Sources: `/Transfer_Station/sources/your_document.pdf`
- Jobs: `/Transfer_Station/jobs/`
- Output: `/Transfer_Station/output/`
- Logs: `/Transfer_Station/Logs/`

The `/Transfer_Station` volume is **shared between Windows and all containers**.

---

## 🔧 Step 3: Manual Job Creation (Advanced - Container Only)

If you need to manually queue a job (bypassing auto-discovery), you must do it **inside the container**:

### Method 1: Using ingestion_wrapper_async.py (Inside Container)

```bash
# Connect to ingestion_engine container
docker exec -it ttrpg_ingestion_engine bash

# Queue a job (use container paths!)
cd /Transfer_Station/scripts
python3 ingestion_wrapper_async.py \
    --source-pdf /Transfer_Station/sources/your_document.pdf

# Exit container
exit
```

**CRITICAL**:
- ❌ Never run this on Windows host
- ✅ Always use container paths: `/Transfer_Station/sources/file.pdf`
- ❌ Never use Windows paths: `/e/n8n_TTRPG_Transfer_Station/...`

### Method 2: Batch Process Multiple PDFs (Inside Container)

```bash
# Connect to container
docker exec -it ttrpg_ingestion_engine bash

# Queue all PDFs in sources directory
cd /Transfer_Station/scripts
for pdf in /Transfer_Station/sources/*.pdf; do
    python3 ingestion_wrapper_async.py --source-pdf "$pdf"
done

# Exit
exit
```

### Method 3: Force Reprocess (Inside Container)

```bash
docker exec -it ttrpg_ingestion_engine bash

cd /Transfer_Station/scripts
python3 ingestion_wrapper_async.py \
    --source-pdf /Transfer_Station/sources/your_document.pdf \
    --force-reprocess

exit
```

---

## ⚙️ Step 4: How to Change Configuration

### Configuration Files

#### 1. **ingestion/ingestion.cfg** - Main Pipeline Configuration

```ini
[paths]
transfer_station = /Transfer_Station
sources_dir = /Transfer_Station/sources
output_dir = /Transfer_Station/output
jobs_dir = /Transfer_Station/jobs
logs_dir = /Transfer_Station/Logs

[pipeline]
# Enable/disable optional stages
enable_doc_splitter = true
enable_log_analyzer = true
enable_db_remediation = true
enable_pipeline_optimizer = true

# Worker timeouts (seconds)
timeout_pass_a_metadata = 300
timeout_pass_a_mongo_upsert = 600
timeout_pass_d_checksum = 60
timeout_pass_d_hayhooks = 7200
timeout_pass_e_graph_builder = 1800
timeout_pass_e_neo4j_upsert = 1800
timeout_pass_f_validation = 1800
timeout_gate_1_log_analyzer = 600
timeout_gate_1_db_remediation = 1800
timeout_gate_1_pipeline_optimizer = 600
timeout_gate_1_cleanup = 300

[worker]
# Worker polling configuration
poll_interval = 5
max_retries = 3
retry_delay = 60

[source_monitor]
# Source directory monitoring
poll_interval = 300  # 5 minutes
manifest_path = /Transfer_Station/Logs/source_monitor/manifest.json

[openai]
# OpenAI API configuration
model = gpt-4o
temperature = 0.1
max_tokens = 4096

[databases]
# Database connection strings
mongodb_uri = mongodb://mongodb:27017/ttrpg
cassandra_contact_points = cassandra:9042
cassandra_keyspace = ttrpg
neo4j_uri = bolt://neo4j:7687
```

#### 2. **.env** - Credentials and Secrets

```bash
# OpenAI API
OPENAI_API_KEY=your_openai_api_key_here

# Neo4j
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_neo4j_password

# PostgreSQL
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_postgres_password
POSTGRES_DB=ttrpg_auth
```

#### 3. **ingestion/pipeline_routes.json** - Stage Routing

```json
{
  "gate_0_hash": "gate_0_validate",
  "gate_0_validate": "doc_splitter",
  "doc_splitter": "pass_a_unstructured",
  "pass_a_unstructured": "pass_a_metadata",
  "pass_a_metadata": "pass_a_mongo_upsert",
  "pass_a_mongo_upsert": "pass_d_checksum",
  "pass_d_checksum": "pass_d_hayhooks",
  "pass_d_hayhooks": "pass_e_graph_builder",
  "pass_e_graph_builder": "pass_e_neo4j_upsert",
  "pass_e_neo4j_upsert": "pass_f_validation",
  "pass_f_validation": "gate_1_log_analyzer",
  "gate_1_log_analyzer": "gate_1_db_remediation",
  "gate_1_db_remediation": "gate_1_pipeline_optimizer",
  "gate_1_pipeline_optimizer": "gate_1_cleanup",
  "gate_1_cleanup": "complete"
}
```

### Common Configuration Changes

#### Change Source Monitor Poll Interval

**Edit `scripts/start_all_workers_production.sh`:**
```bash
# Change from --poll-interval 300 to --poll-interval 600 (10 minutes)
--poll-interval 600  # Check every 10 minutes instead of 5
```

**Restart source monitor worker:**
```bash
docker exec ttrpg_ingestion_engine pkill -f "source_monitor_worker.py"
bash scripts/start_all_workers_production.sh
```

#### Change Worker Timeouts

**Edit each worker file (e.g., `ingestion/pass_d_hayhooks_worker.py`):**
```python
# Change timeout in subprocess.run()
result = subprocess.run(
    cmd,
    capture_output=True,
    text=True,
    check=False,
    timeout=3600  # Change from 7200 (2 hours) to 3600 (1 hour)
)
```

**Redeploy and restart:**
```bash
bash scripts/deploy_workers_production.sh
bash scripts/start_all_workers_production.sh
```

#### Disable Optional Stages

**Method 1: Edit pipeline_routes.json** (skip stage entirely):
```json
{
  "pass_f_validation": "gate_1_cleanup"  // Skip log analyzer, remediation, optimizer
}
```

**Method 2: Edit worker to always succeed** (run but don't block):
```python
# In gate_1_log_analyzer_worker.py
def _process_job(self, job_dir: Path, status: Dict[str, Any]) -> bool:
    self.logger.info("Log analyzer disabled - skipping")
    return True  # Always succeed, skip to next stage
```

#### Change OpenAI Model

**Edit .env file:**
```bash
OPENAI_MODEL=gpt-4o-mini  # Use cheaper/faster model
```

**Edit worker scripts (gate_1_log_analyzer.py, gate_1_pipeline_optimizer.py):**
```python
model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
```

**Redeploy workers:**
```bash
bash scripts/deploy_workers_production.sh
bash scripts/start_all_workers_production.sh
```

#### Change Database Connections

**Edit .env file:**
```bash
# Use external MongoDB instead of container
MONGODB_URI=mongodb://external-mongo.example.com:27017/ttrpg

# Use cloud Neo4j instead of local
NEO4J_URI=neo4j+s://your-instance.neo4j.io:7687
```

**Redeploy affected workers:**
```bash
# Redeploy mongodb worker after changing MONGODB_URI
docker cp ingestion/pass_a_mongo_upsert_worker.py ttrpg_mongodb:/opt/workers/
docker exec ttrpg_mongodb pkill -f "pass_a_mongo_upsert_worker.py"
bash scripts/start_all_workers_production.sh
```

---

## 📊 Step 5: Monitor Job Progress

### Check Source Monitor Activity

```bash
# View source monitor log
docker exec ttrpg_ingestion_engine tail -f /Transfer_Station/Logs/source_monitor/worker.log

# Check manifest of known PDFs
docker exec ttrpg_ingestion_engine cat /Transfer_Station/Logs/source_monitor/manifest.json
```

### Check Job Status

```bash
# Find your job ID (first 16 chars of SHA-256 hash)
JOB_ID="your_job_id_here"

# View job status
cat /e/n8n_TTRPG_Transfer_Station/jobs/*/${JOB_ID}/status.json | jq .

# Watch job progression (from Windows)
watch -n 2 "ls -la /e/n8n_TTRPG_Transfer_Station/jobs/*/${JOB_ID}/"
```

### Check Worker Logs

```bash
# View specific worker log
docker exec ttrpg_ingestion_engine tail -f /Transfer_Station/Logs/gate_0_hash/worker.log

# View all worker heartbeats
cat /e/n8n_TTRPG_Transfer_Station/Logs/*/heartbeat.json | jq '{stage: .stage_name, last_activity, jobs_processed}'

# Search for errors across all logs
grep -r "ERROR" /e/n8n_TTRPG_Transfer_Station/Logs/*/worker.log
```

### Check Pipeline Completion

```bash
# Job completed successfully (from Windows)
ls /e/n8n_TTRPG_Transfer_Station/jobs/complete/${JOB_ID}/

# Job failed
ls /e/n8n_TTRPG_Transfer_Station/jobs/failed/${JOB_ID}/

# Count completed jobs
ls /e/n8n_TTRPG_Transfer_Station/jobs/complete/ | wc -l

# Count failed jobs
ls /e/n8n_TTRPG_Transfer_Station/jobs/failed/ | wc -l
```

---

## 🔄 Step 6: Restart or Stop Workers

### Restart All Workers

```bash
# Stop all workers
for container in ttrpg_ingestion_engine ttrpg_mongodb ttrpg_cassandra ttrpg_hayhooks ttrpg_llamaindex ttrpg_hgrn; do
    docker exec $container pkill -f "worker.py" 2>/dev/null || true
done

# Start all workers
bash scripts/start_all_workers_production.sh
```

### Restart Source Monitor Only

```bash
# Stop source monitor
docker exec ttrpg_ingestion_engine pkill -f "source_monitor_worker.py"

# Restart just source monitor
docker exec -d ttrpg_ingestion_engine bash -c \
  "cd /Transfer_Station/scripts && python3 source_monitor_worker.py \
  --sources-dir /Transfer_Station/sources \
  --manifest-path /Transfer_Station/Logs/source_monitor/manifest.json \
  --poll-interval 300 \
  2>&1 | tee -a /Transfer_Station/Logs/source_monitor/worker.log"
```

### Restart Single Worker

```bash
# Example: Restart hayhooks worker (the 2-hour bottleneck)
docker exec ttrpg_hayhooks pkill -f "pass_d_hayhooks_worker.py"

# Restart just that worker
docker exec -d ttrpg_hayhooks bash -c \
  "cd /opt/workers && python3 pass_d_hayhooks_worker.py \
  --jobs-dir /Transfer_Station/jobs \
  --log-dir /Transfer_Station/Logs \
  --poll-interval 5 \
  2>&1 | tee -a /Transfer_Station/Logs/pass_d_hayhooks/worker.log"
```

### Stop All Workers (Graceful Shutdown)

```bash
# Stop workers in all containers
for container in ttrpg_ingestion_engine ttrpg_mongodb ttrpg_cassandra ttrpg_hayhooks ttrpg_llamaindex ttrpg_hgrn; do
    docker exec $container pkill -f "worker.py" 2>/dev/null || true
done

echo "All workers stopped"
```

---

## 🧪 Step 7: Test Configuration

### Test Auto-Discovery Workflow

```bash
# Step 1: Copy test PDF to sources (from Windows)
cp /path/to/test.pdf E:/n8n_TTRPG_Transfer_Station/sources/test.pdf

# Step 2: Wait up to 5 minutes for source_monitor to detect it
# Monitor source_monitor log
docker exec ttrpg_ingestion_engine tail -f /Transfer_Station/Logs/source_monitor/worker.log

# Step 3: Watch job progress (from Windows)
watch -n 2 'ls -la E:/n8n_TTRPG_Transfer_Station/jobs/*/ | tail -20'

# Step 4: Remove PDF to test cleanup (from Windows)
rm E:/n8n_TTRPG_Transfer_Station/sources/test.pdf

# Step 5: Wait up to 5 minutes for cleanup detection
# Monitor cleanup in source_monitor log
```

### Validate Configuration

```bash
# Check if all containers are running
docker ps | grep ttrpg

# Check if Python is installed in DB containers
docker exec ttrpg_mongodb python3 --version
docker exec ttrpg_cassandra python3 --version

# Check if workers are deployed
docker exec ttrpg_ingestion_engine ls -la /Transfer_Station/scripts/*worker.py
docker exec ttrpg_mongodb ls -la /opt/workers/*worker.py
docker exec ttrpg_llamaindex ls -la /opt/workers/*worker.py

# Check if source_monitor is running
docker exec ttrpg_ingestion_engine ps aux | grep source_monitor

# Verify database connections
docker exec ttrpg_mongodb mongosh --eval "db.runCommand({ ping: 1 })"
docker exec ttrpg_cassandra cqlsh -e "DESCRIBE KEYSPACES"
docker exec ttrpg_neo4j cypher-shell -u neo4j -p password "RETURN 1"
```

---

## 📚 Quick Command Reference

```bash
# Deploy production architecture (one-time setup)
docker compose -f docker-compose-ttrpg.yml build llamaindex
docker compose -f docker-compose-ttrpg.yml up -d
bash scripts/install_python_db_containers.sh
bash scripts/deploy_workers_production.sh
bash scripts/start_all_workers_production.sh

# Start jobs (AUTOMATIC - just copy PDFs to sources)
# From Windows: Copy to E:\n8n_TTRPG_Transfer_Station\sources\
# source_monitor_worker auto-detects and queues jobs

# Monitor source discovery
docker exec ttrpg_ingestion_engine tail -f /Transfer_Station/Logs/source_monitor/worker.log

# Monitor progress (from Windows)
watch 'ls -la E:/n8n_TTRPG_Transfer_Station/jobs/*/'
cat E:/n8n_TTRPG_Transfer_Station/Logs/*/heartbeat.json | jq .

# Restart workers
bash scripts/start_all_workers_production.sh

# View logs (inside container paths)
docker exec ttrpg_ingestion_engine tail -f /Transfer_Station/Logs/gate_0_hash/worker.log
```

---

## 🆘 Troubleshooting

### Problem: Source Monitor Not Detecting PDFs

**Check if source_monitor is running:**
```bash
docker exec ttrpg_ingestion_engine ps aux | grep source_monitor
```

**Check source_monitor logs:**
```bash
docker exec ttrpg_ingestion_engine tail -100 /Transfer_Station/Logs/source_monitor/worker.log
```

**Restart source_monitor:**
```bash
docker exec ttrpg_ingestion_engine pkill -f "source_monitor_worker.py"
bash scripts/start_all_workers_production.sh
```

### Problem: Job Stuck in Stage

**Check worker logs:**
```bash
# Find which stage job is stuck in
JOB_ID="your_job_id"
find /e/n8n_TTRPG_Transfer_Station/jobs/*/${JOB_ID}/ -name "*.marker"

# Check that stage's worker log
docker exec ttrpg_ingestion_engine tail -100 /Transfer_Station/Logs/<stage>/worker.log
```

**Restart that stage's worker:**
```bash
bash scripts/start_all_workers_production.sh
```

### Problem: Workers Not Running

**Check if workers are running:**
```bash
docker exec ttrpg_ingestion_engine ps aux | grep worker
```

**If not, start them:**
```bash
bash scripts/start_all_workers_production.sh
```

### Problem: Configuration Changes Not Taking Effect

**Redeploy workers after config changes:**
```bash
# Copy updated files
bash scripts/deploy_workers_production.sh

# Restart workers to load new config
docker exec ttrpg_ingestion_engine pkill -f "worker.py"
bash scripts/start_all_workers_production.sh
```

### Problem: Manual Job Creation Fails

**Common mistakes:**
- ❌ Running `python3 ingestion_wrapper_async.py` on Windows host
- ❌ Using Windows paths: `/e/n8n_TTRPG_Transfer_Station/...`

**Correct approach:**
```bash
# Connect to container FIRST
docker exec -it ttrpg_ingestion_engine bash

# Use container paths
cd /Transfer_Station/scripts
python3 ingestion_wrapper_async.py \
    --source-pdf /Transfer_Station/sources/your_document.pdf

# Exit container
exit
```

---

## ✨ Key Differences from Previous Instructions

### ❌ OLD (Incorrect):
- Run `python3 ingestion_wrapper_async.py` on Windows host
- Use Windows paths like `/e/n8n_TTRPG_Transfer_Station/sources/`
- Manually queue jobs for every PDF

### ✅ NEW (Correct):
- **Automatic job discovery** via source_monitor_worker
- **Just copy PDFs to sources directory** - jobs start automatically!
- Manual job creation **only inside containers** using container paths
- Use container paths: `/Transfer_Station/sources/`

---

**For more details, see:**
- `claudedocs/PRODUCTION_DEPLOYMENT_SUMMARY.md` - Full deployment guide
- `claudedocs/ASYNC_PRODUCTION_ARCHITECTURE.md` - Architecture details
- `claudedocs/ASYNC_WORKER_CONTAINER_MAPPING.md` - Worker details
