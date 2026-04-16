FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .
COPY frontend/ ../frontend/

ENV INSTANCE_ID=huggingface-replica
ENV PORT=7860

EXPOSE 7860

CMD ["python", "app.py"]
