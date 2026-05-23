import json
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, Request

LOGS = Path("/opt/internal-sink/logs")
LOGS.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="internal-sink")

@app.get("/")
def root():
    return {"app": "internal-sink", "status": "up"}

@app.post("/")
async def ingest(request: Request):
    body = await request.json()
    now = datetime.utcnow()
    fname = LOGS / f"{now.date().isoformat()}.md"
    event = body.get("event") if isinstance(body, dict) else None
    block = (
        f"\n## {now.isoformat()}Z  `{event}`\n\n"
        f"```json\n{json.dumps(body, indent=2, ensure_ascii=False)}\n```\n"
    )
    with fname.open("a", encoding="utf-8") as f:
        f.write(block)
    return {"ok": True}
