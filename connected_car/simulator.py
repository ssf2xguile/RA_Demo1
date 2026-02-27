from fastapi import FastAPI

app = FastAPI()

# vehicle_id -> state をメモリ上で保持
vehicle_state = {}

@app.post("/command")
def execute_command(command_data: dict):
    command = command_data.get("command")
    vehicle_id = command_data.get("vehicle_id", "unknown")

    if command == "START_CLIMATE":
        state = vehicle_state.setdefault(vehicle_id, {"is_climate_on": False})

        if not state["is_climate_on"]:
            print(f"VehicleSimulator[{vehicle_id}]: Command received. Turning climate ON.")
            state["is_climate_on"] = True
            return {"status": "Climate turned ON", "vehicle_id": vehicle_id}
        else:
            print(f"VehicleSimulator[{vehicle_id}]: Climate is already ON.")
            return {"status": "Climate was already ON", "vehicle_id": vehicle_id}

    return {"status": "Unknown command", "vehicle_id": vehicle_id}

@app.get("/status")
def get_status():
    return {"vehicle_count": len(vehicle_state)}
