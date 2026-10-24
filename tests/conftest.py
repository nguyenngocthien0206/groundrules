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


@pytest.fixture(scope="session")
def pos_a(data_dir) -> dict[str, list[dict]]:
    """Vendor A files by name, in date order."""
    return {p.name: read_csv(p) for p in sorted((data_dir / "pos_a").glob("*.csv"))}


@pytest.fixture(scope="session")
def pos_b(data_dir) -> dict[str, list[dict]]:
    """Vendor B files by name (sorted by name, which is not date order)."""
    return {
        p.name: read_csv(p, delimiter=";", encoding="utf-8-sig")
        for p in sorted((data_dir / "pos_b").glob("*.csv"))
    }
