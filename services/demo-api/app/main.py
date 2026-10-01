# Minimal API service scaffolded by platformctl.
from fastapi import FastAPI  # noqa: F401 (service code lives here, not in the platform)

app = FastAPI(title="demo-api", version="1.0.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "demo-api"}


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "demo-api", "docs": "/docs"}
