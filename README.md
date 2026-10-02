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

## Commands

```bash
python3 platformctl.py scaffold <name> --port 8080   # create services/<name>/
python3 platformctl.py lint services/<name>           # check guardrails
python3 platformctl.py render <name> --port 8080      # offline deploy pre-check
python3 platformctl.py verify                         # scaffold+lint+teardown probe
```

`render` is the deploy pre-check. It renders the golden path to a temp dir and
prints the guardrails (image, replicas, cpu/mem requests & limits, readiness
probe) so you can eyeball the manifest **without a cluster**. `kubectl apply`
itself still needs a real cluster — this demo runs headless, so `render` is the
verifiable offline stand-in for that step.

## Verified (2026-10-02)

```
$ render my-api --port 9000 → image / replicas / requests / limits / probe printed
$ verify                    → scaffold + lint + teardown, no stray files
$ lint services/demo-api    → ok — passes golden-path guardrails
```

## Next week (planned)

- Wire `lint` into a CI step so broken services can't be merged.
- Add a real `deploy` subcommand (renders then `kubectl apply`) once a demo
  cluster (k3d/minikube) is available — `render` already covers the offline half.
