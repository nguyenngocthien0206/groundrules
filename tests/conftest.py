import csv
from pathlib import Path

import pytest

import generate


@pytest.fixture(scope="session")
def data_dir(tmp_path_factory) -> Path:
    """Generate the extracts once per test session, into a temp folder."""
    out = tmp_path_factory.mktemp("data")
    generate.generate(out)
    return out


def read_csv(path: Path, delimiter: str = ",", encoding: str = "utf-8") -> list[dict[str, str]]:
    with path.open(encoding=encoding, newline="") as f:
        return list(csv.DictReader(f, delimiter=delimiter))
