#!/usr/bin/env python3
"""Create a reproducible manifest for an intelligence evaluation bundle."""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_revision(root: Path) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def collect_files(root: Path) -> list[Path]:
    paths: list[Path] = []
    for directory in (root / "src", root / "scripts", root / "docs", root / "tests"):
        if directory.exists():
            paths.extend(path for path in directory.rglob("*") if path.is_file())
    for path in (root / "README.md", root / "pyproject.toml", root / "requirements.txt"):
        if path.exists():
            paths.append(path)
    return sorted(set(paths))


def build_manifest(root: Path, benchmark: Path | None = None) -> dict:
    files = collect_files(root)
    manifest = {
        "schema": "intelligence-artifact-bundle.v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "git_revision": git_revision(root),
        "python": sys.version,
        "platform": platform.platform(),
        "files": [
            {"path": str(path.relative_to(root)), "sha256": sha256(path),
             "bytes": path.stat().st_size}
            for path in files
        ],
    }
    if benchmark and benchmark.exists():
        manifest["benchmark"] = {
            "path": str(benchmark.relative_to(root)),
            "sha256": sha256(benchmark),
            "bytes": benchmark.stat().st_size,
        }
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--benchmark", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    benchmark = args.benchmark.resolve() if args.benchmark else None
    manifest = build_manifest(root, benchmark)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"wrote {args.output} ({len(manifest['files'])} files)")


if __name__ == "__main__":
    main()
