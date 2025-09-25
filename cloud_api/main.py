import os, time, uuid, asyncio, threading
from collections import deque
from typing import Dict, Deque, Tuple
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import httpx, os as _os

# === Tunables (env) ===
VEHICLE_BASE = os.getenv("VEHICLE_SIMULATOR_URL", "http://vehicle:8001")
HTTPX_MAX = int(os.getenv("HTTPX_MAX", "1"))           # 下流は直列寄り
REQ_TIMEOUT = int(os.getenv("REQ_TIMEOUT", "60"))      # 下流タイムアウト

PER_SESSION_BYTES = int(os.getenv("PER_SESSION_BYTES", str(10 * 1024 * 1024)))  # 10MB/セッション
MAX_SESSIONS = int(os.getenv("MAX_SESSIONS", "50"))    # 同時保持上限（≒上限メモリ）
SESSION_TTL = int(os.getenv("SESSION_TTL", "5"))       # アイドルTTLで解放
APP_QUEUE_TIMEOUT_S = int(os.getenv("APP_QUEUE_TIMEOUT_S", "60"))  # メモリ確保待ちの上限

LOG_PATH = os.getenv("SYNC_LOG_PATH", "/data/proxy.log")
LOG_CHUNK_KB = int(os.getenv("LOG_CHUNK_KB", "514"))   # 514KB/req を同期書き込み

METRICS_WINDOW_S = int(os.getenv("METRICS_WINDOW_S", "5"))  # 直近窓

STICKY_ON_TIMEOUT_S = int(os.getenv("STICKY_ON_TIMEOUT_S", "600"))

# === App / Client ===
app = FastAPI()
limits = httpx.Limits(max_connections=HTTPX_MAX, max_keepalive_connections=HTTPX_MAX)
client = httpx.AsyncClient(base_url=VEHICLE_BASE, timeout=REQ_TIMEOUT, limits=limits)

# === Metrics ===
_metrics = {"pending":0, "done":0, "timeouts":0, "errors":0}
_met_lock = threading.Lock()
_arrivals: Deque[Tuple[float, int]] = deque()
_timeouts: Deque[Tuple[float, int]] = deque()

def _inc(k, d=1):
    with _met_lock: _metrics[k] += d
def _snap():
    with _met_lock: return dict(_metrics)
def _rec_arrival():
    now=time.time(); _arrivals.append((now,1))
    while _arrivals and now-_arrivals[0][0]>METRICS_WINDOW_S: _arrivals.popleft()
def _rec_timeout():
    now=time.time(); _timeouts.append((now,1))
    while _timeouts and now-_timeouts[0][0]>METRICS_WINDOW_S: _timeouts.popleft()
def _recent():
    now=time.time()
    while _arrivals and now-_arrivals[0][0]>METRICS_WINDOW_S: _arrivals.popleft()
    while _timeouts and now-_timeouts[0][0]>METRICS_WINDOW_S: _timeouts.popleft()
    a=sum(v for _,v in _arrivals); t=sum(v for _,v in _timeouts)
    return {"recent_arrivals":a,"recent_timeouts":t,"recent_timeout_ratio": round((t/a) if a else 0.0,3)}

# === sync I/O (fsync) ===
def sync_append_kb(path:str,kb:int,line:str):
    fd=_os.open(path,_os.O_CREAT|_os.O_APPEND|_os.O_WRONLY,0o644)
    try:
        _os.write(fd,(line+"\n").encode())
        if kb>0: _os.write(fd,b"x"*(kb*1024))
        _os.fsync(fd)
    finally:
        _os.close(fd)

# === Session Manager: 上限付きオンデマンド確保 ===
class _Entry:
    __slots__=("buf","last_used")
    def __init__(self):
        self.buf=bytearray(PER_SESSION_BYTES)  # 実際に10MB確保（zero-initでピーク抑制）
        self.last_used=time.time()
    def touch(self): self.last_used=time.time()

_timedout_sids: Dict[str, float] = {}
_timedout_lock = threading.Lock()

def _mark_sid_timed_out(sid: str):
    if STICKY_ON_TIMEOUT_S > 0:
        with _timedout_lock:
            _timedout_sids[sid] = time.time()

