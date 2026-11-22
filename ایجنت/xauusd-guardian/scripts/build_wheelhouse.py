"""Build or verify the exact D-008 offline wheelhouse (network needed to build only).

Build:
    python scripts/build_wheelhouse.py --out C:\\GuardianD008\\wheelhouse

The output directory must be empty; stale or extra wheels are never silently included.

Verify (offline, read-only):
    python scripts/build_wheelhouse.py --verify \
        --wheelhouse C:\\GuardianD008\\wheelhouse \
        --lock ایجنت/xauusd-guardian/requirements-hashed.lock \
        --manifest ایجنت/xauusd-guardian/WHEELHOUSE.sha256

Verification fails on: a wheel named in the lock/manifest but absent on disk, a wheel on
disk that neither file names, a byte or hash mismatch, a lock/manifest disagreement, a
version disagreement between the filename and the lock, and a closure that differs from
``PACKAGES``.
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
LOCK_RE = re.compile(r"^(?P<name>[A-Za-z0-9_.\-]+)==(?P<version>[^\s]+)\s+--hash=sha256:(?P<hash>[0-9a-f]{64})$")


def canonical(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def expected_closure() -> dict[str, str]:
    result: dict[str, str] = {}
    for item in PACKAGES:
        name, version = item.split("==", 1)
        key = canonical(name)
        if key in result:
            raise RuntimeError(f"duplicate package in PACKAGES: {name}")
        result[key] = version
    return result


def parse_manifest(text: str) -> tuple[dict[str, tuple[str, str]], list[str]]:
    entries: dict[str, tuple[str, str]] = {}
    errors: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        parts = line.split("  ", 1)
        if len(parts) != 2 or not re.fullmatch(r"[0-9a-f]{64}", parts[0]):
            errors.append(f"manifest line is malformed: {raw!r}")
            continue
        digest, filename = parts
        if not filename.endswith(".whl"):
            errors.append(f"manifest names a non-wheel: {filename}")
            continue
        stem = filename[:-4]
        chunks = stem.split("-")
        if len(chunks) < 5:
            errors.append(f"invalid wheel filename: {filename}")
            continue
        key = canonical(chunks[0])
        if key in entries:
            errors.append(f"duplicate distribution in manifest: {key}")
            continue
        entries[key] = (chunks[1], digest)
    return entries, errors


def parse_lock(text: str) -> tuple[dict[str, tuple[str, str]], list[str]]:
    entries: dict[str, tuple[str, str]] = {}
    errors: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = LOCK_RE.match(line)
        if not match:
            errors.append(f"lock line is malformed: {raw!r}")
            continue
        key = canonical(match.group("name"))
        if key in entries:
            errors.append(f"duplicate distribution in lock: {key}")
            continue
        entries[key] = (match.group("version"), match.group("hash"))
    return entries, errors


def verify(wheelhouse: Path, lock: Path, manifest: Path) -> list[str]:
    """Return a list of problems; an empty list means the closure is consistent."""
    errors: list[str] = []
    if not wheelhouse.is_dir():
        return [f"wheelhouse is not a directory: {wheelhouse}"]
    for path in (lock, manifest):
        if not path.is_file():
            errors.append(f"missing file: {path}")
    if errors:
        return errors

    locked, lock_errors = parse_lock(lock.read_text(encoding="utf-8"))
    listed, manifest_errors = parse_manifest(manifest.read_text(encoding="utf-8"))
    errors.extend(lock_errors)
    errors.extend(manifest_errors)

    on_disk: dict[str, list[Path]] = {}
    for wheel in sorted(wheelhouse.glob("*.whl")):
        chunks = wheel.name[:-4].split("-")
        if len(chunks) < 5:
            errors.append(f"invalid wheel filename on disk: {wheel.name}")
            continue
        key = canonical(chunks[0])
        on_disk.setdefault(key, []).append(wheel)

    for key, wheels in sorted(on_disk.items()):
        if len(wheels) > 1:
            names = ", ".join(wheel.name for wheel in wheels)
            errors.append(f"duplicate wheels for distribution on disk: {key}: {names}")

    expected = expected_closure()
    for scope, table in (("lock", locked), ("manifest", listed)):
        missing = sorted(set(table) - set(on_disk))
        for key in missing:
            errors.append(f"{scope} names {key} but no wheel is present")
        extra = sorted(set(on_disk) - set(table))
        for key in extra:
            names = ", ".join(wheel.name for wheel in on_disk[key])
            errors.append(f"{scope} does not name {key}, but {names} are on disk")

    for key in sorted(set(expected) - set(on_disk)):
        errors.append(f"required distribution missing from the wheelhouse: {key}")
    for key in sorted(set(on_disk) - set(expected)):
        errors.append(f"unexpected distribution in the wheelhouse: {key}")

    for key, wheels in sorted(on_disk.items()):
        for wheel in wheels:
            digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
            version_on_disk = wheel.name[:-4].split("-")[1]
            if key in listed:
                version, declared = listed[key]
                if version != version_on_disk:
                    errors.append(
                        f"version mismatch for {key}: filename {version_on_disk}, manifest {version}"
                    )
                if declared != digest:
                    errors.append(f"manifest hash does not match the wheel bytes: {key}")
            if key in locked:
                version, declared = locked[key]
                if version != version_on_disk:
                    errors.append(
                        f"version mismatch for {key}: filename {version_on_disk}, lock {version}"
                    )
                if declared != digest:
                    errors.append(f"lock hash does not match the wheel bytes: {key}")
    for key in sorted(set(locked) & set(listed)):
        if locked[key][1] != listed[key][1]:
            errors.append(f"lock and manifest disagree on the hash for {key}")
        if locked[key][0] != listed[key][0]:
            errors.append(f"lock and manifest disagree on the version for {key}")
    return errors


def build(out: Path, python: str) -> int:
    out.mkdir(parents=True, exist_ok=True)
    if any(out.iterdir()):
        raise SystemExit(f"refusing non-empty wheelhouse directory: {out}")

    expected = expected_closure()
    with tempfile.TemporaryDirectory(prefix="guardian-d008-") as temp:
        staging = Path(temp)
        command = [
            python, "-m", "pip", "download", *PACKAGES,
            "--only-binary=:all:", "--index-url", PYPI, "-d", str(staging),
        ]
        print("+", " ".join(command))
        subprocess.run(command, check=True)

        wheels = sorted(staging.glob("*.whl"))
        found: dict[str, tuple[str, Path]] = {}
        for wheel in wheels:
            chunks = wheel.name[:-4].split("-")
            if len(chunks) < 5:
                raise SystemExit(f"invalid wheel filename: {wheel.name}")
            name, version = canonical(chunks[0]), chunks[1]
            if name in found:
                raise SystemExit(f"duplicate wheel for distribution: {name}")
            found[name] = (version, wheel)

        if set(found) != set(expected):
            raise SystemExit(
                f"wheel closure mismatch; missing={sorted(set(expected) - set(found))}, "
                f"extra={sorted(set(found) - set(expected))}"
            )
        for name, version in expected.items():
            if found[name][0] != version:
                raise SystemExit(f"version mismatch for {name}: expected {version}, got {found[name][0]}")

        manifest: list[str] = []
        locked: list[str] = []
        for name in sorted(found):
            version, source = found[name]
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            shutil.copy2(source, out / source.name)
            manifest.append(f"{digest}  {source.name}")
            locked.append(f"{source.name[:-4].split('-')[0]}=={version} --hash=sha256:{digest}")

    (out.parent / "WHEELHOUSE.sha256").write_text("\n".join(manifest) + "\n", encoding="ascii")
    (out.parent / "requirements-hashed.lock").write_text(
        "\n".join(HEADER + locked) + "\n", encoding="ascii"
    )
    print(f"wheels: {len(found)}; manifest and hashed lock written beside {out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="build or verify the D-008 offline wheelhouse")
    parser.add_argument("--out", help="empty wheelhouse directory (build mode)")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--verify", action="store_true", help="verify an existing wheelhouse (offline)")
    parser.add_argument("--wheelhouse")
    parser.add_argument("--lock")
    parser.add_argument("--manifest")
    args = parser.parse_args(argv)

    if args.verify:
        if not (args.wheelhouse and args.lock and args.manifest):
            parser.error("--verify needs --wheelhouse, --lock and --manifest")
        problems = verify(Path(args.wheelhouse), Path(args.lock), Path(args.manifest))
        if problems:
            for problem in problems:
                print(f"VERIFY FAIL: {problem}", file=sys.stderr)
            return 1
        print("VERIFY OK: lock, manifest and wheel bytes agree; closure is exact")
        return 0

    if not args.out:
        parser.error("--out is required unless --verify is used")
    return build(Path(args.out), args.python)


if __name__ == "__main__":
    raise SystemExit(main())
