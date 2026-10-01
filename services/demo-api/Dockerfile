# Golden-path service image — no build cache surprises.
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
COPY app/ ./app/

# Minimal runtime: uvicorn only, not the dev toolchain.
RUN pip install --no-cache-dir "uvicorn[standard]>=0.30,<1"

EXPOSE 8080

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
