from pydantic import BaseModel
from sqlalchemy import Column, Integer, Float, DateTime
from database import Base  # ← ここで database.py の Base を使う
from datetime import datetime

class LocationDataORM(Base):
    __tablename__ = "locations"
    id = Column(Integer, primary_key=True, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

class LocationData(BaseModel):
    latitude: float
    longitude: float

    class Config:
        from_attributes = True  # ← pydantic v2 では orm_mode → from_attributes