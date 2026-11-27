FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OHR_HAKSAV_MODEL_DIR=/app/model_assets

WORKDIR /app

COPY requirements-web.txt .
RUN pip install --no-cache-dir -r requirements-web.txt

COPY core/ ./core/
COPY web/ ./web/
COPY model_assets/ ./model_assets/
COPY version.json .

RUN test -s /app/model_assets/mishkefet-v1.pt

EXPOSE 8080

CMD ["uvicorn", "web.app:app", "--host", "0.0.0.0", "--port", "8080"]
