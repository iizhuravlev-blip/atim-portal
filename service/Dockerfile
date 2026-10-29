# АТИМ Управление — центральная страница, upr.atimlab.ru. Сборка: docker compose -f service/docker-compose.yml build
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 TZ=Europe/Moscow DATA_DIR=/data

WORKDIR /app
COPY service/requirements.txt .
RUN pip install -r requirements.txt

COPY service/app app
COPY service/tests tests
COPY service/pytest.ini .

RUN useradd -u 10001 -m app && mkdir -p /data && chown app:app /data
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/health')"
ENV FORWARDED_ALLOW_IPS=172.18.0.0/16,127.0.0.1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
