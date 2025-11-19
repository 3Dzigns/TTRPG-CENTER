# Troubleshooting Guide

Common issues and solutions for the n8n TTRPG Center stack.

## Table of Contents

- [Docker & Containers](#docker--containers)
- [Custom n8n Node](#custom-n8n-node)
- [Database Issues](#database-issues)
- [Transfer Station](#transfer-station)
- [LangFlow](#langflow)
- [Configuration](#configuration)

---

## Docker & Containers

### Service Won't Start

**Symptoms:** Service stuck in "starting" state or repeatedly restarting

**Solutions:**

1. **Check logs:**
   ```bash
   docker compose -f docker-compose-n8n_TTRPG.yml logs -f <service_name>
   ```

2. **Check service health:**
   ```bash
   docker ps
   ```
   Look for "(unhealthy)" or "Restarting" status

3. **Verify dependencies:**
   - Cassandra must be healthy before Stargate can start (~40s startup time)
   - Neo4j takes ~30s to reach healthy state
   - Check healthcheck configuration in docker-compose file

4. **Restart service:**
   ```bash
   docker compose -f docker-compose-n8n_TTRPG.yml restart <service_name>
   ```

5. **Rebuild container:**
   ```bash
   docker compose -f docker-compose-n8n_TTRPG.yml up -d --force-recreate <service_name>
   ```

### Port Already in Use

**Symptoms:** Error message "bind: address already in use"

**Solutions:**

1. **Identify conflicting process:**
   ```bash
   # Windows
   netstat -ano | findstr :<port_number>

   # Linux/Mac
   lsof -i :<port_number>
   ```

2. **Change external port mapping:**
   Edit `docker-compose-n8n_TTRPG.yml` and change the external port (left side of `:`):
   ```yaml
   ports:
     - "9999:5678"  # Changed from 9000:5678
   ```

3. **Stop conflicting service:**
   ```bash
   # Windows
   taskkill /PID <process_id> /F

   # Linux/Mac
   kill -9 <process_id>
   ```

### Container Runs Out of Memory

**Symptoms:** Container crashes, OOM (Out of Memory) errors in logs

**Solutions:**

1. **Increase Docker memory limit:**
   - Docker Desktop → Settings → Resources → Memory
   - Recommended: 8GB minimum, 16GB for full stack

2. **Add memory limits to services:**
   Edit `docker-compose-n8n_TTRPG.yml`:
   ```yaml
   services:
     cassandra:
       deploy:
         resources:
           limits:
             memory: 4G
           reservations:
             memory: 2G
   ```

### Volume Permission Issues

**Symptoms:** "Permission denied" errors when accessing volumes

**Solutions:**

1. **Check volume ownership:**
   ```bash
   docker exec <container_name> ls -la /path/to/volume
   ```

2. **Fix permissions (Linux/Mac):**
   ```bash
   sudo chown -R $(id -u):$(id -g) /path/to/volume
   ```

3. **Windows Docker Desktop:**
   - Ensure drive is shared: Docker Desktop → Settings → Resources → File Sharing
   - Verify path exists: `E:\n8n_TTRPG_Transfer_Station`

---

## Custom n8n Node

### Custom Node Not Appearing in n8n

**Symptoms:** PDF Slice node not visible in n8n node palette

**Diagnostic Steps:**

1. **Verify build artifacts exist:**
   ```bash
   ls n8n-nodes-pdf-slice/dist/
   ```
   Should contain `.js` files

2. **Check package.json configuration:**
   ```json
   {
     "n8n": {
       "n8nNodesApiVersion": 1,
       "nodes": ["dist/nodes/PdfSlice/PdfSlice.node.js"]
     }
   }
   ```

3. **Verify node installed in container:**
   ```bash
   docker exec n8n_TTRPG_n8n ls -la /home/node/.n8n/custom/n8n-nodes-pdf-slice/
   ```

**Solutions:**

1. **Rebuild node:**
   ```bash
   cd n8n-nodes-pdf-slice
   npm run clean
   npm install
   npm run build
   ```

2. **Copy to container:**
   ```bash
   docker cp n8n-nodes-pdf-slice/dist n8n_TTRPG_n8n:/home/node/.n8n/custom/n8n-nodes-pdf-slice/
   ```

3. **Restart n8n:**
   ```bash
   docker restart n8n_TTRPG_n8n
   ```

4. **Check n8n logs:**
   ```bash
   docker logs n8n_TTRPG_n8n | grep -i "pdf\|custom\|node"
   ```

### TypeScript Build Errors

**Symptoms:** Build fails with module resolution errors

**Common Issues:**

1. **Missing `.js` extensions in imports:**
   ```typescript
   // Wrong
   import { PdfSliceNode } from './PdfSlice.node'

   // Correct (ESM spec)
   import { PdfSliceNode } from './PdfSlice.node.js'
   ```

2. **Incorrect tsconfig.json:**
   ```json
   {
     "compilerOptions": {
       "module": "ES2020",
       "target": "ES2020",
       "moduleResolution": "Bundler"
     }
   }
   ```

3. **Package.json not set for ESM:**
   ```json
   {
     "type": "module"
   }
   ```

---

## Database Issues

### Stargate Won't Start

**Symptoms:** Stargate container restarts repeatedly or fails healthcheck

**Solutions:**

1. **Verify Cassandra is healthy:**
   ```bash
   docker ps | grep cassandra
   ```
   Wait for "(healthy)" status (~40s after start)

2. **Check Cassandra cluster status:**
   ```bash
   docker exec n8n_TTRPG_cassandra nodetool status
   ```

3. **Increase RING_DELAY:**
   Edit `docker-compose-n8n_TTRPG.yml`:
   ```yaml
   environment:
     RING_DELAY: 60  # Increase from default
   ```

4. **Check Cassandra logs:**
   ```bash
   docker logs n8n_TTRPG_cassandra
   ```

### MongoDB Connection Refused

**Symptoms:** Scripts fail with "connection refused" or timeout errors

**Solutions:**

1. **Verify MongoDB is running:**
   ```bash
   docker ps | grep mongodb
   ```

2. **Test connection from host:**
   ```bash
   docker exec n8n_TTRPG_mongodb mongosh --eval "db.adminCommand('ping')"
   ```

3. **Check port mapping:**
   ```bash
   docker port n8n_TTRPG_mongodb
   ```
   Should show: `27017/tcp -> 0.0.0.0:9002`

4. **Test from ingestion_engine:**
   ```bash
   docker exec n8n_TTRPG_ingestion_engine python3 -c "from pymongo import MongoClient; print(MongoClient('n8n_TTRPG_mongodb', 27017).admin.command('ping'))"
   ```

### Neo4j Authentication Failed

**Symptoms:** "AuthError" or "Invalid credentials" when connecting to Neo4j

**Solutions:**

1. **Verify credentials:**
   Default: `neo4j` / `password` (set in docker-compose.yml)

2. **Reset password:**
   ```bash
   docker exec -it n8n_TTRPG_neo4j cypher-shell -u neo4j -p password
   # Then run: ALTER CURRENT USER SET PASSWORD FROM 'password' TO 'newpassword'
   ```

3. **Check .env file:**
   ```bash
   # .env
   NEO4J_USER=neo4j
   NEO4J_PASSWORD=password
   ```

4. **Test connection:**
   ```bash
   docker exec -it n8n_TTRPG_neo4j cypher-shell -u neo4j -p password
   ```

### Cassandra Keyspace Not Found

**Symptoms:** "Keyspace 'ttrpg_vectors' does not exist"

**Solutions:**

1. **Create keyspace manually:**
   ```bash
   docker exec -it n8n_TTRPG_cassandra cqlsh -e "
   CREATE KEYSPACE IF NOT EXISTS ttrpg_vectors
   WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1};"
   ```

2. **Run Pass D with --create-schema:**
   ```bash
   docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/pass_d_hayhooks.py \
     /Transfer_Station/Pass_B_Out/manifest.json --create-schema
   ```

3. **Verify keyspace exists:**
   ```bash
   docker exec -it n8n_TTRPG_cassandra cqlsh -e "DESCRIBE KEYSPACES;"
   ```

---

## Transfer Station

### File Not Found Errors

**Symptoms:** Scripts fail with "No such file or directory" for Transfer Station paths

**Solutions:**

1. **Verify path exists on host:**
   ```bash
   # Windows
   dir E:\n8n_TTRPG_Transfer_Station

   # Linux/Mac
   ls -la /path/to/Transfer_Station
   ```

2. **Check Docker has drive access (Windows):**
   - Docker Desktop → Settings → Resources → File Sharing
   - Add `E:\` drive if not present

3. **Verify mount inside container:**
   ```bash
   docker exec n8n_TTRPG_ingestion_engine ls -la /Transfer_Station
   ```

4. **Use absolute paths:**
   Always use `/Transfer_Station/` inside containers, not relative paths

### Incorrect Subdirectory Structure

**Symptoms:** Files not found in expected `*_inbound` or `*_processing` directories

**Expected Structure:**
```
E:\n8n_TTRPG_Transfer_Station\
├── Gate_0_Out/
├── Pass_A_Out/
├── Pass_B_Out/
├── Pass_C_Out/
├── Pass_D_Out/
├── Pass_E_Out/
├── n8n_inbound/
├── n8n_processing/
├── mongodb_inbound/
├── mongodb_processing/
├── cassandra_inbound/
├── cassandra_processing/
├── ingestion_inbound/
└── ingestion_processing/
```

**Solutions:**

1. **Create missing directories:**
   ```bash
   # Windows
   mkdir E:\n8n_TTRPG_Transfer_Station\Pass_A_Out

   # Linux/Mac
   mkdir -p /path/to/Transfer_Station/Pass_A_Out
   ```

2. **Verify from container:**
   ```bash
   docker exec n8n_TTRPG_ingestion_engine ls /Transfer_Station/
   ```

---

## LangFlow

### Component Not Loading

**Symptoms:** Custom components or flows fail to load in LangFlow UI

**Solutions:**

1. **Check LangFlow logs:**
   ```bash
   docker logs n8n_TTRPG_langflow
   ```

2. **Verify dependencies installed:**
   ```bash
   docker exec n8n_TTRPG_langflow pip list | grep pypdf
   ```

3. **Install missing dependencies:**
   ```bash
   docker exec n8n_TTRPG_langflow pip install pypdf
   ```

4. **Restart LangFlow:**
   ```bash
   docker restart n8n_TTRPG_langflow
   ```

5. **Check LangFlow version compatibility:**
   ```bash
   docker exec n8n_TTRPG_langflow pip show langflow
   ```

---

## Configuration

### .env File Not Found

**Symptoms:** Pass D fails with "OPENAI_API_KEY not found" or similar environment errors

**Solutions:**

1. **Create .env file in project root:**
   ```bash
   # E:\n8n_TTRPG_Center\.env
   OPENAI_API_KEY=sk-proj-...
   NEO4J_USER=neo4j
   NEO4J_PASSWORD=password
   ```

2. **Verify .env is in .gitignore:**
   ```bash
   cat .gitignore | grep .env
   ```

3. **Load .env in container (if needed):**
   ```bash
   docker exec n8n_TTRPG_ingestion_engine bash -c "export $(cat /app/.env | xargs)"
   ```

### ingestion.cfg Not Found

**Symptoms:** Scripts fail with "Configuration file not found"

**Solutions:**

1. **Verify config file exists:**
   ```bash
   ls -la ingestion/ingestion.cfg
   ```

2. **Check mount in container:**
   ```bash
   docker exec n8n_TTRPG_ingestion_engine ls -la /app/ingestion.cfg
   ```

3. **Use default config path:**
   Scripts look for `./ingestion/ingestion.cfg` by default

### Invalid Configuration Values

**Symptoms:** Scripts fail with parsing errors or unexpected behavior

**Solutions:**

1. **Validate INI syntax:**
   - No spaces around `=` in key=value pairs
   - Comments start with `#`
   - Section headers: `[Section_Name]`

2. **Check for typos in keys:**
   ```ini
   [Pass_D]
   cassandra_host = n8n_TTRPG_cassandra  # Correct
   casandra_host = ...                    # Wrong (typo)
   ```

3. **Verify data types:**
   ```ini
   min_chunk_chars = 500   # Integer, no quotes
   embedding_model = text-embedding-3-small  # String
   ```

---

## General Debugging

### Enable Verbose Logging

**For Python scripts:**
```bash
# Add -v or --verbose flag if supported
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/pass_a_unstructured.py \
  /Transfer_Station/sources/doc.pdf -v
```

**For Docker services:**
```yaml
# docker-compose-n8n_TTRPG.yml
services:
  n8n:
    environment:
      - N8N_LOG_LEVEL=debug
```

### Check All Service Health

```bash
# Quick health check
docker ps --format "table {{.Names}}\t{{.Status}}"

# Detailed health check
docker compose -f docker-compose-n8n_TTRPG.yml ps
```

### Restart Entire Stack

```bash
# Stop all services
docker compose -f docker-compose-n8n_TTRPG.yml down

# Start with fresh state
docker compose -f docker-compose-n8n_TTRPG.yml up -d

# Watch logs for all services
docker compose -f docker-compose-n8n_TTRPG.yml logs -f
```

### Clear All Data and Reset

**WARNING: This deletes all database data!**

```bash
# Stop stack
docker compose -f docker-compose-n8n_TTRPG.yml down

# Remove volumes (data loss!)
docker compose -f docker-compose-n8n_TTRPG.yml down -v

# Start fresh
docker compose -f docker-compose-n8n_TTRPG.yml up -d
```
