"""Build a clean, exact D-008 offline wheelhouse (requires network; installs nothing).

Usage:
    python scripts/build_wheelhouse.py --out C:\\GuardianD008\\wheelhouse

The output directory must be empty. Stale or extra wheels are never silently included.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PYPI = "https://pypi.org/simple"
PACKAGES = [
    "MetaTrader5==5.0.6231",
    "numpy==2.4.6",
    "pytest==9.2.0",
    "pluggy==1.7.0",
    "iniconfig==2.3.1",
    "packaging==25.0",
    "colorama==0.4.6",
    "Pygments==2.21.0",
]
HEADER = [
    "# D-008 hashed lock - Python 3.11.8 win_amd64",
    "# install: pip install --no-index --find-links <wheelhouse> --require-hashes -r requirements-hashed.lock",
]


def canonical(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def expected_closure() -> dict[str, str]:
    result = {}
    for item in PACKAGES:
        name, version = item.split("==", 1)
        key = canonical(name)
        if key in result:
            raise RuntimeError(f"duplicate package in PACKAGES: {name}")
        result[key] = version
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="build the D-008 offline wheelhouse")
    parser.add_argument("--out", required=True, help="empty wheelhouse directory")
    parser.add_argument("--python", default=sys.executable, help="interpreter whose pip downloads")
    args = parser.parse_args(argv)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    if any(out.iterdir()):
        raise SystemExit(f"refusing non-empty wheelhouse directory: {out}")

    expected = expected_closure()
    with tempfile.TemporaryDirectory(prefix="guardian-d008-") as temp:
        staging = Path(temp)
        command = [
            args.python, "-m", "pip", "download", *PACKAGES,
            "--only-binary=:all:", "--index-url", PYPI, "-d", str(staging),
        ]
        print("+", " ".join(command))
        subprocess.run(command, check=True)

        wheels = sorted(staging.glob("*.whl"))
        found: dict[str, tuple[str, Path]] = {}
        for wheel in wheels:
            parts = wheel.name.split("-")
            if len(parts) < 5:
                raise SystemExit(f"invalid wheel filename: {wheel.name}")
            name, version = canonical(parts[0]), parts[1]
            if name in found:
                raise SystemExit(f"duplicate wheel for distribution: {name}")
            found[name] = (version, wheel)

        if set(found) != set(expected):
            missing = sorted(set(expected) - set(found))
            extra = sorted(set(found) - set(expected))
            raise SystemExit(f"wheel closure mismatch; missing={missing}, extra={extra}")
        for name, version in expected.items():
            actual = found[name][0]
            if actual != version:
                raise SystemExit(f"version mismatch for {name}: expected {version}, got {actual}")

        manifest: list[str] = []
        locked: list[str] = []
        for name in sorted(found):
            version, source = found[name]
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            shutil.copy2(source, out / source.name)
            manifest.append(f"{digest}  {source.name}")
            locked.append(f"{source.name.split('-')[0]}=={version} --hash=sha256:{digest}")

    (out.parent / "WHEELHOUSE.sha256").write_text("\n".join(manifest) + "\n", encoding="ascii")
    (out.parent / "requirements-hashed.lock").write_text(
        "\n".join(HEADER + locked) + "\n", encoding="ascii"
    )
    print(f"wheels: {len(wheels)}; manifest and hashed lock written beside wheelhouse")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
