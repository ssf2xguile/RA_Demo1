import requests
import uuid
import threading

API_URL = "http://nginx_proxy/api/v1/vehicle/climate/start"
# 一度に送信するリクエストの数を増やす
CONCURRENT_REQUESTS = 100

def send_climate_command():
    """エアコン起動リクエストを送信する単一の関数"""
    request_id = str(uuid.uuid4())
    print(f"Client: [Req ID: {request_id}] Sending request...")
    
    try:
        response = requests.post(
            API_URL, 
            json={"user_id": f"user-{uuid.uuid4().hex[:6]}", "vehicle_id": "vin-sim-456"},
            headers={"X-Request-ID": request_id},
            # Nginxのタイムアウト(60s)より少し長めに設定
            timeout=65
        )
        response.raise_for_status()
        print(f"Client: [Req ID: {request_id}] Success! Response: {response.json()}")

    except requests.exceptions.Timeout:
        print(f"Client: [Req ID: {request_id}] ERROR! Operation timed out.")
    except requests.exceptions.RequestException as e:
        print(f"Client: [Req ID: {request_id}] An unexpected error occurred: {e}")

if __name__ == "__main__":
    print(f"--- Starting a burst of {CONCURRENT_REQUESTS} concurrent requests ---")
    threads = []
    for _ in range(CONCURRENT_REQUESTS):
        thread = threading.Thread(target=send_climate_command)
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()
    
    print("--- Burst finished ---")