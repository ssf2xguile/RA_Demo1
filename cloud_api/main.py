import asyncio
import requests
import uuid
from fastapi import FastAPI, Request

VEHICLE_SIMULATOR_URL = "http://vehicle:8001/command"

# アプリケーションサーバーのメモリ上にセッション情報を保持する辞書
SESSION_STORE = {}

<<<<<<< HEAD
app = FastAPI()
=======
def heavy_cpu_task():
    """
    CPUに高い負荷をかける同期関数。
    これが実行されるスレッドをブロックします。
    """
    print("Starting heavy CPU task...")
    result = 0
    # 計算量を増やしてCPUを長時間占有させる
    for i in range(10_000_000):
        result += (i * i) % 12345
    print(f"Finished heavy CPU task with result: {result}")
>>>>>>> e6ea14b (CPU処理を重くする方針でシナリオを再現する)

@app.post("/api/v1/vehicle/climate/start")
async def start_climate(data: dict, request: Request):
    request_id = request.headers.get("X-Request-ID", "N/A")
    
    # 1. セッション情報をメモリに蓄積 (メモリリークのシミュレーション)
    session_id = str(uuid.uuid4())
    # 1セッションあたり約1MBのデータを生成
    session_data = ' ' * (1024 * 1024) 
    SESSION_STORE[session_id] = session_data
    
    memory_usage_mb = len(SESSION_STORE)
    print(f"AppServer: [Req ID: {request_id}] Received. Session stored. Total sessions: {len(SESSION_STORE)}, Approx memory: {memory_usage_mb} MB")

    try:
        await asyncio.sleep(0.5)
        
    except asyncio.CancelledError:
        print(f"AppServer: [Req ID: {request_id}] Detected client disconnection. Stopping process.")
        raise

    # 2. タイムアウト後も処理は続行され、車両シミュレータにコマンドを送信
    try:
        print(f"AppServer: [Req ID: {request_id}] Sending command to Vehicle Simulator...")
        requests.post(VEHICLE_SIMULATOR_URL, json={"command": "START_CLIMATE"})
        print(f"AppServer: [Req ID: {request_id}] Command sent successfully.")
    except requests.exceptions.RequestException as e:
        print(f"AppServer: [Req ID: {request_id}] Failed to send command to vehicle: {e}")

    return {"message": "Command processed", "request_id": request_id}