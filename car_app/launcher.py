import subprocess
import sys
import time
import signal
import os

processes = []

def signal_handler(sig, frame):
    print("\n[Launcher] Stopping all processes...")
    for p in processes:
        p.terminate()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

print("=== Starting 12 Load Generator Processes + 1 Monitor ===")

# 1. 12個のリクエスト送信プロセスを起動
for i in range(12):
    cmd = [sys.executable, "send_command.py"]
    
    # 環境変数をコピーして、PROCESS_IDをセット
    env = os.environ.copy()
    env["PROCESS_ID"] = str(i)
    env["PYTHONUNBUFFERED"] = "1"

    p = subprocess.Popen(cmd, env=env)
    processes.append(p)
    print(f"[Launcher] Started Requester Process-{i}")

# 2. 監視用プロセスを別途起動 (send_command.pyに実装するより分離した方が良いが、今回は簡易的に同じスクリプトのモード違いと仮定するか、別途monitor専用スクリプトがあればそちらを呼ぶ)
# 既存コードの構成上、Monitor用の関数を別ファイルに切り出すか、
# ここでMonitor専用の小さなスクリプトを実行するのが綺麗です。
# 今回は簡易的なMonitorをインラインで実行する別スクリプト(monitor_runner.py)を作って呼ぶ形にします。

# 簡易Monitorスクリプトの生成（ファイルがなければ作る）
monitor_script = """
import asyncio
import httpx
import time
import uuid
import logging
import os
import uvloop

logging.basicConfig(level=logging.INFO, format="[Monitor] %(asctime)s - %(message)s")
logger = logging.getLogger("Monitor")
API_URL = os.getenv("API_URL", "http://nginx:80/api/v1/vehicle/climate/start")
TIMEOUT_S = float(os.getenv("CLIENT_TIMEOUT_S", "60"))

async def run_monitor():
    uvloop.install()
    limits = httpx.Limits(max_connections=10, max_keepalive_connections=10)
    async with httpx.AsyncClient(limits=limits, timeout=TIMEOUT_S) as client:
        logger.info("Started (1 probe/sec)")
        while True:
            # MonitorはランダムなユーザーIDでOK
            req_id = f"MONITOR-{uuid.uuid4()}"
            start_ts = time.time()
            try:
                resp = await client.post(
                    API_URL,
                    json={"user_id": "monitor-user", "vehicle_id": "monitor-vin"},
                    headers={"X-Request-ID": req_id},
                )
                duration = time.time() - start_ts
                if resp.status_code == 200:
                    logger.info(f"OK ({duration:.2f}s)")
                else:
                    logger.error(f"ERROR Status:{resp.status_code} ({duration:.2f}s)")
            except Exception as e:
                logger.error(f"FAILED: {type(e).__name__}")
            await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(run_monitor())
"""

with open("monitor_runner.py", "w") as f:
    f.write(monitor_script)

# Monitorプロセスの起動
p_mon = subprocess.Popen([sys.executable, "monitor_runner.py"], env=os.environ.copy())
processes.append(p_mon)
print("[Launcher] Started Monitor Process")

# プロセス終了待ち
for p in processes:
    p.wait()
