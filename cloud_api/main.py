import asyncio
import requests
from fastapi import FastAPI, Request

VEHICLE_SIMULATOR_URL = "http://vehicle:8001/command"

app = FastAPI()

def heavy_cpu_task():
    """
    CPUに高い負荷をかける同期関数。
    これが実行されるスレッドをブロックします。
    """
    print("Starting heavy CPU task...")
    result = 0
    # 計算量を増やしてCPUを長時間占有させる
    for i in range(30_000_000):
        result += (i * i) % 12345
    print(f"Finished heavy CPU task with result: {result}")

@app.post("/api/v1/vehicle/climate/start")
async def start_climate(data: dict, request: Request):
    request_id = request.headers.get("X-Request-ID", "N/A")
    print(f"AppServer: [Req ID: {request_id}] Received request.")

    try:
        # 1. CPU負荷の高い同期処理を、FastAPIのワーカースレッドで実行する
        #    これにより、メインのイベントループをブロックせず、
        #    複数のリクエストが並行してCPUリソースを奪い合う状況を作り出す。
        await asyncio.to_thread(heavy_cpu_task)
        
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

    # このレスポンスはタイムアウトの場合クライアントに届かない
    return {"message": "Command processed", "request_id": request_id}