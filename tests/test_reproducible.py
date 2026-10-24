"""The extracts must be byte-identical on every machine and every run.

Golden question expected values are frozen from these files. If this test
fails after an intended change to the generator, run `make data-manifest`
and commit the new fixture together with the change. If it fails without
one, something made the output depend on the machine (a library version,
the OS, iteration order) and that must be fixed, not re-frozen.
"""

import json
from pathlib import Path

from synth import manifest

FIXTURE = Path(__file__).parent / "fixtures" / "expected_manifest.json"


def test_manifest_matches_the_files_on_disk(data_dir):
    written = json.loads((data_dir / manifest.MANIFEST).read_text(encoding="utf-8"))
    assert written == manifest.build(data_dir)


def test_output_matches_the_committed_fingerprint(data_dir):
    expected = json.loads(FIXTURE.read_text(encoding="utf-8"))
    actual = manifest.build(data_dir)
    assert sorted(actual) == sorted(expected), "the set of files changed"
    changed = [name for name in expected if actual[name] != expected[name]]
    assert not changed, f"{len(changed)} files differ, first: {changed[:5]}"
