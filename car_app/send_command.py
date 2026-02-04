import os
import asyncio
import uuid
import logging
import random
import httpx
import time
import multiprocessing

# ログ設定
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger("LoadGenerator")

API_URL = os.getenv("API_URL", "http://nginx:80/api/v1/vehicle/climate/start")
NUM_USERS = int(os.getenv("NUM_USERS", "31300"))
USER_PREFIX = os.getenv("USER_PREFIX", "user")

# 負荷設定
NORMAL_BURST = 20
OVERLOAD_BURST = 270
BURST_INTERVAL_S = 5

# httpx 設定
TIMEOUT_S = float(os.getenv("CLIENT_TIMEOUT_S", "65"))

def pick_user_and_vehicle():
    i = random.randrange(NUM_USERS)
    user_id = f"{USER_PREFIX}-{i:06d}"
    vehicle_id = f"vin-{i:06d}"
    proxy_session = f"dev-{i:06d}"
    return user_id, vehicle_id, proxy_session

# ==========================================
# Process 1: リクエスト送信役 (Requester)
# サーバーを落とすことだけに集中し、結果の集計は最低限にする
# ==========================================
async def send_request(client):
    user_id, vehicle_id, proxy_session = pick_user_and_vehicle()
    request_id = str(uuid.uuid4())
    try:
        # レスポンスの中身は読まずに閉じることで負荷を軽減
        await client.post(
            API_URL,
            json={"user_id": user_id, "vehicle_id": vehicle_id},
            headers={"X-Request-ID": request_id, "X-Proxy-Session": proxy_session},
        )
    except:
        pass # 攻撃側はエラーを無視する（測定はMonitorに任せる）

async def request_burst(client, n, batch_id):
    logger.info(f"[Requester] Batch {batch_id} FIRE! ({n} reqs)")
    # create_taskだけで保持せず、結果も待たない（Fire and Forgetの徹底）
    for _ in range(n):
        asyncio.create_task(send_request(client))

async def run_requester():
    # リクエスト送信用は制限を緩くする
    limits = httpx.Limits(max_connections=10000, max_keepalive_connections=10000)
    timeout = httpx.Timeout(TIMEOUT_S)

    async with httpx.AsyncClient(limits=limits, timeout=timeout) as client:
        start_time = time.time()
        batch_id = 0
        logger.info("=== [Requester] Process Started ===")

        while True:
            batch_id += 1
            loop_start = time.time()
            elapsed = loop_start - start_time

            # フェーズ判定
            if elapsed < 20:
                burst_size = NORMAL_BURST
            else:
                burst_size = OVERLOAD_BURST

            # バースト実行（投げっぱなし）
            asyncio.create_task(request_burst(client, burst_size, batch_id))

            # 正確なインターバル制御
            sleep_duration = BURST_INTERVAL_S - (time.time() - loop_start)
            if sleep_duration > 0:
                await asyncio.sleep(sleep_duration)
            else:
                # 遅延しても即座に次を撃つ（攻撃の手を緩めない）
                await asyncio.sleep(0)

def start_requester_process():
    try:
        asyncio.run(run_requester())
    except KeyboardInterrupt:
        pass

# ==========================================
# Process 2: 監視役 (Monitor)
# 定期的(1秒ごと)にリクエストを送り、正確な死活監視を行う
# ==========================================
async def run_monitor():
    # 監視用は独立したクライアント
    limits = httpx.Limits(max_connections=10, max_keepalive_connections=10)
    timeout = httpx.Timeout(TIMEOUT_S)

    async with httpx.AsyncClient(limits=limits, timeout=timeout) as client:
        logger.info("=== [Monitor] Process Started (1 probe/sec) ===")
        
        while True:
            user_id, vehicle_id, proxy_session = pick_user_and_vehicle()
            req_id = f"MONITOR-{uuid.uuid4()}"
            start_ts = time.time()
            status = "UNKNOWN"
            
            try:
                resp = await client.post(
                    API_URL,
                    json={"user_id": user_id, "vehicle_id": vehicle_id},
                    headers={"X-Request-ID": req_id, "X-Proxy-Session": proxy_session},
                )
                duration = time.time() - start_ts
                status = resp.status_code
                
                if status == 200:
                    logger.info(f"[Monitor] OK ({duration:.2f}s)")
                else:
                    logger.error(f"[Monitor] ERROR Status:{status} ({duration:.2f}s)")

            except httpx.ReadTimeout:
                logger.error(f"[Monitor] TIMEOUT > {TIMEOUT_S}s")
            except httpx.ConnectError:
                logger.error(f"[Monitor] CONNECTION REFUSED (Server Down?)")
            except Exception as e:
                logger.error(f"[Monitor] EXCEPTION: {type(e).__name__}")

            # 1秒待機
            await asyncio.sleep(1)

def start_monitor_process():
    try:
        asyncio.run(run_monitor())
    except KeyboardInterrupt:
        pass

# ==========================================
# Main Entry Point
# ==========================================
if __name__ == "__main__":
    # リクエスト送信プロセスと監視プロセスを分離して起動
    requester = multiprocessing.Process(target=start_requester_process)
    monitor = multiprocessing.Process(target=start_monitor_process)

    requester.start()
    monitor.start()

    try:
        requester.join()
        monitor.join()
    except KeyboardInterrupt:
        requester.terminate()
        monitor.terminate()
        logger.info("Stopped by user.")
