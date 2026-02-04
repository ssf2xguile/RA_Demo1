FROM python:3.11-slim
WORKDIR /app
COPY send_command.py .
RUN pip install --no-cache-dir requests httpx==0.27.0
CMD ["python", "send_command.py"]