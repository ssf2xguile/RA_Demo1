import asyncio
import requests
import threading
import logging 
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

VEHICLE_SIMULATOR_URL = "http://vehicle:8001/command"

app = FastAPI()

pending_requests = 0
processed_requests = 0
metrics_lock = threading.Lock()

def heavy_cpu_task():
    """CPUに高い負荷をかける同期関数"""
    logging.info("Starting heavy CPU task...")
    result = 0
    for i in range(10_000_000):
        result += (i * i) % 12345
    logging.info(f"Finished heavy CPU task with result: {result}")

@app.post("/api/v1/vehicle/climate/start")
async def start_climate(data: dict, request: Request):
    global pending_requests, processed_requests
    request_id = request.headers.get("X-Request-ID", "N/A")
    #logging.info(f"AppServer: [Req ID: {request_id}] Received.")

    with metrics_lock:
        pending_requests += 1
    
    try:
        await asyncio.to_thread(heavy_cpu_task)
        
    except asyncio.CancelledError:
        logging.warning(f"AppServer: [Req ID: {request_id}] Detected client disconnection. Stopping process.")
        with metrics_lock:
            pending_requests -= 1
        raise

    try:
        #logging.info(f"AppServer: [Req ID: {request_id}] Sending command to Vehicle Simulator...")
        requests.post(VEHICLE_SIMULATOR_URL, json={"command": "START_CLIMATE"})
        logging.info(f"AppServer: [Req ID: {request_id}] Command sent successfully.")
    except requests.exceptions.RequestException as e:
        logging.error(f"AppServer: [Req ID: {request_id}] Failed to send command to vehicle: {e}")
    finally:
        with metrics_lock:
            pending_requests -= 1
            processed_requests += 1

    return {"message": "Command processed", "request_id": request_id}

@app.get("/metrics")
async def get_metrics():
    with metrics_lock:
        return JSONResponse(content={
            "pending_requests": pending_requests,
            "processed_requests": processed_requests
        })

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
