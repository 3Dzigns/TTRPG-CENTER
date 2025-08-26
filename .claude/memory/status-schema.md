# Memory: Status Event Schema

This schema defines the **structured events** each ingestion phase must emit for the Admin UI and for audit trails.  
All ingestion-related components are expected to follow this contract.

## Event Format

```json
{
  "job_id": "uuid",                  // unique per ingestion run
  "env": "dev|test|prod",            // environment source
  "phase": "upload|chunk|dictionary|embed|enrich|verify",
  "status": "queued|running|stalled|error|done",
  "progress": 0,                     // integer 0–100
  "updated_at": "ISO-8601 timestamp",
  "message": "short human-readable update",
  "logs_tail": ["..."],              // last 10–20 log lines
  "metrics": {
    "chunks": 0,
    "tokens": 0,
    "duration_ms": 0
  },
  "error": {
    "code": "string",
    "hint": "actionable guidance"
  }
}
