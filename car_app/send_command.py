import requests
import uuid
import threading
import time
import logging 
import sys 

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


API_URL = "http://nginx:80/api/v1/vehicle/climate/start" # nginx_proxyからnginxに変更

def send_request(request_id):
    """リクエストを1件送信する"""
    #logging.info(f"Client: [Req ID: {request_id}] Sending request...")
    try:
        response = requests.post(
            API_URL, 
            json={"user_id": f"user-{uuid.uuid4().hex[:6]}", "vehicle_id": "vin-sim-456"},
            headers={"X-Request-ID": request_id},
            timeout=65
        )
        response.raise_for_status()
        #logging.info(f"Client: [Req ID: {request_id}] Success!")
    except requests.exceptions.Timeout:
        # エラーなのでlogging.errorに変更
        logging.error(f"Client: [Req ID: {request_id}] ERROR! Operation timed out.")
    except requests.exceptions.RequestException as e:
        # エラーなのでlogging.errorに変更
        logging.error(f"Client: [Req ID: {request_id}] ERROR! An unexpected error occurred: {e}")

def run_burst(num_requests):
    """指定された数のリクエストを並行して送信する"""
    threads = []
    for _ in range(num_requests):
        req_id = str(uuid.uuid4())
        thread = threading.Thread(target=send_request, args=(req_id,))
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

if __name__ == "__main__":
    start_time = time.time()
    # 最初の20秒間は、5秒ごとに10件の同時リクエストを送信（正常な負荷）
    logging.info("\n" + "="*50)
    logging.info("="*50 + "\n")
    while time.time() - start_time < 20:
        run_burst(10)
        time.sleep(5)

    # 20秒経過後、5秒ごとに200件の同時リクエストを送信（過負荷）
    logging.info("\n" + "="*50)
    logging.info("="*50 + "\n")
    while True:
        run_burst(200)
        time.sleep(5)
