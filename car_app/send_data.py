# car_app/send_data.py

import time
import random
import requests

def get_location():
    lat = round(random.uniform(35.0, 36.0), 6)
    lon = round(random.uniform(139.0, 140.0), 6)
    return {"latitude": lat, "longitude": lon}

def send_data():
    while True:
        data = get_location()
        try:
            response = requests.post("http://nginx/location", json=data, timeout=1) # 意図的に短いタイムアウトを設定
            print(f"[SEND] status={response.status_code}, body={response.text}")
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Failed to send data: {e}")
        time.sleep(5)

if __name__ == "__main__":
    send_data()
