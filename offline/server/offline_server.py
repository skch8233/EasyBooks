"""Entry point for the offline Windows build: runs the Easy Books API + web UI on 127.0.0.1."""
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = Path(getattr(sys, "_MEIPASS", HERE))
sys.path.insert(0, str(HERE.parent.parent / "backend"))

os.environ["OFFLINE_MODE"] = "1"
for k in ("MONGO_URL", "DB_NAME", "JWT_SECRET", "LICENCE_PUBLIC_KEY", "EB_DATA_DIR", "FRONTEND_DIR"):
    if not os.environ.get(k):
        sys.exit(f"Missing environment variable {k}")
os.environ.setdefault("CORS_ORIGINS", "*")
os.environ.setdefault("ADMIN_EMAIL", "offline@localhost")
os.environ.setdefault("ADMIN_PASSWORD", "unused")

import uvicorn  # noqa: E402
from fastapi.responses import FileResponse, JSONResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from server import app  # noqa: E402

FRONT = Path(os.environ["FRONTEND_DIR"])
app.mount("/static", StaticFiles(directory=FRONT / "static"), name="static")


@app.get("/{path:path}", include_in_schema=False)
async def spa(path: str):
    if path.startswith("api/"):
        return JSONResponse({"detail": "Not Found"}, status_code=404)
    f = (FRONT / path).resolve()
    if path and f.is_file() and FRONT.resolve() in f.parents:
        return FileResponse(f)
    return FileResponse(FRONT / "index.html")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("EB_PORT", "8765")), log_level="warning")
