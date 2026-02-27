FROM python:3.11-slim
WORKDIR /app
COPY send_command.py .
COPY launcher.py .
RUN pip install --no-cache-dir requests httpx==0.27.0 uvloop
CMD ["python", "launcher.py"]