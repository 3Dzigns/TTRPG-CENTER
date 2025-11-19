# n8n with Community Nodes

This folder contains a Dockerfile and docker-compose file to build and run n8n with community nodes baked into the image.

## Files
- `Dockerfile.n8n` — builds an image based on `n8nio/n8n` and installs the packages listed in `COMMUNITY_PACKAGES`.
- `docker-compose.n8n.yml` — runs the image with community packages enabled.

## Usage
```bash
# build
docker compose -f docker-compose.n8n.yml build n8n

# run
docker compose -f docker-compose.n8n.yml up -d n8n
```

### Change which nodes get installed
Edit the `COMMUNITY_PACKAGES` build arg in the compose file or pass it at build time:
```bash
docker compose -f docker-compose.n8n.yml build --build-arg COMMUNITY_PACKAGES="@n8n/n8n-nodes-langchain your-favorite-node"
```

## Ingestion Pipeline Notes
- The ingestion scripts default to `/Transfer_Station`. Override by exporting `INGESTION_TRANSFER_ROOT` or passing `--transfer-root` to `ingestion_wrapper.py`.
- Core services expected during a run: MongoDB, Cassandra, Neo4j, PostgreSQL, OpenAI-compatible embeddings endpoint, and Unstructured.io. Ensure they are reachable before launching the wrapper.
- Python dependencies for the ingestion engine are now pinned in `ingestion/requirements.txt`; update intentionally and rebuild containers when bumping versions.
- If Pass E or any downstream step fails, `ingestion_wrapper.py` automatically routes to Gate 1 log analysis in “safe mode” and forces `gate_1_db_remediation_executor.py --dry-run` so no automated fixes are applied while you investigate.
- Pass D now persists an `embedding_manifests` row (chunk count, checksum, index range) for every document. Gate 0 compares its checksum files against this manifest rather than re-counting the entire `embeddings` table.
