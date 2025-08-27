import os, sys

REQUIRED = [
  "ASTRA_DB_API_ENDPOINT","ASTRA_DB_APPLICATION_TOKEN","ASTRA_DB_ID","ASTRA_DB_KEYSPACE","ASTRA_DB_REGION",
  "OPENAI_API_KEY","PORT","APP_ENV"
]

def load_config():
    missing = [k for k in REQUIRED if not os.getenv(k)]
    if missing:
        sys.exit(f"Missing required env keys: {', '.join(missing)}")
    return {
        "astra": {
            "endpoint": os.getenv("ASTRA_DB_API_ENDPOINT"),
            "token_present": bool(os.getenv("ASTRA_DB_APPLICATION_TOKEN")),
            "id": os.getenv("ASTRA_DB_ID"),
            "keyspace": os.getenv("ASTRA_DB_KEYSPACE"),
            "region": os.getenv("ASTRA_DB_REGION"),
        },
        "graph": {
            "id": os.getenv("ASTRA_GRAPHDB_ID"),
            "token_present": bool(os.getenv("ASTRA_GRAPHDB_TOKEN"))
        },
        "openai": {"key_present": bool(os.getenv("OPENAI_API_KEY"))},
        "runtime": {
            "env": os.getenv("APP_ENV"),
            "port": int(os.getenv("PORT")),
            "ngrok_enabled": os.getenv("NGROK_ENABLED","false").lower() == "true"
        }
    }