from pathlib import Path
import os
from scripts.ingest import run

if __name__ == "__main__":
    os.environ.setdefault("APP_ENV", "dev")
    pdf = Path("uploads") / "Eberron Campaign Setting.pdf"
    code = run([pdf], os.getenv("APP_ENV", "dev"), False)
    raise SystemExit(code)

