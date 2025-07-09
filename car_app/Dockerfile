FROM python:3.11-slim

WORKDIR /app

COPY send_data.py .

RUN pip install --no-cache-dir --progress-bar off requests

CMD ["python", "send_data.py"]
