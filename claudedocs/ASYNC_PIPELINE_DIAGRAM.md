# Async Ingestion Pipeline Architecture Diagram

## Full Pipeline Flow with Container Mapping

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ASYNC INGESTION PIPELINE                            │
│                         14 Workers + 3 Databases                            │
└─────────────────────────────────────────────────────────────────────────────┘

                              ┌──────────────┐
                              │  USER/API    │
                              │  Queue Job   │
                              └──────┬───────┘
                                     │
                                     ▼
                      ┌──────────────────────────┐
                      │ ingestion_wrapper_async  │
                      │   (fire-and-forget)      │
                      └──────────┬───────────────┘
                                 │
                                 ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                          GATE 0: ENTRY & VALIDATION                        │
│                     Container: ttrpg_ingestion_engine                      │
└────────────────────────────────────────────────────────────────────────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         ▼                       ▼                       ▼
   ┌──────────┐          ┌──────────────┐        ┌─────────────┐
   │  WORKER  │          │   WORKER     │        │   WORKER    │
   │gate_0_   │  (0.5s)  │ gate_0_      │ (0.7s) │doc_splitter │ (~5s)
   │hash      │─────────▶│ validate     │───────▶│  (optional) │
   │          │          │              │        │             │
   └──────────┘          └──────────────┘        └──────┬──────┘
                                                         │
                                                         ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                    PASS A: UNSTRUCTURED & METADATA                         │
└────────────────────────────────────────────────────────────────────────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         ▼                       ▼                       ▼
   ┌──────────┐          ┌──────────────┐        ┌─────────────┐
   │  WORKER  │          │   WORKER     │        │   WORKER    │
   │pass_a_   │ (varies) │ pass_a_      │ (5min) │pass_a_mongo │ (10min)
   │unstruc   │─────────▶│ metadata     │───────▶│  _upsert    │───┐
   │tured     │          │              │        │             │   │
   └──────────┘          └──────────────┘        └─────────────┘   │
       │                                                             │
       │ Container: ttrpg_unstructured                              │
       │                                                             │
       └─────────────────────────────────────────────────────────────┤
                              Container: ttrpg_ingestion_engine     │
                                                                     │
                                                                     ▼
                                                              ┌─────────────┐
                                                              │  DATABASE   │
                                                              │  MongoDB    │
                                                              │  (elements) │
                                                              └─────────────┘
                                                                     │
                                                                     ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                    PASS D: CHECKSUMS & EMBEDDINGS                          │
│                     Container: ttrpg_ingestion_engine                      │
└────────────────────────────────────────────────────────────────────────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         ▼                       ▼                       ▼
   ┌──────────┐          ┌──────────────┐        ┌─────────────┐
   │  WORKER  │          │   WORKER     │        │   CALLS     │
   │pass_d_   │  (1min)  │ pass_d_      │ (2hrs) │  hayhooks   │
   │checksum  │─────────▶│ hayhooks     │───────▶│  container  │
   │          │          │              │        │  (OpenAI)   │
   └──────────┘          └──────┬───────┘        └─────────────┘
                                │                       │
                                ▼                       ▼
                         ┌─────────────┐        ┌─────────────┐
                         │  DATABASE   │        │  DATABASE   │
                         │  Cassandra  │        │  Cassandra  │
                         │  (checksum) │        │  (vectors)  │
                         └─────────────┘        └─────────────┘
                                │                       │
                                └───────────┬───────────┘
                                            ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                      PASS E: KNOWLEDGE GRAPH                               │
│                     Container: ttrpg_ingestion_engine                      │
└────────────────────────────────────────────────────────────────────────────┘
                                 │
         ┌───────────────────────┴───────────────────────┐
         ▼                                               ▼
   ┌──────────┐                                   ┌─────────────┐
   │  WORKER  │           (30min)                 │   WORKER    │  (30min)
   │pass_e_   │──────────────────────────────────▶│pass_e_neo4j │────┐
   │graph_    │                                    │  _upsert    │    │
   │builder   │                                    │             │    │
   └──────────┘                                    └─────────────┘    │
                                                                      ▼
                                                              ┌─────────────┐
                                                              │  DATABASE   │
                                                              │   Neo4j     │
                                                              │   (graph)   │
                                                              └─────────────┘
                                                                      │
                                                                      ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                      PASS F: CROSS-STORE VALIDATION                        │
