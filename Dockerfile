FROM python:3.10-slim

WORKDIR /app

COPY worker.py /app/worker.py

CMD ["python", "/app/worker.py"]