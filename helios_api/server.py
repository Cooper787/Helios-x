from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import subprocess
import os
import signal
from pathlib import Path
from typing import Optional

app = FastAPI(title="Helios-X Control API")

STATE_DIR = Path("state")
AUDIT_PATH = STATE_DIR / "audit.jsonl"
KILL_PATH = STATE_DIR / "KILL"
PID_PATH = STATE_DIR / "rogue_x.pid"

class StartRequest(BaseModel):
    symbol: str = "SPLG"
    capital: float = 500
    qty: int = 1
    run_seconds: int = 1800

def _read_pid() -> Optional[int]:
    try:
        if PID_PATH.exists():
            return int(PID_PATH.read_text().strip())
    except:
        pass
    return None

def _is_running() -> bool:
    pid = _read_pid()
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except:
        return False

@app.get("/status")
def status():
    return {
        "running": _is_running(),
        "pid": _read_pid(),
        "kill_switch": KILL_PATH.exists(),
        "audit_exists": AUDIT_PATH.exists(),
    }

@app.post("/start")
def start(req: StartRequest):
    if _is_running():
        raise HTTPException(400, "Already running")
    
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if KILL_PATH.exists():
        KILL_PATH.unlink()
    
    cmd = [
        "python", "-m", "strategy", "run",
        "--symbol", req.symbol,
        "--capital", str(req.capital),
        "--qty", str(req.qty),
    ]
    
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    PID_PATH.write_text(str(proc.pid))
    return {"started": True, "pid": proc.pid}

@app.post("/stop")
def stop():
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    KILL_PATH.write_text("1")
    return {"stopping": True}

@app.post("/kill")
def kill():
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    KILL_PATH.write_text("1")
    
    pid = _read_pid()
    if not pid:
        return {"killed": False, "reason": "no pid"}
    
    try:
        os.kill(pid, signal.SIGKILL)
        return {"killed": True, "pid": pid}
    except Exception as e:
        return {"killed": False, "error": str(e)}

@app.get("/audit/tail")
def audit_tail(n: int = 200):
    if not AUDIT_PATH.exists():
        return {"lines": []}
    
    lines = AUDIT_PATH.read_text().splitlines()[-n:]
    parsed = []
    for ln in lines:
        try:
            import json
            parsed.append(json.loads(ln))
        except:
            parsed.append({"raw": ln})
    return {"lines": parsed}