│                     Container: ttrpg_ingestion_engine                      │
└────────────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
                          ┌──────────────┐
                          │   WORKER     │  (30min)
                          │  pass_f_     │
                          │  validation  │────────┐
                          │              │        │
                          └──────────────┘        │
                                 │                │
                                 │ Validates:    │ Generates:
                                 │ MongoDB       │ HGRN Reports
                                 │ Cassandra     │ Remediations
                                 │ Neo4j         │ Suggestions
                                 │                │
                                 ▼                ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                       GATE 1: QUALITY & CLEANUP                            │
│                     Container: ttrpg_ingestion_engine                      │
└────────────────────────────────────────────────────────────────────────────┘
                                 │
    ┌────────────────────────────┼────────────────────────────┐
    ▼                            ▼                            ▼
┌────────────┐            ┌─────────────┐            ┌──────────────┐
│  WORKER    │  (10min)   │   WORKER    │  (30min)   │   WORKER     │ (10min)
│gate_1_log  │  OPTIONAL  │  gate_1_db  │  OPTIONAL  │ gate_1_pipe  │ OPTIONAL
│_analyzer   │───────────▶│_remediation │───────────▶│_optimizer    │
│            │            │             │            │              │
└────────────┘            └─────────────┘            └──────┬───────┘
     │                                                       │
     │ Uses OpenAI                                          │ Uses OpenAI
     │ GPT-4o                                               │ GPT-4o-mini
     │                                                       │
     └───────────────────────────┬───────────────────────────┘
                                 ▼
                          ┌──────────────┐
                          │   WORKER     │  (5min)
                          │  gate_1_     │
                          │  cleanup     │
                          │              │
                          └──────┬───────┘
                                 │
                                 ▼
                          ┌──────────────┐
                          │   SUCCESS    │
                          │   complete/  │
                          │   {job_id}/  │
                          └──────────────┘


════════════════════════════════════════════════════════════════════════════
                            CONTAINER SUMMARY
════════════════════════════════════════════════════════════════════════════

┌─────────────────────────────┬──────────────────────────────────────────┐
│ CONTAINER NAME              │ WORKERS RUNNING                          │
├─────────────────────────────┼──────────────────────────────────────────┤
│ ttrpg_ingestion_engine      │ • gate_0_hash_worker                     │
│                             │ • gate_0_validate_worker                 │
│                             │ • doc_splitter_worker                    │
│                             │ • pass_a_metadata_worker                 │
│                             │ • pass_a_mongo_upsert_worker             │
│                             │ • pass_d_checksum_worker                 │
│                             │ • pass_d_hayhooks_worker                 │
│                             │ • pass_e_graph_builder_worker            │
│                             │ • pass_e_neo4j_upsert_worker             │
│                             │ • pass_f_validation_worker               │
│                             │ • gate_1_log_analyzer_worker             │
│                             │ • gate_1_db_remediation_worker           │
│                             │ • gate_1_pipeline_optimizer_worker       │
│                             │ • gate_1_cleanup_worker                  │
│                             │ (14 workers total)                       │
├─────────────────────────────┼──────────────────────────────────────────┤
│ ttrpg_unstructured          │ • unstructured_job_worker                │
│                             │ (1 worker - handles Unstructured.io)     │
└─────────────────────────────┴──────────────────────────────────────────┘

┌─────────────────────────────┬──────────────────────────────────────────┐
│ SERVICE CONTAINERS          │ PURPOSE                                  │
├─────────────────────────────┼──────────────────────────────────────────┤
│ ttrpg_mongodb               │ Store elements & metadata                │
│ ttrpg_cassandra             │ Store checksums & vector embeddings      │
│ ttrpg_neo4j                 │ Store knowledge graph                    │
│ ttrpg_hayhooks              │ Generate OpenAI embeddings               │
│ ttrpg_hgrn                  │ HGRN validation & remediation            │
└─────────────────────────────┴──────────────────────────────────────────┘


