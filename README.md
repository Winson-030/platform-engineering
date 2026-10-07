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

## Week 3 — deploy subcommand (2026-10-06)

`deploy <name>` renders the golden path and validates the manifest **offline**
(no cluster). Default path parses `kubernetes.yaml` with PyYAML and asserts the
golden-path k8s markers (Deployment + Service present, container resource
requests/limits). `--apply` instead runs `kubectl apply` against a live cluster
(needs a real kubectl context + image registry).

```
$ deploy my-api --port 9000  → validated offline (no cluster)
$ deploy <resource-less>     → FAIL, actionable message
$ deploy services/bad-svc    → ok — passes both (weak fixture; a real bad service
                               would fail lint for unrendered placeholders)
```

> `deploy` and `lint` are complementary: `deploy` checks the manifest is valid
> K8s YAML with golden-path *semantics*; `lint` checks scaffolding *cleanliness*
> (files present, no unrendered placeholders). A service that ships half-baked
> fails lint; one that's valid but resource-less fails deploy.

Note: `kubectl --dry-run=client` still dials the cluster API to discover resource
kinds, so it cannot validate offline — hence the local PyYAML parse. Ceiling: the
offline check asserts keys we care about, not full k8s schema (lint covers the
rest).

## Week 4 — IDP CI gate (2026-10-07)

`.github/workflows/idp-ci.yml` runs `platformctl.py lint` on every service
directory **changed by the push or PR** (`git diff`), so a broken service can't
merge while untouched fixtures (like `bad-svc2`) don't fail the build.

```bash
# Local equivalent of the CI step:
python3 platformctl.py lint services/your-api   # exit 0 = mergeable
python3 platformctl.py lint services/bad-svc2   # exit 1 = blocked
```

- Stdlib-only: `lint` needs no pip installs (PyYAML ships with CPython ≥3.11), so
  the gate itself can't break on a missing dependency.
- Only changed service dirs are linted → fixtures and docs don't block merges.

## Next week (planned)

- Add a real `deploy --apply` path against a demo cluster (k3d/minikube) once one
  is available — offline validation already covers the pre-check half.
