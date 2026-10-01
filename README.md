# Platform Engineering — golden-path IDP portfolio

4-week acceptance project. Week 2 deliverable (2026-10-01): a working
**internal-developer-platform CLI** that enforces a "golden path" for
self-serve service creation.

## What it is

`platformctl.py` — one stdlib-only Python file, no dependencies. New devs run a
single command to get a service that already ships the guardrails the platform
team cares about:

```bash
python3 platformctl.py scaffold <service-name> --port 8080   # creates services/<name>/
python3 platformctl.py lint services/<name>                  # checks guardrails
python3 platformctl.py verify                                # scaffold+lint+teardown probe
```

## The golden path

`scaffold` copies `templates/service/` → `services/<name>/`, rendering
`{{SERVICE_NAME}}` / `{{SERVICE_PORT}}` placeholders. Each service ships:

- `Dockerfile` — slim base, uvicorn, no dev tooling in the image.
- `kubernetes.yaml` — Deployment + Service with **resource requests/limits** and a `/health` readiness probe.
- `app/main.py` — FastAPI skeleton with `/health`.
- `README.md` — usage + guardrail rationale.

## Guardrails (the actual platform value)

Defined once in `platformctl.py::GUARDRAILS`, enforced by `lint`:

| Guardrail | Why |
|-----------|-----|
| Required files present | Every service looks the same → less review burden. |
| k8s `resources` requests/limits | No noisy-neighbor OOM kills, predictable cost. |
| `/health` readiness probe | K8s routes traffic only when a pod is truly ready. |
| No unrendered placeholders | Scaffolds are never shipped half-baked. |

## Verified (2026-10-01)

```
$ scaffold demo-api            → 5 files created
$ lint services/demo-api       → ok — passes golden-path guardrails
$ lint <missing k8s>           → FAIL, exit 1, actionable messages
$ verify                       → probe scaffolds + lints + tears down cleanly
```

## Next week (planned)

- Add a `deploy` subcommand that renders to a temp dir and calls `kubectl apply`
  (dry-run `--dry-run=client` first — no cluster required for the demo).
- Wire lint into a CI step so broken services can't be merged.
