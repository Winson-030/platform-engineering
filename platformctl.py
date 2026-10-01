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


def cmd_verify(args: argparse.Namespace) -> int:
    """Scaffold, lint, and tear down a throwaway service. CI-style smoke test."""
    probe = Path("services/__verify__")
    if probe.exists():
        shutil.rmtree(probe)
    rc_scaff = cmd_scaffold(argparse.Namespace(name="__verify__", port=8080))
    rc_lint = cmd_lint(args=argparse.Namespace(path=str(probe)))
    shutil.rmtree(probe, ignore_errors=True)
    return rc_scaff or rc_lint


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

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