════════════════════════════════════════════════════════════════════════════
                         PROCESSING TIME BREAKDOWN
════════════════════════════════════════════════════════════════════════════

Stage                          Time        Critical    Container
────────────────────────────────────────────────────────────────────────────
gate_0_hash                    0.5s        YES         ttrpg_ingestion_engine
gate_0_validate                0.7s        YES         ttrpg_ingestion_engine
doc_splitter                   ~5s         NO          ttrpg_ingestion_engine
pass_a_unstructured            varies      YES         ttrpg_unstructured
pass_a_metadata                <5min       YES         ttrpg_ingestion_engine
pass_a_mongo_upsert            <10min      YES         ttrpg_ingestion_engine
pass_d_checksum                <1min       YES         ttrpg_ingestion_engine
pass_d_hayhooks                ~2hrs       YES         ttrpg_ingestion_engine
pass_e_graph_builder           <30min      YES         ttrpg_ingestion_engine
pass_e_neo4j_upsert            <30min      YES         ttrpg_ingestion_engine
pass_f_validation              <30min      YES         ttrpg_ingestion_engine
gate_1_log_analyzer            <10min      NO          ttrpg_ingestion_engine
gate_1_db_remediation          <30min      NO          ttrpg_ingestion_engine
gate_1_pipeline_optimizer      <10min      NO          ttrpg_ingestion_engine
gate_1_cleanup                 <5min       YES         ttrpg_ingestion_engine
────────────────────────────────────────────────────────────────────────────
TOTAL ESTIMATED TIME:          2-3 hours (dominated by hayhooks embeddings)

Critical = Required for pipeline success
Non-Critical = Optional quality/optimization stages


════════════════════════════════════════════════════════════════════════════
                            DATA FLOW SUMMARY
════════════════════════════════════════════════════════════════════════════

PDF Source
   │
   ├──▶ Gate 0: Hash + Validate ──▶ Document ID + Validation Status
   │
   ├──▶ Pass A: Unstructured + Metadata ──▶ Elements + TOC ──▶ MongoDB
   │
   ├──▶ Pass D: Checksum + Embeddings ──▶ Vectors ──▶ Cassandra
   │
   ├──▶ Pass E: Graph Building ──▶ Nodes + Edges ──▶ Neo4j
   │
   ├──▶ Pass F: Validation ──▶ HGRN Reports + Remediations
   │
   └──▶ Gate 1: Quality + Cleanup ──▶ Logs + Optimization + Cleanup


════════════════════════════════════════════════════════════════════════════
                        SHARED VOLUME STRUCTURE
════════════════════════════════════════════════════════════════════════════

/Transfer_Station/
├── jobs/                          # Job queues (marker-based routing)
│   ├── gate_0_hash/
│   ├── gate_0_validate/
│   ├── doc_splitter/
│   ├── unstructured/
│   ├── pass_a_metadata/
│   ├── pass_a_mongo_upsert/
│   ├── pass_d_checksum/
│   ├── pass_d_hayhooks/
│   ├── pass_e_graph_builder/
│   ├── pass_e_neo4j_upsert/
│   ├── pass_f_validation/
│   ├── gate_1_log_analyzer/
│   ├── gate_1_db_remediation/
│   ├── gate_1_pipeline_optimizer/
│   ├── gate_1_cleanup/
│   ├── complete/                  # Terminal success state
│   └── failed/                    # Terminal failure state
│
├── scripts/                       # Worker executables
│   ├── *_worker.py (14 workers)
│   └── start_all_workers.sh
│
├── Logs/                          # Worker logs + heartbeats
│   ├── gate_0_hash/
│   │   ├── worker.log
│   │   └── heartbeat.json
│   └── ... (one per stage)
│
└── sources/                       # Input PDFs
