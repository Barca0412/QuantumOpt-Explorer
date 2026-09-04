#!/usr/bin/env python3
"""Build deterministic full and portal-light semifinal ZIP files."""

from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import zipfile
from pathlib import Path


EXCLUDED_PARTS = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    "dist",
    "tmp",
    "rendered",
}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".DS_Store"}


def included(path: Path, root: Path) -> bool:
    rel = path.relative_to(root)
    if any(part in EXCLUDED_PARTS for part in rel.parts):
        return False
    if path.name == ".DS_Store" or path.suffix in EXCLUDED_SUFFIXES:
        return False
    return path.is_file()


def git_sha(root: Path) -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True
    ).strip()


def write_zip(output: Path, files: list[Path], root: Path) -> None:
    epoch = (2026, 9, 5, 0, 0, 0)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in sorted(files, key=lambda item: item.relative_to(root).as_posix()):
            rel = path.relative_to(root).as_posix()
            info = zipfile.ZipInfo(f"QuantumOpt-Explorer/{rel}", epoch)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o755 if os.access(path, os.X_OK) else 0o644) << 16
            zf.writestr(info, path.read_bytes())


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default="v2.0.0")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    output_dir = root / "dist"
    output_dir.mkdir(exist_ok=True)

    required = [
        root / "README.md",
        root / "SEMIFINAL_REPORT.md",
        root / "output/pdf/QuantumOpt-Explorer_Semifinal_Report.pdf",
        root / "runs/v2/summary.csv",
        root / "runs/v2/query_log.jsonl",
        root / "uv.lock",
    ]
    missing = [str(path.relative_to(root)) for path in required if not path.is_file()]
    if missing:
        raise SystemExit(f"Missing release files: {', '.join(missing)}")

    all_files = [path for path in root.rglob("*") if included(path, root)]
    full_zip = output_dir / f"QuantumOpt-Explorer_Semifinal_{args.version}.zip"
    write_zip(full_zip, all_files, root)

    light_names = {
        "README.md",
        "REPOSITORY_URL.txt",
        "RELEASE_MANIFEST.txt",
        "LICENSE",
        "DATA_LICENSE.md",
        "THIRD_PARTY_NOTICES.md",
        "output/pdf/QuantumOpt-Explorer_Semifinal_Report.pdf",
        "archive/v1/QuantumOpt-Explorer_Problem_Definition.pdf",
    }
    light_files = [root / name for name in sorted(light_names) if (root / name).is_file()]
    light_zip = output_dir / f"QuantumOpt-Explorer_Portal_{args.version}.zip"
    write_zip(light_zip, light_files, root)

    manifest = output_dir / "SHA256SUMS.txt"
    manifest.write_text(
        "\n".join(
            [
                f"{sha256(full_zip)}  {full_zip.name}",
                f"{sha256(light_zip)}  {light_zip.name}",
                f"git_commit  {git_sha(root)}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(full_zip)
    print(light_zip)
    print(manifest)


if __name__ == "__main__":
    main()
