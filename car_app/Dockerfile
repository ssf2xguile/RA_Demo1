FROM python:3.11-slim
WORKDIR /app
COPY send_command.py .
RUN pip install --no-cache-dir requests
CMD ["python", "send_command.py"]