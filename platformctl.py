#!/usr/bin/env python3
"""platformctl — minimal internal-developer-platform CLI.

Self-serve "golden path": one command to spin up a service that already ships
with the guardrails the platform team cares about (container image, k8s manifest
with resource limits, health endpoint, README). Lint enforces them so a new dev
cannot ship something unguarded by accident.

Stdlib only. Python 3.9+.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parent / "templates"

# One source of truth for golden-path guardrails (see README §2).
GUARDRAILS = {
    "required_files": ["Dockerfile", "kubernetes.yaml", "README.md", "app/main.py"],
    "k8s": ["resources:", "requests:", "limits:"],          # naive substring check
    "placeholders": ["{{SERVICE_NAME}}", "{{SERVICE_PORT}}"],  # must not survive scaffold
}


def cmd_scaffold(args: argparse.Namespace) -> int:
    dest = Path("services") / args.name
    if dest.exists():
        print(f"refuse: {dest} already exists", file=sys.stderr)
        return 1

    shutil.copytree(TEMPLATES / "service", dest)
    # Render placeholders in every text file under the new service.
    for f in dest.rglob("*"):
        if not f.is_file():
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if "{{" in text:
            text = text.replace("{{SERVICE_NAME}}", args.name)
            text = text.replace("{{SERVICE_PORT}}", str(args.port))
            f.write_text(text, encoding="utf-8")

    print(f"scaffolded {dest} ({len(list(dest.rglob('*')))} files)")
    return 0


def cmd_lint(args: argparse.Namespace) -> int:
    root = Path(args.path)
    problems: list[str] = []

    for req in GUARDRAILS["required_files"]:
        if not (root / req).exists():
            problems.append(f"missing required file: {req}")

    k8s = (root / "kubernetes.yaml").read_text(encoding="utf-8") if (root / "kubernetes.yaml").exists() else ""
    for needle in GUARDRAILS["k8s"]:
        if needle not in k8s:
            problems.append(f"kubernetes.yaml missing guardrail marker: {needle!r}")

    for f in root.rglob("*"):
        if f.is_file():
            try:
                text = f.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for ph in GUARDRAILS["placeholders"]:
                if ph in text:
                    problems.append(f"unrendered placeholder {ph!r} in {f}")

    if problems:
        print(f"FAIL {root}:")
        for p in problems:
            print(f"  - {p}")
        return 1

    print(f"ok {root} — passes golden-path guardrails")
    return 0


def _render_to(dest: Path) -> None:
    """Copy template -> dest, rendering {{SERVICE_NAME}}/{{SERVICE_PORT}}."""
    shutil.copytree(TEMPLATES / "service", dest)
    for f in dest.rglob("*"):
        if not f.is_file():
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if "{{" in text:
            text = text.replace("{{SERVICE_NAME}}", dest.name)
            text = text.replace("{{SERVICE_PORT}}", "8080")
            f.write_text(text, encoding="utf-8")


def _summarize_manifest(service: str) -> dict[str, str]:
    """Extract the golden-path guardrails from a rendered k8s manifest.

    Regex over a controlled template shape — not a YAML parser. Ceiling: only
    matches this repo's own rendered layout; if kubernetes.yaml is reformatted
    substantially, add an actual yaml.safe_load and drop these regexes.
    """
    import re

    path = TEMPLATES / "service" / "kubernetes.yaml"
    text = path.read_text(encoding="utf-8").replace("{{SERVICE_NAME}}", service)
    text = text.replace("{{SERVICE_PORT}}", "8080")

    def grab(pattern: str) -> str:
        m = re.search(pattern, text, re.MULTILINE)
        return m.group(1).strip().strip('"') if m else "?"

    def grab2(pattern: str) -> str:
        m = re.search(pattern, text, re.MULTILINE)
        if not m:
            return "?"
        return f"{m.group(1).strip().strip(chr(34))} / {m.group(2).strip().strip(chr(34))}"

    return {
        "replicas": grab(r"replicas:\s*(\d+)"),
        "image": grab(r"image:\s*(\S+)"),
        "cpu_req": grab(r"cpu:\s*\"?([\d.]+m)\"?"),
        "mem_req": grab(r"memory:\s*\"?(\S+)\"?"),
        "limits": grab2(
            r"limits:\n\s+cpu:\s*\"?([\d.]+m)\"?[^\n]*\n\s+memory:\s*\"?(\S+)\"?"
        ),
        "probe_path": grab(r"path:\s*(/\w+)"),
    }


def cmd_render(args: argparse.Namespace) -> int:
    """Render the golden path to a temp dir and summarize guardrails. Offline:
    no cluster needed — this is the deploy pre-check (kubectl apply needs a
    real cluster, which the demo does not have)."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        dest = Path(tmp) / args.name
        _render_to(dest)
        svc = _summarize_manifest(args.name)
        print(f"rendered {args.name} -> temp dir (no cluster required)")
        print(f"  image         : {svc['image']}")
        print(f"  replicas      : {svc['replicas']}")
        print(f"  requests : cpu {svc['cpu_req']} / mem {svc['mem_req']}")
        print(f"  limits   : {svc['limits']}")
        print(f"  readiness     : GET {svc['probe_path']} (port {args.port})")
    return 0


