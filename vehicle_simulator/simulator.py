from fastapi import FastAPI

app = FastAPI()

# 車両の状態をメモリ上で保持
vehicle_state = {
    "is_climate_on": False
}

@app.post("/command")
def execute_command(command_data: dict):
    command = command_data.get("command")
    if command == "START_CLIMATE":
        if not vehicle_state["is_climate_on"]:
            # print("VehicleSimulator: Command received. Turning climate ON.")
            vehicle_state["is_climate_on"] = True
            # return {"status": "Climate turned ON"}
        #else:
        #   print("VehicleSimulator: Climate is already ON.")
        #   return {"status": "Climate was already ON"}
    
    #return {"status": "Unknown command"}

@app.get("/status")
def get_status():
    # print(f"VehicleSimulator: Status requested. Climate is {'ON' if vehicle_state['is_climate_on'] else 'OFF'}")
    return vehicle_state