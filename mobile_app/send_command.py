import os
import asyncio
import uuid
import logging
import random
import httpx
import time
import sys
import resource
import uvloop

# --- 設定 ---
# 1プロセスあたりの担当ユーザー数 (3000人)
USERS_PER_PROCESS = 3000
# 全体のサイクル秒数 (12プロセス × 5秒 = 60秒)
TOTAL_CYCLE_SECONDS = 60

# --- 引数/環境変数から設定値を取得 ---
# プロセスID (0〜11) を環境変数または引数から取得
try:
    PROCESS_ID = int(os.getenv("PROCESS_ID", sys.argv[1] if len(sys.argv) > 1 else "0"))
except ValueError:
    PROCESS_ID = 0

# このプロセスが担当するユーザーIDの開始番号
# Proc 0: 0-2999, Proc 1: 3000-5999, ...
USER_ID_OFFSET = PROCESS_ID * USERS_PER_PROCESS

# ログ設定
logging.basicConfig(level=logging.INFO, format=f"[Proc-{PROCESS_ID:02d}] %(asctime)s - %(message)s")
logger = logging.getLogger("LoadGenerator")

API_URL = os.getenv("API_URL", "http://nginx:80/api/v1/vehicle/climate/start")
USER_PREFIX = os.getenv("USER_PREFIX", "user")

# 負荷設定
# 最初の数回は少なめ、その後本気出す
NORMAL_BURST = 20
OVERLOAD_BURST = 270

TIMEOUT_S = float(os.getenv("CLIENT_TIMEOUT_S", "65"))

def maximize_fd_limit():
    try:
        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        resource.setrlimit(resource.RLIMIT_NOFILE, (hard, hard))
    except Exception:
        pass

def pick_user_and_vehicle():
    # 担当範囲 (Offset 〜 Offset + 2999) からランダムに選ぶ
    i = USER_ID_OFFSET + random.randrange(USERS_PER_PROCESS)
    user_id = f"{USER_PREFIX}-{i:06d}"
    vehicle_id = f"vin-{i:06d}"
    proxy_session = f"dev-{i:06d}"
    return user_id, vehicle_id, proxy_session

async def send_request(client):
    user_id, vehicle_id, proxy_session = pick_user_and_vehicle()
    request_id = str(uuid.uuid4())
    try:
        await client.post(
            API_URL,
            json={"user_id": user_id, "vehicle_id": vehicle_id},
            headers={"X-Request-ID": request_id, "X-Proxy-Session": proxy_session},
        )
    except:
        pass

async def request_burst(client, n, batch_id):
    logger.info(f"Batch {batch_id} FIRE! ({n} reqs)")
    for _ in range(n):
        asyncio.create_task(send_request(client))

async def run_requester():
    uvloop.install()
    maximize_fd_limit()

    limits = httpx.Limits(max_connections=5000, max_keepalive_connections=5000)
    timeout = httpx.Timeout(TIMEOUT_S)

    async with httpx.AsyncClient(limits=limits, timeout=timeout) as client:
        # 基準となる開始時刻
        base_start_time = time.time()
        
        # 自分の最初の送信タイミングまで待機 (0, 5, 10... 55秒)
        initial_delay = PROCESS_ID * 5
        logger.info(f"Waiting {initial_delay}s to start first burst...")
        await asyncio.sleep(initial_delay)

        batch_id = 0
        while True:
            batch_id += 1
            loop_start = time.time()
            
            # 経過時間（全体）
            elapsed_total = loop_start - base_start_time

            # 最初の20秒（全体時間での判断）はウォームアップ
            if elapsed_total < 20 + initial_delay:
                 burst_size = NORMAL_BURST
            else:
                 burst_size = OVERLOAD_BURST

            # バースト実行
            asyncio.create_task(request_burst(client, burst_size, batch_id))

            # 次のサイクル (60秒後) まで待機
            now = time.time()
            sleep_duration = TOTAL_CYCLE_SECONDS - (now - loop_start)
            
            if sleep_duration > 0:
                await asyncio.sleep(sleep_duration)
            else:
                await asyncio.sleep(0)

# Monitorプロセスは別途立ち上げるため、ここにはRequesterのみ記述
if __name__ == "__main__":
    try:
        asyncio.run(run_requester())
    except KeyboardInterrupt:
        pass