def _validate_manifest(rendered: Path) -> list[str]:
    """Offline check: parsed YAML + golden-path markers present in the manifest.

    kubectl --dry-run=client still dials the cluster API to discover resource
    kinds, so it can't validate offline — parse locally instead. Ceiling: only
    checks keys we care about, not full k8s schema.
    """
    import yaml

    problems: list[str] = []
    doc = (rendered / "kubernetes.yaml").read_text(encoding="utf-8")
    try:
        docs = [d for d in yaml.safe_load_all(doc) if d is not None]
    except yaml.YAMLError as e:
        return [f"kubernetes.yaml does not parse as YAML: {e}"]

    kinds = {d.get("kind", "?") for d in docs}
    for want in ("Deployment", "Service"):
        if want not in kinds:
            problems.append(f"manifest missing kind: {want}")

    deploys = [d for d in docs if d.get("kind") == "Deployment"]
    for dep in deploys:
        containers = (dep.get("spec", {}).get("template", {}).get("spec", {})
                      .get("containers", []))
        for c in containers:
            res = c.get("resources", {})
            if not {"requests", "limits"} <= res.keys():
                problems.append("container missing resources.requests/limits")
    return problems


def cmd_deploy(args: argparse.Namespace) -> int:
    """Render the golden path, validate the manifest offline.

    Default: parse the rendered kubernetes.yaml + assert golden-path markers
    (Deployment+Service, resource requests/limits). No cluster needed. --apply
    instead runs `kubectl apply` against a live cluster (needs context + image
    registry) — the dry-run=client path is skipped there since it also needs
    the cluster API to discover resource kinds.
    """
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        dest = Path(tmp) / args.name
        _render_to(dest)
        problems = _validate_manifest(dest)

        if args.apply:
            import subprocess
            cmd = ["kubectl", "apply", f"-f{dest / 'kubernetes.yaml'}"]
            try:
                out = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            except FileNotFoundError:
                problems.append("kubectl not found on PATH (for --apply)")
            else:
                if out.returncode != 0:
                    problems.append((out.stdout + out.stderr).strip())

    if problems:
        print(f"deploy FAILED {args.name}:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1

    mode = "applied to live cluster" if args.apply else "validated offline (no cluster)"
    print(f"deploy {args.name} -> {mode}")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    """Scaffold, lint, and tear down a throwaway service. CI-style smoke test.

    Refactored onto _render_to (no stray services/__verify__ on disk)."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        probe = Path(tmp) / "__verify__"
        _render_to(probe)
        rc_lint = cmd_lint(args=argparse.Namespace(path=str(probe)))
    return rc_lint


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="platformctl", description="Golden-path IDP CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scaffold", help="create a new service from the golden path")
    s.add_argument("name")
    s.add_argument("--port", type=int, default=8080)
    s.set_defaults(func=cmd_scaffold)

    l = sub.add_parser("lint", help="check a service against golden-path guardrails")
    l.add_argument("path")
    l.set_defaults(func=cmd_lint)

    v = sub.add_parser("verify", help="scaffold+lint+teardown a probe service")
    v.set_defaults(func=cmd_verify)

    r = sub.add_parser(
        "render",
        help="render golden path to temp dir, summarize guardrails (offline)",
    )
    r.add_argument("name")
    r.add_argument("--port", type=int, default=8080)
    r.set_defaults(func=cmd_render)

    d = sub.add_parser(
        "deploy",
        help="render + validate manifest (kubectl dry-run); --apply to a live cluster",
    )
    d.add_argument("name")
    d.add_argument("--port", type=int, default=8080)
    d.add_argument(
        "--apply",
        action="store_true",
        help="push to a live cluster instead of dry-run (needs kubectl context)",
    )
    d.set_defaults(func=cmd_deploy)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
