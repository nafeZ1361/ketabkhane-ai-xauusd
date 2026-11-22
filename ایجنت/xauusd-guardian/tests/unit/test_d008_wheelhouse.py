"""D-008 wheelhouse verifier — positive and negative paths (no network)."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "build_wheelhouse.py"

_spec = importlib.util.spec_from_file_location("build_wheelhouse", SCRIPT)
assert _spec and _spec.loader
wheelhouse_tool = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(wheelhouse_tool)

WHEELS = {
    "colorama-0.4.6-py2.py3-none-any.whl": b"colorama-bytes",
    "iniconfig-2.3.1-py3-none-any.whl": b"iniconfig-bytes",
    "metatrader5-5.0.6231-cp311-cp311-win_amd64.whl": b"mt5-bytes",
    "numpy-2.4.6-cp311-cp311-win_amd64.whl": b"numpy-bytes",
    "packaging-25.0-py3-none-any.whl": b"packaging-bytes",
    "pluggy-1.7.0-py3-none-any.whl": b"pluggy-bytes",
    "pygments-2.21.0-py3-none-any.whl": b"pygments-bytes",
    "pytest-9.2.0-py3-none-any.whl": b"pytest-bytes",
}


def _write_tree(base: Path) -> tuple[Path, Path, Path]:
    wh = base / "wheelhouse"
    wh.mkdir(parents=True)
    manifest: list[str] = []
    lock: list[str] = []
    for filename, payload in sorted(WHEELS.items()):
        (wh / filename).write_bytes(payload)
        digest = hashlib.sha256(payload).hexdigest()
        manifest.append(f"{digest}  {filename}")
        name, version = filename[:-4].split("-")[:2]
        lock.append(f"{name}=={version} --hash=sha256:{digest}")
    manifest_path = base / "WHEELHOUSE.sha256"
    lock_path = base / "requirements-hashed.lock"
    manifest_path.write_text("\n".join(manifest) + "\n", encoding="ascii")
    lock_path.write_text("\n".join(lock) + "\n", encoding="ascii")
    return wh, lock_path, manifest_path


def test_valid_tree_verifies(tmp_path: Path) -> None:
    wh, lock, manifest = _write_tree(tmp_path)
    assert wheelhouse_tool.verify(wh, lock, manifest) == []


def test_missing_wheel_is_reported(tmp_path: Path) -> None:
    wh, lock, manifest = _write_tree(tmp_path)
    (wh / "pytest-9.2.0-py3-none-any.whl").unlink()
    problems = wheelhouse_tool.verify(wh, lock, manifest)
    assert any("pytest" in p for p in problems)
    assert any("no wheel is present" in p or "missing from the wheelhouse" in p for p in problems)


def test_extra_wheel_is_reported(tmp_path: Path) -> None:
    wh, lock, manifest = _write_tree(tmp_path)
    (wh / "evil-9.9-py3-none-any.whl").write_bytes(b"evil")
    problems = wheelhouse_tool.verify(wh, lock, manifest)
    assert any("evil" in p and "unexpected" in p for p in problems)


def test_stale_bytes_are_reported(tmp_path: Path) -> None:
    wh, lock, manifest = _write_tree(tmp_path)
    (wh / "numpy-2.4.6-cp311-cp311-win_amd64.whl").write_bytes(b"tampered")
    problems = wheelhouse_tool.verify(wh, lock, manifest)
    assert any("does not match the wheel bytes" in p for p in problems)


def test_version_mismatch_is_reported(tmp_path: Path) -> None:
    wh, lock, manifest = _write_tree(tmp_path)
    text = lock.read_text(encoding="ascii").replace("pytest==9.2.0", "pytest==9.1.0")
    lock.write_text(text, encoding="ascii")
    problems = wheelhouse_tool.verify(wh, lock, manifest)
    assert any("version mismatch for pytest" in p for p in problems)


def test_malformed_lock_hash_is_reported(tmp_path: Path) -> None:
    wh, lock, manifest = _write_tree(tmp_path)
    lines = lock.read_text(encoding="ascii").splitlines()
    lines[0] = lines[0][:-4] + "zzzz"          # break the hex digest
    lock.write_text("\n".join(lines) + "\n", encoding="ascii")
    problems = wheelhouse_tool.verify(wh, lock, manifest)
    assert any("malformed" in p for p in problems)


def test_lock_and_manifest_disagreement_is_reported(tmp_path: Path) -> None:
    wh, lock, manifest = _write_tree(tmp_path)
    lines = manifest.read_text(encoding="ascii").splitlines()
    digest, filename = lines[0].split("  ", 1)
    lines[0] = f"{'0' * 64}  {filename}"
    manifest.write_text("\n".join(lines) + "\n", encoding="ascii")
    problems = wheelhouse_tool.verify(wh, lock, manifest)
    assert any("disagree" in p or "does not match the wheel bytes" in p for p in problems)


@pytest.mark.parametrize(
    "duplicate_name",
    [
        "pytest-9.1.0-py3-none-any.whl",
        "pytest-9.2.0-1-py3-none-any.whl",
    ],
)
def test_duplicate_wheels_for_distribution_are_reported(
    tmp_path: Path, duplicate_name: str
) -> None:
    wh, lock, manifest = _write_tree(tmp_path)
    (wh / duplicate_name).write_bytes(b"duplicate-wheel-bytes")
    problems = wheelhouse_tool.verify(wh, lock, manifest)
    assert any("duplicate wheels for distribution on disk: pytest" in p for p in problems)


def test_build_refuses_a_non_empty_directory(tmp_path: Path) -> None:
    wh = tmp_path / "wheelhouse"
    wh.mkdir()
    (wh / "leftover.whl").write_bytes(b"x")
    with pytest.raises(SystemExit, match="refusing non-empty"):
        wheelhouse_tool.main(["--out", str(wh)])
