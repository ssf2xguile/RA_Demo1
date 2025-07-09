import asyncio
from fastapi import FastAPI, HTTPException
from models import LocationData, LocationDataORM
from database import engine, SessionLocal, Base
from sqlalchemy.orm import Session
import traceback

app = FastAPI()
Base.metadata.create_all(bind=engine)

@app.post("/location")
async def receive_location(data: LocationData):
    await asyncio.sleep(2)  # nginxのproxy_read_timeout(1s)に引っかけるための遅延
    db: Session = SessionLocal()
    try:
        orm_obj = LocationDataORM(**data.dict())  # ← ここが重要
        db.add(orm_obj)
        db.commit()
        return {"message": "Location saved"}
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()
