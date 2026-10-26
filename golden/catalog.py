"""Load golden questions and their frozen expected values."""

import hashlib
from pathlib import Path

import yaml

GOLDEN = Path(__file__).resolve().parent
QUESTIONS_DIR = GOLDEN / "questions"
EXPECTED_FILE = GOLDEN / "expected.yml"
ROOT = GOLDEN.parent

KINDS = ("tacit_rule", "conflict", "caveat_required", "deprecated")
QUESTION_FIELDS = {
    "id", "question", "kind", "metric", "filters", "as_of", "tolerance",
    "why", "decision", "signed_off_by", "signed_off_on",
}


def load_questions() -> list[dict]:
    questions = []
    for path in sorted(QUESTIONS_DIR.glob("*.yml")):
        for q in yaml.safe_load(path.read_text(encoding="utf-8"))["questions"]:
            q["file"] = path.name
            questions.append(q)
    return questions


def load_expected() -> dict:
    return yaml.safe_load(EXPECTED_FILE.read_text(encoding="utf-8"))


def data_fingerprint(data_dir: Path) -> str:
    """SHA-256 of the extracts' manifest: the data the expected values came from."""
    return hashlib.sha256((data_dir / "_manifest.json").read_bytes()).hexdigest()
