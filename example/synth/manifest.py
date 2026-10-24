"""A fingerprint of every extract: SHA-256 and row count per file.

Golden question expected values are frozen from these files, so the files
must be byte-identical on every machine. The test suite compares this
manifest with the committed copy in `tests/fixtures/expected_manifest.json`.
"""

import hashlib
import json
from pathlib import Path

MANIFEST = "_manifest.json"


def _rows(path: Path) -> int:
    lines = path.read_bytes().count(b"\n")
    return lines if path.suffix == ".jsonl" else lines - 1  # CSV files have a header


def build(out: Path) -> dict[str, dict[str, object]]:
    files = sorted(p for p in out.rglob("*") if p.is_file() and p.name != MANIFEST)
    return {
        p.relative_to(out).as_posix(): {
            "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
            "rows": _rows(p),
        }
        for p in files
    }


def write(out: Path) -> dict[str, dict[str, object]]:
    manifest = build(out)
    (out / MANIFEST).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return manifest
