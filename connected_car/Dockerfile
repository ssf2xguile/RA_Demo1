FROM python:3.11-slim
WORKDIR /app
COPY simulator.py .
RUN pip install --no-cache-dir fastapi uvicorn
CMD ["uvicorn", "simulator:app", "--host", "0.0.0.0", "--port", "8001"]