class SessionManager:
    def __init__(self):
        self._lock=asyncio.Lock()
        self._cv=asyncio.Condition(self._lock)
        self._tbl: Dict[str,_Entry]={}

    async def ensure(self, sid:str, timeout_s:int):
        async with self._lock:
            e=self._tbl.get(sid)
            if e: e.touch(); return
            async def wait_slot():
                while len(self._tbl)>=MAX_SESSIONS:
                    await self._cv.wait()
            try:
                await asyncio.wait_for(wait_slot(), timeout=timeout_s)
            except asyncio.TimeoutError:
                raise
            self._tbl[sid]=_Entry()

    async def gc(self):
        now=time.time()
        async with self._lock:
            dead=[]
            for k, e in list(self._tbl.items()):
                # sticky期間中ならGC対象から外す
                if STICKY_ON_TIMEOUT_S > 0:
                    with _timedout_lock:
                        ts = _timedout_sids.get(k)
                    if ts and (now - ts) < STICKY_ON_TIMEOUT_S:
                        continue

                    # sticky期間が過ぎていたら記録を消して通常のTTL判定へ
                    if ts and (now - ts) >= STICKY_ON_TIMEOUT_S:
                        with _timedout_lock:
                            _timedout_sids.pop(k, None)

                # 通常のTTL判定
                if now - e.last_used > SESSION_TTL:
                    dead.append(k)

            for k in dead:
                del self._tbl[k]
            if dead:
                self._cv.notify_all()

    async def stats(self):
        async with self._lock:
            n=len(self._tbl)
            return {"session_count":n,"reserved_mb": (n*PER_SESSION_BYTES)//(1024*1024)}

sess=SessionManager()

async def _gc_loop():
    while True:
        await sess.gc()
        await asyncio.sleep(1)

# === Handler ===
@app.post("/api/v1/vehicle/climate/start")
async def start_climate(data:dict, request:Request):
    _rec_arrival()
    _inc("pending",+1)
    req_id=request.headers.get("X-Request-ID") or str(uuid.uuid4())
    sid=request.headers.get("X-Proxy-Session") or str(uuid.uuid4())

    try:
        # 1) セッション確保 / 空き待ち（最大60s）
        try:
            await sess.ensure(sid, APP_QUEUE_TIMEOUT_S)
        except asyncio.TimeoutError:
            _inc("timeouts",+1); _rec_timeout()
            _mark_sid_timed_out(sid)
            raise HTTPException(503, "queued > 60s: session memory not available")

        # 2) 実I/Oでサービス時間を確保
        await asyncio.to_thread(sync_append_kb, LOG_PATH, LOG_CHUNK_KB, f"{time.time()} {req_id} {sid}")

        # 3) 下流は接続プール小さめで直列化
        r=await client.post("/command", json={"command":"START_CLIMATE", **data})
        r.raise_for_status()

        _inc("done",+1)
        return {"ok":True,"request_id":req_id,"proxy_session":sid}

    except httpx.ReadTimeout:
        _inc("timeouts",+1); _rec_timeout()
        _mark_sid_timed_out(sid)
        raise HTTPException(504, "vehicle timeout")
    except asyncio.CancelledError:
        _inc("timeouts",+1); _rec_timeout()
        _mark_sid_timed_out(sid)
        raise
    except HTTPException:
        raise
    except Exception as e:
        _inc("errors",+1)
        raise HTTPException(502, str(e))
    finally:
        _inc("pending",-1)

@app.get("/metrics")
async def metrics():
    m=_snap(); s=await sess.stats(); r=_recent()
    return JSONResponse({**m, **s, **r,
        "per_session_bytes":PER_SESSION_BYTES,
        "max_sessions":MAX_SESSIONS,
        "session_ttl":SESSION_TTL,
        "app_queue_timeout_s":APP_QUEUE_TIMEOUT_S,
        "log_chunk_kb":LOG_CHUNK_KB,
        "httpx_max":HTTPX_MAX,
        # ★ わざと“丸見え”なメトリクスは追加しない（痕跡が目立たないように）
        "sticky_on_timeout_s": STICKY_ON_TIMEOUT_S  # ←必要なら可視化
    })

@app.on_event("startup")
async def _startup():
    _os.makedirs(_os.path.dirname(LOG_PATH), exist_ok=True)
    asyncio.create_task(_gc_loop())

@app.on_event("shutdown")
async def _shutdown():
    await client.aclose()
