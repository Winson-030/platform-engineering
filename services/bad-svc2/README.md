# bad-svc2

Golden-path service scaffolded by `platformctl`. Ships with the guardrails the
platform team requires — you start from here, not from scratch.

## What you get

- `Dockerfile` — slim base, uvicorn, no dev tooling in the image.
- `kubernetes.yaml` — Deployment + Service with **resource requests/limits** and a `/health` readiness probe.
- `app/main.py` — FastAPI skeleton with `/health`.

## Run it

```bash
python3 ../platformctl.py scaffold bad-svc2 --port 8080   # from platform-engineering/
cd bad-svc2
# build + push the image, then kubectl apply -f kubernetes.yaml
```

## Golden-path guardrails (enforced by `platformctl lint`)

| Guardrail | Why |
|-----------|-----|
| Resource requests **and** limits | Prevents noisy-neighbor OOM kills and unbounded cost. |
| `/health` readiness probe | K8s routes traffic only when the pod is truly ready. |
| Single source template | Every service looks the same → less review burden. |

## Adding more (the lazy way)

More guardrails live in one place: `platformctl.py` → `GUARDRAILS`. Add a string
to `"k8s"` and it's enforced everywhere. Don't copy-paste manifests.
